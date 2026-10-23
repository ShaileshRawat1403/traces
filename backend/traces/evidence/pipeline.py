"""Verification pipeline driver for the Task 002 baseline (port of research/task002/pipeline/run.sh,
inside_run.py and inside_run_002b.py with portable paths).

Outside the sandbox: pinned fetch, throwaway clones, before/after snapshots, the CT15(e) network control.
Inside one sandbox invocation (workers/sandbox.sh, `unshare -rn`): the isolation probe, three CodeGraph index runs
(real, copyA, copyB) with per-process namespace logging, the expected-chain fixture and injected negatives (validator
inputs only), the adapter on all three indexes, the adapter negative contract cases, the frozen line checker, the
validation twice (determinism), and schema checks. Results go to <run_dir>/inside_result.json; the contract and
regression tests (tests/contract, tests/regression) read them.

Usage:  python -m traces.evidence.pipeline baseline [--run-id ID]          (driver, outside)
        python -m traces.evidence.pipeline inside <run_dir>                  (called by the driver, inside)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from traces.core.common import canonical_hash, now_ist
from traces.core.config import Settings, get_settings
from traces.fixtures.task002.chain import REPO, REPO_SHA, REPO_URL
from traces.ingest.fetch import ensure_pinned_checkout, local_clone
from traces.ingest.urls import parse_repo_url

PKG = Path(__file__).resolve().parents[1]  # backend/traces
SCHEMA_03 = PKG / "evidence" / "schema" / "evidence_record.v0.3.schema.json"
CHECKER_DIR = PKG / "validators" / "checker"
CODEGRAPH_PIN = {"package": "@colbymchenry/codegraph", "version": "1.6.2",
                 "npm_integrity": "sha512-hODH/mGnCf3IUMs6rzktv/zbecJIKJfdZAYHZ9mqecb0G7ZkHaA8CZafDVnswANFEL1YFcG+lfAwc5SIXzUH6Q==",
                 "npm_shasum": "372b7b4f0190197b07d444116d6692240883a2d5", "schema_version_max": 11, "extraction_version": "27"}


ISOLATION_OFF = "off"


class IsolationUnavailable(RuntimeError):
    """Network isolation for the analysis workers cannot be shown (E_ISOLATION). The run must stop (D-Q5, D-002A.6, D-026)."""

    code = "E_ISOLATION"


def resolve_isolation(s: Settings) -> str:
    """Return "unshare" when `unshare -rn` works, or "off" only for the explicit dev override TRACES_ISOLATION=off.
    Fails closed (IsolationUnavailable) otherwise: "auto" never falls back to running without isolation, an explicit
    "unshare" that does not work is an error, and any other value (including the old "none") is refused (D-026)."""
    mode = (s.isolation or "auto").strip().lower()
    if mode == ISOLATION_OFF:
        return ISOLATION_OFF
    if mode not in ("auto", "unshare"):
        raise IsolationUnavailable(f"TRACES_ISOLATION={s.isolation!r} is not supported (use auto, unshare, or off for an "
                                   "explicit unisolated dev run)")
    # Probe through the real wrapper (workers/sandbox.sh with unshare), so the check is exactly what the workers will get
    # and every non-git process the worker starts is still the sandbox.
    try:
        with tempfile.TemporaryDirectory(prefix="traces-isoprobe-") as home:
            env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "TRACES_SANDBOX_HOME": home,
                   "TRACES_TOOLCHAIN_DIR": str(s.toolchain_dir), "TRACES_ISOLATION": "unshare"}
            ok = subprocess.run(["bash", str(s.workers_dir / "sandbox.sh"), "true"], env=env, capture_output=True,
                                timeout=20, stdin=subprocess.DEVNULL).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        ok = False
    if not ok:
        raise IsolationUnavailable("no network namespace is available (`unshare -rn` failed), so the indexer cannot be shown "
                                   "to run without network; the run stops. Set TRACES_ISOLATION=off only for an explicit, "
                                   "unisolated dev run (never acceptance evidence)")
    return "unshare"


def target_checkout(s: Settings) -> Path:
    ref = parse_repo_url(REPO_URL)
    return ensure_pinned_checkout(ref, REPO_SHA, s.targets_dir / ref.cache_key / REPO_SHA / "source")


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def snapshot(run: Path, which: str, source: Path, s: Settings) -> None:
    """CT15/CT16 evidence: the pinned cache checkout, spec/checker hashes, and a file list of every tracked area
    the pipeline must not modify (everything outside the run dir)."""
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    g = lambda *a: subprocess.run(["git", "-C", str(source), "--no-optional-locks", *a], capture_output=True, text=True, env=env).stdout
    lines = [f"# {which} {now_ist()}", "## source", g("status", "--porcelain", "--untracked-files=all"), g("rev-parse", "HEAD"),
             f"git index mtime {os.stat(source / '.git' / 'index').st_mtime_ns}", "## lead", "## schema"]
    lines += [f"{_sha256(p)}  {p.relative_to(s.repo_root)}" for p in sorted((PKG / "evidence" / "schema").glob("*.json"))]
    lines += ["## checker"] + [f"{_sha256(p)}  {p.name}" for p in sorted(CHECKER_DIR.iterdir()) if p.is_file()]
    lines += ["## sandbox"] + [f"{_sha256(p)}  {p.name}" for p in sorted(s.workers_dir.iterdir()) if p.is_file()]
    (run / f"snapshot_{which}.txt").write_text("\n".join(lines) + "\n")
    roots = [source, s.repo_root / "backend", s.repo_root / "workers", s.toolchain_dir]
    out = []
    for root in roots:
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if d not in ("node_modules", "__pycache__", ".pytest_cache")]
            for f in fns:
                p = os.path.join(dp, f)
                try:
                    st = os.stat(p)
                except FileNotFoundError:
                    continue
                out.append(f"{st.st_mtime_ns} {st.st_size} {p}")
    (run / f"files_{which}.txt").write_text("\n".join(sorted(out, key=lambda x: x.split(" ", 2)[2])) + "\n")


def sandbox_cmd(s: Settings, iso: str, cmd: list[str], run: Path) -> tuple[list[str], dict[str, str]]:
    env = {**os.environ, "TRACES_SANDBOX_HOME": str(run / "sandbox_home"), "TRACES_TOOLCHAIN_DIR": str(s.toolchain_dir),
           "TRACES_ISOLATION": iso, "PYTHONDONTWRITEBYTECODE": "1"}
    return ["bash", str(s.workers_dir / "sandbox.sh"), *cmd], env


def run_baseline(run_id: str | None = None, s: Settings | None = None) -> Path:
    s = s or get_settings()
    try:
        iso = resolve_isolation(s)
    except IsolationUnavailable as e:
        raise SystemExit(f"E_ISOLATION: {e}") from None
    source = target_checkout(s)
    rid = run_id or "t002-" + time.strftime("%Y%m%dT%H%M%S")
    run = s.runs_dir / rid
    if run.exists():
        raise SystemExit(f"run dir exists: {run}")
    run.mkdir(parents=True)
    for c in ("real", "copyA", "copyB"):
        local_clone(source, run / c, REPO_SHA)
    meta = {"run_id": rid, "isolation": iso, "source": str(source), "python": sys.version.split()[0], "repo": REPO, "repo_sha": REPO_SHA}
    (run / "run_meta.json").write_text(json.dumps(meta, indent=1))
    snapshot(run, "before", source, s)
    ce, ons = "unknown", "unknown"
    env = {**os.environ, "TRACES_TOOLCHAIN_DIR": str(s.toolchain_dir)}
    if iso == "unshare":
        out = subprocess.run(["bash", str(s.workers_dir / "control_outside.sh"), str(run / "netprobe.log")], capture_output=True, text=True, env=env).stdout.split()
        ce, ons = (out + ["unknown", "unknown"])[:2]
    py = sys.executable
    inner = f"{py} -m traces.evidence.pipeline inside {run}"
    if iso == "unshare":
        inner = f"bash {s.workers_dir / 'probe_inside.sh'} {run / 'netprobe.log'} && {inner}"
    cmd, senv = sandbox_cmd(s, iso, ["env", f"OUTER_NS={ons}", f"CONTROL_E={ce}", "bash", "-c", inner], run)
    senv["PYTHONPATH"] = str(PKG.parent) + os.pathsep + senv.get("PYTHONPATH", "")
    t0 = time.time()
    p = subprocess.run(cmd, env=senv, capture_output=True, text=True)
    (run / "inside_stdout.txt").write_text(p.stdout + p.stderr + f"\n[exit={p.returncode} wall_s={time.time() - t0:.1f}]\n")
    snapshot(run, "after", source, s)
    if p.returncode != 0:
        raise SystemExit(f"baseline pipeline failed (exit {p.returncode}); see {run / 'inside_stdout.txt'}")
    return run


# ------------------------------------------------------------------ inside the sandbox
class Inside:
    def __init__(self, run: Path):
        self.s = get_settings()
        self.run = run.resolve()
        self.meta = json.loads((self.run / "run_meta.json").read_text())
        self.rid = self.meta["run_id"]
        self.iso = self.meta["isolation"]
        self.py = sys.executable
        self.log = open(self.run / "commands.log", "a")

    def sh(self, cmd, cwd=None, env=None, check=False, out=None):
        t0 = time.time()
        p = subprocess.run([str(c) for c in cmd], cwd=cwd, env={**os.environ, **(env or {})}, capture_output=True, text=True)
        self.log.write(f"\n[{now_ist()}] $ {' '.join(map(str, cmd))}\n{p.stdout[-6000:]}{p.stderr[-6000:]}[exit={p.returncode} wall_s={time.time() - t0:.1f}]\n")
        self.log.flush()
        if out:
            Path(out).write_text(p.stdout)
        if check and p.returncode != 0:
            raise SystemExit(f"command failed: {cmd}: {p.stderr[-2000:]}")
        return p

    def manifest(self, name, checkout, index, extra=None, cg=None):
        d = self.run / name
        d.mkdir(parents=True, exist_ok=True)
        m = {"run_id": self.rid, "repo": REPO, "repo_sha": REPO_SHA, "checkout_path": str(checkout), "index_path": str(index),
             "codegraph": dict(CODEGRAPH_PIN, **(cg or {})),
             "wrapper": {"path": "workers/sandbox.sh", "sha256": _sha256(self.s.workers_dir / "sandbox.sh")},
             "env": {"telemetry_disabled": True, "isolation": self.iso, "netprobe_log": str(self.run / "netprobe.log")},
             "adapter_out": str(d / "out"), "package_dir": str(self.s.codegraph_package_dir), "lockfile": str(self.s.lockfile),
             "registry_record": str(self.s.registry_record)}
        if extra:
            m.update(extra)
        p = d / "manifest.json"
        p.write_text(json.dumps(m, indent=1))
        return p, m

    def adapter(self, name, checkout, index, **kw):
        p, m = self.manifest(name, checkout, index, **kw)
        r = self.sh([self.py, "-m", "traces.adapter.codegraph", "--manifest", p])
        e = Path(m["adapter_out"]) / "errors.json"
        return {"exit": r.returncode, "stdout": r.stdout.strip(), "errors": json.loads(e.read_text()) if e.exists() else None, "out": m["adapter_out"], "manifest": str(p)}

    def clone(self, name, rev=REPO_SHA):
        d = self.run / name
        self.sh(["git", "clone", "-q", "--config", "core.symlinks=false", "--no-hardlinks", "--no-checkout", self.meta["source"], d], check=True)
        self.sh(["git", "-C", d, "-c", "advice.detachedHead=false", "checkout", "-q", "--detach", rev], check=True)
        return d

    def db_copy(self, name, mutate):
        d = self.run / "ct" / name
        d.mkdir(parents=True, exist_ok=True)
        p = d / "codegraph.db"
        src = sqlite3.connect(f"file:{self.run / 'real' / '.codegraph' / 'codegraph.db'}?mode=ro&immutable=1", uri=True)
        dst = sqlite3.connect(p)
        src.backup(dst)
        src.close()
        mutate(dst)
        dst.commit()
        dst.close()
        return p

    def main(self):
        R = self.run
        res = {"run_id": self.rid, "started": now_ist(), "isolation": self.iso}
        vi = R / "validator_inputs"
        vi.mkdir(exist_ok=True)
        fixture = R / "fixtures" / "chain_create_item.json"
        fixture.parent.mkdir(exist_ok=True)
        self.sh([self.py, "-m", "traces.fixtures.task002.chain", "--src", R / "real", "--fixture-out", fixture, "--injected-out", vi / "injected.jsonl",
                 "--run-id", self.rid, "--spotcheck-out", R / "fixture_spotcheck.txt"], check=True)
        # three index runs on throwaway clones (CT14, CT15 d); namespace of the indexer and every child logged
        idx = {}
        for c in ("real", "copyA", "copyB"):
            d = R / c
            r = self.sh(["bash", self.s.workers_dir / "index_with_ns.sh", d, R / "netprobe.log", R / f"index_{c}.log"])
            idx[c] = {"exit": r.returncode, "dir": str(d), "index_db_sha256": _sha256(d / ".codegraph" / "codegraph.db") if (d / ".codegraph" / "codegraph.db").exists() else None}
            if r.returncode != 0:
                (R / "inside_result.json").write_text(json.dumps(dict(res, index_runs=idx), indent=1))
                raise SystemExit(f"indexing failed for {c}")
        res["index_runs"] = idx
        A = {c: self.adapter(f"adapter_{c}", R / c, R / c / ".codegraph" / "codegraph.db") for c in ("real", "copyA", "copyB")}
        res["adapter"] = A
        if A["real"]["exit"] != 0:
            (R / "inside_result.json").write_text(json.dumps(res, indent=1))
            raise SystemExit("adapter failed on the real index: " + A["real"]["stdout"])
        rec_real = Path(A["real"]["out"]) / "records.jsonl"
        res["canonical_hash"] = {k: (canonical_hash([json.loads(line) for line in open(Path(v["out"]) / "records.jsonl")]) if v["exit"] == 0 else None) for k, v in A.items()}
        # CT5 schema: self-test must run (fix of the 1049-3 defect) and every adapter record must validate
        self.sh([self.py, "-m", "traces.evidence.schema_check", SCHEMA_03, "--self-test"], out=R / "schema_selftest.txt")
        self.sh([self.py, "-m", "traces.evidence.schema_check", SCHEMA_03, rec_real], out=R / "schema_adapter.json")
        cA = R / "copyA"
        dbA = cA / ".codegraph" / "codegraph.db"
        neg = {}
        neg["CT1a_version_1.6.3"] = self.adapter("ct/CT1a", cA, self.db_copy("CT1a", lambda c: c.execute("UPDATE project_metadata SET value='1.6.3' WHERE key='indexed_with_version'")))
        neg["CT1b_wrong_integrity"] = self.adapter("ct/CT1b", cA, dbA, cg={"npm_integrity": "sha512-" + "A" * 86 + "=="})
        neg["CT2a_edges_provenance_renamed"] = self.adapter("ct/CT2a", cA, self.db_copy("CT2a", lambda c: c.execute("ALTER TABLE edges RENAME COLUMN provenance TO provenance_x")))
        neg["CT2b_no_unresolved_refs"] = self.adapter("ct/CT2b", cA, self.db_copy("CT2b", lambda c: c.execute("DROP TABLE unresolved_refs")))
        c3a = self.clone("ct/CT3a_clone")
        f3 = c3a / "backend/app/api/routes/items.py"
        f3.write_bytes(f3.read_bytes().replace(b"def create_item(", b"def create_iten(", 1))
        neg["CT3a_byte_changed"] = self.adapter("ct/CT3a", c3a, dbA)
        neg["CT3b_head_minus_1"] = self.adapter("ct/CT3b", self.clone("ct/CT3b_clone", REPO_SHA + "~1"), dbA)
        neg["CT3c_manifest_other_sha"] = self.adapter("ct/CT3c", cA, dbA, extra={"repo_sha": "0" * 40})

        def guess(c):
            rid = c.execute("SELECT id FROM edges WHERE json_extract(metadata,'$.resolvedBy')='exact-match' ORDER BY id LIMIT 1").fetchone()[0]
            md = json.loads(c.execute("SELECT metadata FROM edges WHERE id=?", (rid,)).fetchone()[0])
            md["resolvedBy"] = "guess"
            c.execute("UPDATE edges SET metadata=? WHERE id=?", (json.dumps(md), rid))
        neg["CT4_resolvedBy_guess"] = self.adapter("ct/CT4", cA, self.db_copy("CT4", guess))
        neg["CT9a_absolute_path"] = self.adapter("ct/CT9a", cA, self.db_copy("CT9a", lambda c: c.execute("UPDATE files SET path='/etc/passwd' WHERE path='backend/app/crud.py'")))
        neg["CT9b_dotdot_path"] = self.adapter("ct/CT9b", cA, self.db_copy("CT9b", lambda c: c.execute("UPDATE files SET path='../outside.py' WHERE path='backend/app/crud.py'")))
        res["negative"] = neg
        # frozen checker (CT7): hashes must match SHA256SUMS
        self.sh(["sha256sum", "-c", "SHA256SUMS"], cwd=CHECKER_DIR, out=R / "checker_sha256.txt")
        for mode in ("parser", "lab_route"):
            self.sh([self.py, CHECKER_DIR / "line_checker_v1.py", "--db", R / "real/.codegraph/codegraph.db", "--src", R / "real", "--sha", REPO_SHA,
                     "--ts-module", self.s.ts_module, "--mode", mode, "--out", R / f"checker_{mode}.json"],
                    env={"TS_MODULE": str(self.s.ts_module)}, out=R / f"checker_{mode}_stdout.json")
        # validation twice (determinism)
        vt = {}
        for k in ("v1", "v2"):
            vd = R / k
            vd.mkdir(exist_ok=True)
            (vd / "manifest.json").write_text(json.dumps({"run_id": self.rid}))
            t0 = time.time()
            r = self.sh([self.py, "-m", "traces.validators.orchestrator", "--run-dir", vd, "--records", rec_real, "--fixture", fixture, "--injected", vi / "injected.jsonl",
                         "--src", R / "real", "--sha", REPO_SHA, "--ts-module", self.s.ts_module, "--node", self.s.node])
            vt[k] = {"exit": r.returncode, "wall_s": round(time.time() - t0, 1), "stdout": r.stdout[-3000:], "stderr": r.stderr[-3000:]}
            if r.returncode == 0:
                ev = [json.loads(line) for line in open(vd / "validation" / "evidence.jsonl")]
                vt[k]["canonical_hash"] = canonical_hash(ev)
                self.sh([self.py, "-m", "traces.evidence.schema_check", SCHEMA_03, vd / "validation" / "evidence.jsonl"], out=vd / "schema_evidence.json")
                if k == "v1":  # steps 8 to 10 artifacts (chain.json, coverage.json), as the research run produced them (F7)
                    rr = self.sh([self.py, "-m", "traces.evidence.report", vd / "validation"])
                    vt[k]["report"] = {"exit": rr.returncode, "stdout": rr.stdout[-2000:], "stderr": rr.stderr[-2000:]}
        res["validation"] = vt
        res["finished"] = now_ist()
        (R / "inside_result.json").write_text(json.dumps(res, indent=1, default=str))
        print("INSIDE_DONE", json.dumps({k: v["exit"] for k, v in vt.items()}))
        if any(v["exit"] != 0 for v in vt.values()):
            raise SystemExit("validation failed")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="traces.evidence.pipeline")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("baseline")
    b.add_argument("--run-id")
    i = sub.add_parser("inside")
    i.add_argument("run_dir")
    a = ap.parse_args(argv)
    if a.cmd == "baseline":
        print(run_baseline(a.run_id))
    else:
        Inside(Path(a.run_dir)).main()


if __name__ == "__main__":
    main()
