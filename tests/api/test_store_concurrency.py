"""Regression for the shared-connection bug: `traces serve` returned occasional 500s (sqlite3.InterfaceError in
Store.get_repo) because one SQLite connection was shared across the API's worker threads. These tests drive a real
uvicorn server over a file-backed store with about 200 parallel requests and require zero 5xx responses."""
from __future__ import annotations

import copy
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest
import uvicorn

from tests.unit.test_schema_v04 import cochange, commit_modifies
from traces.api.app import app, get_store
from traces.evidence.store import Store, create_job, update_job

SHA = "b1125d8839482cb7bbae603ddc6d0081bf87532e"
RID = "github.com__octo__demo"
BASE = f"/api/v1/repos/{RID}/snapshots/{SHA}"


def _seed(st: Store) -> None:
    st.upsert_repo(RID, "github.com", "octo", "demo", "https://github.com/octo/demo")
    sid = st.upsert_snapshot(RID, SHA, "ready")
    a, b = commit_modifies(), cochange()
    b["claim_id"] = "c_" + "6" * 64
    rej = copy.deepcopy(a)
    rej.update(claim_id="c_" + "7" * 64, status="rejected", label="rejected")
    st.put_claims(sid, [a, b, rej])


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture()
def server(tmp_path: Path):
    st = Store(tmp_path / "traces.sqlite3")
    _seed(st)
    create_job(st, "jc", RID, "index")
    app.dependency_overrides[get_store] = lambda: st
    port = _free_port()
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", workers=1))
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    for _ in range(200):
        if srv.started:
            break
        time.sleep(0.025)
    assert srv.started, "uvicorn did not start"
    yield f"http://127.0.0.1:{port}", st
    srv.should_exit = True
    t.join(timeout=10)
    app.dependency_overrides.clear()
    st.close()


def test_parallel_requests_never_5xx(server):
    url, st = server
    paths = [f"/api/v1/repos/{RID}", "/api/v1/repos", f"{BASE}/claims", f"{BASE}/claims?include_rejected=true",
             f"{BASE}/claims/c_{'5' * 64}", f"/api/v1/repos/{RID}/snapshots", "/api/v1/jobs/jc"]
    stop = threading.Event()

    def writer() -> None:  # a concurrent writer, like the index worker updating its job
        p = 0.0
        while not stop.is_set() and p < 0.99:
            p = round(p + 0.01, 2)
            update_job(st, "jc", state="running", phase="indexing", progress=p, message=f"p={p}")

    w = threading.Thread(target=writer)
    w.start()
    with httpx.Client(base_url=url, timeout=30) as c, ThreadPoolExecutor(max_workers=32) as ex:
        statuses = list(ex.map(lambda i: c.get(paths[i % len(paths)]).status_code, range(210)))
    stop.set()
    w.join()
    assert len(statuses) == 210
    assert [s for s in statuses if s >= 500] == []
    assert set(statuses) == {200}


def test_store_threads_share_one_logical_db(tmp_path: Path):
    st = Store(tmp_path / "t.sqlite3")
    _seed(st)
    errors: list[BaseException] = []

    def work(i: int) -> None:
        try:
            for _ in range(25):
                assert st.get_repo(RID) is not None
                assert sum(st.status_counts(f"{RID}@{SHA}").values()) == 3
                st.upsert_repo(f"github.com__octo__r{i}", "github.com", "octo", f"r{i}", f"https://github.com/octo/r{i}")
        except BaseException as e:  # noqa: BLE001
            errors.append(e)

    ts = [threading.Thread(target=work, args=(i,)) for i in range(16)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert errors == []
    assert len(st.list_repos()) == 17
    st.close()


def test_memory_store_visible_across_threads():
    st = Store(":memory:")
    _seed(st)
    out: list[object] = []
    t = threading.Thread(target=lambda: out.append(st.get_repo(RID)))
    t.start()
    t.join()
    assert out and out[0] is not None
    st.close()
