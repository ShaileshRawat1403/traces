"""INDEX worker: one index job for one public repository at one pinned SHA (CONTRACTS.md section 3.2, D-022).

Phases (job.phase), each a step of the job state machine:
  fetching      safe pinned clone into the per-repo cache (traces.ingest.fetch: no hooks, no LFS smudge, no submodules,
                public only, size/time/file caps). The only step with network access.
  checking_out  throwaway working copy in the run directory (CodeGraph writes .codegraph/ into it, never into the cache)
  indexing      CodeGraph 1.6.2 inside workers/sandbox.sh (unshare -rn: no network, credentials stripped, CPU/file/fd
                ulimits) with every indexer process's network namespace logged (workers/index_with_ns.sh)
  adapting      isolation probe + the fail-closed adapter in ONE sandbox invocation (adapter check 4.7 compares its
                own namespace with the probed one)
  validating    independent validators (CPython 3.14 ast, TypeScript 6.0.3 compiler API) inside the sandbox. The Task 002
                regression fixture (expected chain + injected negatives) is added only for its own snapshot,
                fastapi/full-stack-fastapi-template@b1125d8; every other snapshot runs with --no-fixture.
  storing       migrate to traces-evidence/0.4 and store; deterministic components, languages, frameworks and
                generated paths from Git objects (traces.evidence.components)
  history       traces.history.run(...) when the History module provides it (H1), else recorded as skipped

Memory: an RSS watchdog sums VmRSS over the sandboxed process session and kills it past TRACES_MAX_RSS_MB (default
6144). RLIMIT_AS and RLIMIT_DATA are not used: CodeGraph's WebAssembly runtime reserves large virtual ranges and fails
under them (D-006; measured: RLIMIT_DATA 4 GiB fails, 8 GiB passes). Wall-clock caps per step: TRACES_INDEX_TIMEOUT_S.
The target repository's code, hooks, installs and tests are never run."""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
import traceback
from collections import Counter
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from traces.core.config import Settings, get_settings
from traces.evidence import components as comp
from traces.evidence.pipeline import CODEGRAPH_PIN, PKG, resolve_isolation, sandbox_cmd
from traces.evidence.store import Store, now, update_job
from traces.fixtures.task002.chain import REPO as T002_REPO
from traces.fixtures.task002.chain import REPO_SHA as T002_SHA
from traces.ingest.errors import IngestError
from traces.ingest.fetch import ensure_pinned_checkout, local_clone
from traces.ingest.urls import RepoRef

SECRET_MARKERS = ("TOKEN", "SECRET", "PASSWORD", "API_KEY", "CREDENTIAL")
SECRET_PREFIXES = ("GH_", "GITHUB_", "AWS_", "OPENAI", "ANTHROPIC", "XAI")


class IndexFailure(Exception):
    """A safe, user-visible job failure with a stable code (stored as job.error_code)."""

    def __init__(self, code: str, message: str, detail: dict[str, Any] | None = None):
        super().__init__(f"{code}: {message}")
        self.code, self.message, self.detail = code, message, detail or {}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


def clean_env(env: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in env.items() if not (any(m in k.upper() for m in SECRET_MARKERS) or k.upper().startswith(SECRET_PREFIXES))}


def session_rss_kb(sid: int) -> int:
    """Sum VmRSS of every process whose session id is `sid` (the sandbox runs in its own session)."""
    total = 0
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            stat = open(f"/proc/{d}/stat").read()
            if int(stat[stat.rindex(")") + 2:].split()[3]) != sid:
                continue
            for line in open(f"/proc/{d}/status"):
                if line.startswith("VmRSS:"):
                    total += int(line.split()[1])
                    break
        except (OSError, ValueError, IndexError):
            continue
    return total


