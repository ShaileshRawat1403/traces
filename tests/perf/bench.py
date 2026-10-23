"""Local performance baseline: index wall time per phase, then API latency p50/p95 on the key read endpoints.

No network: both repositories are indexed from local full-history clones (the pinned fsft cache and any
other local clone), the same way scripts/e2e_seed.py does. The API runs as a scratch `traces serve` on a
loopback port with its own data dir. Numbers are local to the machine that runs this; they are not CI results.

usage: uv run --frozen python tests/perf/bench.py OUT_DIR [--repo OWNER/NAME=PATH@SHA ...] [--runs 3] [--requests 100]
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FSFT_SHA = "b1125d8839482cb7bbae603ddc6d0081bf87532e"
FSFT = f"fastapi/full-stack-fastapi-template={ROOT}/.cache/targets/github.com__fastapi__full-stack-fastapi-template/{FSFT_SHA}/source@{FSFT_SHA}"


def index_once(data: Path, owner: str, name: str, src: Path, sha: str) -> dict:
    """Index one local clone into a fresh data dir in a child process; returns per-phase seconds."""
    code = f"""
import json, os, time
from dataclasses import dataclass
os.environ["TRACES_DATA_DIR"] = {str(data)!r}
os.environ.setdefault("TRACES_ISOLATION", "unshare")
from traces.core.config import get_settings
from traces.evidence.index import IndexRun
from traces.evidence.store import Store, create_job
from traces.ingest.urls import RepoRef

@dataclass(frozen=True)
class LocalRef(RepoRef):
    path: str = ""
    @property
    def clone_url(self):
        return self.path

marks = []
orig = IndexRun.phase
def phase(self, p, m):
    marks.append((p, time.monotonic()))
    return orig(self, p, m)
IndexRun.phase = phase
ref = LocalRef("github.com", {owner!r}, {name!r}, path={str(src)!r})
s = get_settings()
st = Store(s.db_path)
st.upsert_repo(ref.cache_key, ref.host, ref.owner, ref.name, "https://github.com/" + ref.slug)
st.ensure_snapshot(ref.cache_key, {sha!r})
create_job(st, "perf", ref.cache_key, "index", ref.cache_key + "@" + {sha!r})
t0 = time.monotonic()
res = IndexRun(st, "perf", ref, {sha!r}, s).execute()
t1 = time.monotonic()
st.close()
ph = {{}}
for i, (p, t) in enumerate(marks):
    ph[p] = round((marks[i + 1][1] if i + 1 < len(marks) else t1) - t, 2)
print(json.dumps({{"total_s": round(t1 - t0, 2), "phases_s": ph, "error": res.get("error"), "repo_id": ref.cache_key}}))
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True, cwd=ROOT)
    return json.loads(out.stdout.strip().splitlines()[-1])


def free_port() -> int:
    with socket.socket() as so:
        so.bind(("127.0.0.1", 0))
        return so.getsockname()[1]


def get(url: str, body: bytes | None = None) -> float:
    req = urllib.request.Request(url, data=body, headers={"content-type": "application/json"} if body else {})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=60) as r:
        r.read()
        if r.status >= 400:
            raise RuntimeError(f"{url} -> {r.status}")
    return (time.perf_counter() - t0) * 1000


def pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    k = max(0, min(len(xs) - 1, round(p / 100 * len(xs) + 0.5) - 1))
    return round(xs[k], 1)


@dataclass
class Target:
    owner: str
    name: str
    path: Path
    sha: str


def parse(spec: str) -> Target:
    slug, rest = spec.split("=", 1)
    path, sha = rest.rsplit("@", 1)
    owner, name = slug.split("/")
    return Target(owner, name, Path(path), sha)


def endpoints(repo_id: str, sha: str, fsft: bool) -> list[tuple[str, str, bytes | None]]:
    s = f"/api/v1/repos/{repo_id}/snapshots/{sha}"
    eps = [
        ("repos", "/api/v1/repos", None),
        ("overview", f"{s}/overview", None),
        ("components", f"{s}/components", None),
        ("graph", f"{s}/graph", None),
        ("claims page 1", f"{s}/claims?limit=50", None),
        ("history timeline", f"{s}/history/timeline?limit=50", None),
        ("history milestones", f"{s}/history/milestones", None),
        ("explain (no key)", f"{s}/explain", json.dumps({"question": "Where is the persistence path?"}).encode()),
    ]
    if fsft:
        eps += [
            ("trace create_item", f"{s}/trace?from=backend/app/api/routes/items.py::create_item", None),
            ("source items.py", f"{s}/source?path=backend/app/api/routes/items.py&start=60&end=66", None),
            ("history cochange crud.py", f"{s}/history/cochange?target=backend/app/crud.py", None),
        ]
    return eps


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--repo", action="append", default=[], help="OWNER/NAME=PATH@SHA (fsft is always included)")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--requests", type=int, default=100)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    targets = [parse(FSFT)] + [parse(r) for r in a.repo]
    env_info = {
        "when_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "machine": platform.platform(),
        "cpus": os.cpu_count(),
        "python": platform.python_version(),
        "git_head": subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True
        ).stdout.strip(),
    }
    report: dict = {"env": env_info, "index": {}, "api": {}}
    keep: dict[str, Path] = {}
    for t in targets:
        runs = []
        for i in range(a.runs):
            d = Path(tempfile.mkdtemp(prefix="traces-perf-"))
            r = index_once(d, t.owner, t.name, t.path, t.sha)
            if r["error"]:
                raise SystemExit(f"index failed for {t.owner}/{t.name}: {r['error']}")
            runs.append(r)
            print(f"index {t.owner}/{t.name} run {i + 1}: {r['total_s']} s {r['phases_s']}", flush=True)
            if i == a.runs - 1:
                keep[r["repo_id"]] = d
            else:
                shutil.rmtree(d, ignore_errors=True)
        totals = [r["total_s"] for r in runs]
        report["index"][f"{t.owner}/{t.name}@{t.sha[:7]}"] = {
            "runs_s": totals,
            "median_s": statistics.median(totals),
            "phases_s_last_run": runs[-1]["phases_s"],
        }
    for t in targets:
        repo_id = f"github.com__{t.owner}__{t.name}"
        port = free_port()
        env = {**os.environ, "TRACES_DATA_DIR": str(keep[repo_id])}
        log = open(out / f"serve-{t.name}.log", "w")
        srv = subprocess.Popen(
            ["uv", "run", "--frozen", "traces", "serve", "--host", "127.0.0.1", "--port", str(port)],
            env=env,
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            base = f"http://127.0.0.1:{port}"
            for _ in range(100):
                try:
                    get(base + "/api/v1/health")
                    break
                except OSError:
                    time.sleep(0.2)
            res = {}
            for label, path, body in endpoints(repo_id, t.sha, t.name == "full-stack-fastapi-template"):
                for _ in range(3):
                    get(base + path, body)  # warm-up, not counted
                xs = [get(base + path, body) for _ in range(a.requests)]
                res[label] = {"p50_ms": pct(xs, 50), "p95_ms": pct(xs, 95), "max_ms": round(max(xs), 1), "n": len(xs)}
                print(f"api {t.name} {label}: p50 {res[label]['p50_ms']} ms, p95 {res[label]['p95_ms']} ms", flush=True)
            report["api"][f"{t.owner}/{t.name}@{t.sha[:7]}"] = res
        finally:
            srv.terminate()
            srv.wait(timeout=10)
            log.close()
    for d in keep.values():
        shutil.rmtree(d, ignore_errors=True)
    (out / "perf.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
