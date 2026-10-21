"""In-process index job runner (D-020). Jobs run on a small thread pool (default one at a time, so indexes never
compete for memory); state lives in the store, so pollers see every change through GET /jobs/{id} (ETag = version).
Jobs left queued or running by a previous process are marked failed (`interrupted`) on startup: terminal states are
final and a reindex is a new job (CONTRACTS.md 3.2)."""
from __future__ import annotations

import os
import threading
import uuid
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from traces.evidence.store import Store, create_job, get_job, update_job
from traces.ingest.urls import RepoRef

RunFn = Callable[[Store, str, RepoRef, str], Any]


def _default_run(st: Store, job_id: str, ref: RepoRef, sha: str) -> Any:
    from traces.evidence.index import IndexRun

    return IndexRun(st, job_id, ref, sha).execute()


class IndexJobRunner:
    def __init__(self, st: Store, *, run_fn: RunFn | None = None, max_workers: int | None = None):
        self.st = st
        self.run_fn = run_fn or _default_run
        n = max_workers or int(os.environ.get("TRACES_INDEX_WORKERS", "1") or 1)
        self.ex = ThreadPoolExecutor(max_workers=max(1, n), thread_name_prefix="traces-index")
        self._lock = threading.Lock()
        self.futures: dict[str, Future[Any]] = {}
        self.recovered = self._recover()

    def _recover(self) -> list[str]:
        out = []
        for jid in self.st.unfinished_jobs():
            try:
                update_job(self.st, jid, state="failed", phase="failed", error_code="interrupted",
                           error_detail="the server stopped while this job was queued or running; start a new index job", level="error")
                j = get_job(self.st, jid) or {}
                if j.get("snapshot_id"):
                    s = self.st.get_snapshot(j["snapshot_id"])
                    if s and s["state"] == "indexing":
                        self.st.set_snapshot_state(j["snapshot_id"], "failed")
                out.append(jid)
            except Exception:  # noqa: BLE001
                continue
        return out

    def submit(self, ref: RepoRef, sha: str, kind: str) -> dict[str, Any]:
        """Create (or return the already active) job for repo@sha and schedule it."""
        repo_id = ref.cache_key
        with self._lock:
            sid = self.st.ensure_snapshot(repo_id, sha)
            active = self.st.active_job(sid)
            if active:
                return get_job(self.st, active["id"]) or {}
            jid = "j_" + uuid.uuid4().hex[:20]
            job = create_job(self.st, jid, repo_id, kind, sid)
            self.futures[jid] = self.ex.submit(self._run, jid, ref, sha)
        return job

    def _run(self, jid: str, ref: RepoRef, sha: str) -> None:
        try:
            self.run_fn(self.st, jid, ref, sha)
        except BaseException as e:  # noqa: BLE001  never leave a job non-terminal
            j = get_job(self.st, jid) or {}
            if j.get("state") in ("queued", "running"):
                update_job(self.st, jid, state="failed", phase="failed", error_code="internal_error",
                           error_detail=f"index failed unexpectedly: {type(e).__name__}", level="error")

    def wait(self, jid: str, timeout: float | None = None) -> None:
        f = self.futures.get(jid)
        if f is not None:
            f.result(timeout=timeout)

    def shutdown(self) -> None:
        self.ex.shutdown(wait=True)