def run_watched(cmd: list[str], env: dict[str, str], log_path: Path, *, timeout_s: int, max_rss_mb: int, step: str,
                cwd: Path | None = None) -> int:
    """Run `cmd` in its own session with a wall-clock cap and an RSS cap over the whole process tree."""
    with open(log_path, "ab") as log:
        log.write(f"\n[{now()}] $ {' '.join(cmd)}\n".encode())
        log.flush()
        p = subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, cwd=cwd, start_new_session=True)
        t0, peak, why = time.monotonic(), 0, None
        while p.poll() is None:
            time.sleep(0.25)
            rss = session_rss_kb(p.pid)
            peak = max(peak, rss)
            if time.monotonic() - t0 > timeout_s:
                why = "timeout"
            elif rss > max_rss_mb * 1024:
                why = "memory"
            if why:
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                p.wait()
                break
        log.write(f"[exit={p.returncode} wall_s={time.monotonic() - t0:.1f} peak_rss_mb={peak // 1024}]\n".encode())
    if why == "timeout":
        raise IndexFailure("index_timeout", f"{step} exceeded its {timeout_s} s limit", {"step": step})
    if why == "memory":
        raise IndexFailure("memory_limit", f"{step} exceeded the {max_rss_mb} MiB memory limit", {"step": step, "peak_rss_mb": peak // 1024})
    return int(p.returncode)


class IndexRun:
    PHASE_PROGRESS = {"fetching": 0.05, "checking_out": 0.15, "indexing": 0.2, "adapting": 0.45, "validating": 0.55, "storing": 0.8,
                      "history": 0.9}

    def __init__(self, st: Store, job_id: str, ref: RepoRef, sha: str, s: Settings | None = None,
                 history_run: Callable[..., Any] | None | str = "auto"):
        self.st, self.job_id, self.ref, self.sha = st, job_id, ref, sha
        self.s = s or get_settings()
        self.repo_id = ref.cache_key
        self.sid = f"{self.repo_id}@{sha}"
        self.run_id = f"idx-{job_id}"
        self.run = self.s.runs_dir / self.run_id
        self.history_run = history_run
        self.timeout_s = _env_int("TRACES_INDEX_TIMEOUT_S", 1800)
        self.max_rss_mb = _env_int("TRACES_MAX_RSS_MB", 6144)
        self.result: dict[str, Any] = {"run_id": self.run_id, "repo": ref.slug, "sha": sha}

    # ------------------------------------------------------------------ job bookkeeping
    def phase(self, phase: str, message: str) -> None:
        update_job(self.st, self.job_id, phase=phase, progress=self.PHASE_PROGRESS[phase], message=message)

    def event(self, message: str, level: str = "info") -> None:
        update_job(self.st, self.job_id, message=message, level=level)

    def sandbox(self, cmd: list[str], log: str, step: str, extra: dict[str, str] | None = None) -> int:
        full, env = sandbox_cmd(self.s, self.iso, cmd, self.run)
        env = clean_env({**env, **(extra or {})})
        env["PYTHONPATH"] = str(PKG.parent)
        return run_watched(full, env, self.run / log, timeout_s=self.timeout_s, max_rss_mb=self.max_rss_mb, step=step)

    # ------------------------------------------------------------------ steps
    def execute(self) -> dict[str, Any]:
        started = now()
        prev = self.st.get_snapshot(self.sid)
        was_ready = bool(prev and prev["state"] == "ready")
        update_job(self.st, self.job_id, state="running", phase="fetching", progress=0.01, message=f"indexing {self.ref.slug}@{self.sha[:12]}")
        if not was_ready:
            self.st.set_snapshot_state(self.sid, "indexing")
        try:
            self._steps()
        except BaseException as e:
            code, msg, detail = self._failure(e)
            self.result.update(error={"code": code, "message": msg, "detail": detail})
            if not was_ready:
                self.st.set_snapshot_state(self.sid, "failed")
            update_job(self.st, self.job_id, state="failed", phase="failed", message=msg, error_code=code, error_detail=msg, level="error")
            self._record_run(started)
            if not isinstance(e, Exception):
                raise
            return self.result
        update_job(self.st, self.job_id, state="succeeded", phase="done", progress=1.0, message="index complete")
        self._record_run(started)
        return self.result

    def _failure(self, e: BaseException) -> tuple[str, str, dict[str, Any]]:
        if isinstance(e, IngestError):
            return e.code, e.message, dict(e.detail or {})
        if isinstance(e, IndexFailure):
            return e.code, e.message, e.detail
        tb = traceback.format_exception_only(type(e), e)[-1].strip()[:300]
        (self.run / "internal_error.txt").write_text(traceback.format_exc()) if self.run.exists() else None
        return "internal_error", f"index failed unexpectedly: {tb}", {}

    def _record_run(self, started: str) -> None:
        try:
            rel = str(self.run.relative_to(self.s.data_dir))
        except ValueError:
            rel = str(self.run)
        try:
            self.st.add_run(self.run_id, self.sid, "evidence", rel, self.result, started)
        except Exception:  # noqa: BLE001  bookkeeping must never mask the job outcome
            pass
        if self.run.exists():
            (self.run / "index_result.json").write_text(json.dumps(self.result, indent=1, default=str))

    def _steps(self) -> None:
        s = self.s
        # fetching
        self.phase("fetching", f"fetching {self.ref.slug} (public, no hooks, no LFS, capped)")
        source = ensure_pinned_checkout(self.ref, self.sha, s.targets_dir / self.ref.cache_key / self.sha / "source")
        # checking_out
        self.phase("checking_out", "creating a throwaway working copy")
        if self.run.exists():
            shutil.rmtree(self.run)
        self.run.mkdir(parents=True)
        real = local_clone(source, self.run / "real", self.sha)
        self.iso = resolve_isolation(s)
        if self.iso == "none":
            self.event("isolation fallback: no network namespace available (TRACES_ISOLATION=none); network NOT isolated", "warning")
        self.result["isolation"] = self.iso
        # indexing
        self.phase("indexing", "CodeGraph 1.6.2 in the sandbox (no network)")
        if not s.codegraph_bin.exists():
            raise IndexFailure("toolchain_missing", f"CodeGraph is not installed in {s.toolchain_dir} (run: make toolchain)")
        rc = self.sandbox(["bash", str(s.workers_dir / "index_with_ns.sh"), str(real), str(self.run / "netprobe_index.log"),
                           str(self.run / "index_real.log")], "worker.log", "indexing")
        db = real / ".codegraph" / "codegraph.db"
        if rc != 0 or not db.exists():
            raise IndexFailure("extract_failed", "CodeGraph indexing failed", {"exit": rc, "log_tail": _tail(self.run / "index_real.log")})
        # adapting: probe + adapter in one sandbox invocation
        self.phase("adapting", "adapter (fail-closed) with the isolation probe")
        manifest = self._manifest(real, db)
        inner = f"{sys.executable} -m traces.adapter.codegraph --manifest {manifest}"
        if self.iso == "unshare":
            inner = f"bash {s.workers_dir / 'probe_inside.sh'} {self.run / 'netprobe.log'}; {inner}"
        outer_ns = os.readlink("/proc/self/ns/net")
        rc = self.sandbox(["env", f"OUTER_NS={outer_ns}", "CONTROL_E=skipped", "bash", "-c", inner], "worker.log", "adapting")
        adapter_out = self.run / "adapter" / "out"
        errs = adapter_out / "errors.json"
        if rc != 0 or not (adapter_out / "records.jsonl").exists():
            detail = json.loads(errs.read_text()) if errs.exists() else {"log_tail": _tail(self.run / "worker.log")}
            raise IndexFailure("adapter_failed", "the CodeGraph adapter refused the index (fail closed)", {"adapter": detail})
        # validating
        fixture = self.ref.slug.lower() == T002_REPO.lower() and self.sha == T002_SHA
        self.phase("validating", "independent validators" + (" + Task 002 regression fixture" if fixture else ""))
        vd = self.run / "v1"
        vd.mkdir()
        (vd / "manifest.json").write_text(json.dumps({"run_id": self.run_id}))
        py = sys.executable
        vcmd = [py, "-m", "traces.validators.orchestrator", "--run-dir", str(vd), "--records", str(adapter_out / "records.jsonl"),
                "--src", str(real), "--sha", self.sha, "--ts-module", str(s.ts_module), "--node", s.node]
        if fixture:
            vi = self.run / "validator_inputs"
            vi.mkdir()
            fx = self.run / "fixtures" / "chain_create_item.json"
            fx.parent.mkdir()
            inner = (f"{py} -m traces.fixtures.task002.chain --src {real} --fixture-out {fx} --injected-out {vi / 'injected.jsonl'} "
                     f"--run-id {self.run_id} --spotcheck-out {self.run / 'fixture_spotcheck.txt'} && " + " ".join(
                         [*vcmd, "--fixture", str(fx), "--injected", str(vi / "injected.jsonl")]))
            rc = self.sandbox(["bash", "-c", inner], "worker.log", "validating")
        else:
            rc = self.sandbox([*vcmd, "--no-fixture"], "worker.log", "validating")
        ev = vd / "validation" / "evidence.jsonl"
        if rc != 0 or not ev.exists():
            raise IndexFailure("validation_failed", "validators failed", {"exit": rc, "log_tail": _tail(self.run / "worker.log")})
        self.result["fixture"] = "task002" if fixture else None
        # storing
        self.phase("storing", "migrating to traces-evidence/0.4 and storing")
        self.st.delete_claims(self.sid)
        n = self.st.put_claims(self.sid, _jsonl(ev))
        facts = comp.snapshot_facts(source, self.sha)
        self.st.put_components(self.sid, facts.components)
        stats = self._stats(n, facts)
        rep = adapter_out / "report.json"
        adapter_summary = json.loads(rep.read_text()) if rep.exists() else {}
        extractor = {"codegraph": CODEGRAPH_PIN["version"], "codegraph_integrity": CODEGRAPH_PIN["npm_integrity"], "typescript": "6.0.3",
                     "python": sys.version.split()[0], "isolation": self.iso, "run_id": self.run_id,
                     "adapter_warnings": adapter_summary.get("warnings", []), "adapter_checks_passed": adapter_summary.get("checks_passed")}
        self.st.finish_snapshot(self.sid, extractor=extractor, languages=facts.languages, frameworks=facts.frameworks,
                                generated_paths=facts.generated_paths, stats=stats)
        self.result.update(stats=stats)
        # history
        self.phase("history", "history (native Git)")
        stats["history"] = self._history(source, facts)
        self.st.update_snapshot_stats(self.sid, stats)
        self.result.update(stats=stats)
        # cleanup: the throwaway working copy and its CodeGraph index (the cache checkout stays for source views)
        shutil.rmtree(real, ignore_errors=True)

    def _manifest(self, real: Path, db: Path) -> Path:
        d = self.run / "adapter"
        d.mkdir(parents=True, exist_ok=True)
        m = {"run_id": self.run_id, "repo": self.ref.slug, "repo_sha": self.sha, "checkout_path": str(real), "index_path": str(db),
             "codegraph": dict(CODEGRAPH_PIN), "wrapper": {"path": "workers/sandbox.sh", "sha256": _sha256(self.s.workers_dir / "sandbox.sh")},
             "env": {"telemetry_disabled": True, "isolation": self.iso, "netprobe_log": str(self.run / "netprobe.log")},
             "adapter_out": str(d / "out"), "package_dir": str(self.s.codegraph_package_dir), "lockfile": str(self.s.lockfile),
             "registry_record": str(self.s.registry_record)}
        p = d / "manifest.json"
        p.write_text(json.dumps(m, indent=1))
        return p

    def _stats(self, n: int, facts: comp.SnapshotFacts) -> dict[str, Any]:
        rows = self.st.db.execute("SELECT originator, claim_kind, status, injected, count(*) FROM claims WHERE snapshot_id=? "
                                  "GROUP BY originator, claim_kind, status, injected", (self.sid,)).fetchall()
        by_status: Counter[str] = Counter()
        edges: Counter[str] = Counter()
        by_kind: Counter[str] = Counter()
        injected: Counter[str] = Counter()
        for orig, ck, status, inj, c in rows:
            by_status[status] += c
            by_kind[ck] += c
            if orig == "codegraph" and ck == "relationship":
                edges[status] += c
            if inj:
                injected[status] += c
        return {"records": n, "by_status": dict(by_status), "by_claim_kind": dict(by_kind),
                "codegraph_edges": {"total": sum(edges.values()), **dict(edges)}, "injected": dict(injected),
                "files": len(facts.files), "components": len(facts.components), "sources": facts.sources}

    def _history(self, source: Path, facts: comp.SnapshotFacts) -> dict[str, Any]:
        fn = history_entry_point() if self.history_run == "auto" else self.history_run
        if not callable(fn):
            return self._history_skipped("traces.history.runner.run is not available in this build (hook H1)")
        from traces.evidence.migrate import CURRENT
        from traces.evidence.types import EvidenceSet
        from traces.history.config import HistoryConfig
        from traces.history.interface import HistoryRepoRef

        cmap = comp.component_map(self.sha, facts.components)
        static = [r for r in self.st.iter_claims(self.sid) if r.get("evidence_scope") == "static"]
        evsets = {self.sha: EvidenceSet(repo=self.ref.slug, sha=self.sha, schema_version=CURRENT, records=static)}
        try:
            res = fn(HistoryRepoRef(path=source, repo=self.ref.slug, sha=self.sha), HistoryConfig(), components=cmap,
                     evidence_sets=evsets, cache_dir=self.s.cache_dir / "history" / self.ref.cache_key, max_milestones=8,
                     run_id=self.run_id)
        except NotImplementedError as e:
            return self._history_skipped(f"history runner not implemented yet: {str(e)[:160]}")
        except Exception as e:  # noqa: BLE001  history failure must not discard the stored static evidence
            code = getattr(e, "code", None) or type(e).__name__
            msg = f"history failed ({code}): {str(e)[:200]}"
            self.event(msg, "warning")
            return {"state": "failed", "code": code, "reason": msg}
        recs = list(res.records)
        self.st.delete_claims(self.sid, scopes=("history", "documented"))
        k = self.st.put_claims(self.sid, recs)
        report = dict(getattr(res, "report", {}) or {})
        complete = getattr(res, "complete", report.get("complete", True))
        if complete is False:
            why = report.get("incomplete_reason") or report.get("budget") or "history budget exhausted"
            self.event(f"history completed with warnings (partial result): {str(why)[:200]}", "warning")
            return {"state": "completed_with_warnings", "records": k, "complete": False, "reason": str(why)[:300]}
        return {"state": "done", "records": k, "complete": True}

    def _history_skipped(self, reason: str) -> dict[str, Any]:
        self.event(f"history skipped: {reason}", "warning")
        return {"state": "skipped", "reason": reason}


def history_entry_point() -> Callable[..., Any] | None:
    """Hook H1 call site: traces.history.runner.run(repo, config, *, budget=None, components=None, evidence_sets=None,
    pr_provider=None, cache_dir=None, max_milestones=8, run_id=None, at=None) -> HistoryResult (history.md 8.11, frozen).
    Absent module or a stub raising NotImplementedError: the history step is recorded as skipped with the reason."""
    try:
        from importlib import import_module

        return getattr(import_module("traces.history.runner"), "run", None)
    except Exception:  # noqa: BLE001  a missing or broken history import must not fail the static index
        return None


def _tail(p: Path, n: int = 1500) -> str:
    try:
        return p.read_text(errors="replace")[-n:]
    except OSError:
        return ""


def _sha256(p: Path) -> str:
    import hashlib

    return hashlib.sha256(p.read_bytes()).hexdigest()


def _jsonl(p: Path) -> Iterator[dict[str, Any]]:
    with open(p) as f:
        for line in f:
            if line.strip():
                yield json.loads(line)
