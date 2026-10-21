"""INDEX API: POST index-jobs, job polling with ETag through the in-process runner, duplicate and conflict handling,
safe failure and recovery of interrupted jobs. The pipeline is a stub here; the real one is exercised in
tests/unit/test_index_worker.py (synthetic repo) and tests/api/test_index_baseline.py (Task 002 snapshot)."""
from __future__ import annotations

import threading
import time

import pytest
from fastapi.testclient import TestClient

from tests.api.test_api import HEAD_SHA, FakeProbe
from traces.api.app import app, get_head_probe, get_index_runner, get_store
from traces.evidence.jobs import IndexJobRunner
from traces.evidence.store import Store, create_job, update_job

RID = "github.com__octo__idx"


def stub_pipeline(gate: threading.Event | None = None, fail: BaseException | None = None):
    def run(st: Store, jid: str, ref, sha: str) -> None:
        update_job(st, jid, state="running", phase="fetching", progress=0.05, message="fetching")
        if gate is not None:
            gate.wait(10)
        if fail is not None:
            raise fail
        for i, ph in enumerate(("checking_out", "indexing", "adapting", "validating", "storing", "history")):
            update_job(st, jid, phase=ph, progress=0.1 + 0.1 * i, message=ph)
        st.set_snapshot_state(f"{ref.cache_key}@{sha}", "ready")
        update_job(st, jid, state="succeeded", phase="done", progress=1.0, message="index complete")
    return run


@pytest.fixture()
def env(tmp_path):
    st = Store(tmp_path / "t.sqlite3")
    probe = FakeProbe()
    holder: dict[str, IndexJobRunner] = {"r": IndexJobRunner(st, run_fn=stub_pipeline())}
    app.dependency_overrides[get_store] = lambda: st
    app.dependency_overrides[get_head_probe] = lambda: probe
    app.dependency_overrides[get_index_runner] = lambda: holder["r"]
    c = TestClient(app)
    assert c.post("/api/v1/repos", json={"url": "https://github.com/octo/idx"}).status_code == 201
    yield c, st, holder
    app.dependency_overrides.clear()
    holder["r"].shutdown()
    st.close()


def poll_until_done(c, jid, timeout=10.0):
    etag, seen = None, []
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = c.get(f"/api/v1/jobs/{jid}", headers={"If-None-Match": etag} if etag else {})
        if r.status_code == 200:
            etag = r.headers["etag"]
            j = r.json()
            seen.append(j["phase"])
            if j["state"] in ("succeeded", "failed", "cancelled"):
                return j, seen
        else:
            assert r.status_code == 304
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_index_job_runs_to_success(env):
    c, st, h = env
    r = c.post(f"/api/v1/repos/{RID}/index-jobs", json={})
    assert r.status_code == 202 and r.headers["location"] == f"/api/v1/jobs/{r.json()['id']}"
    j = r.json()
    assert j["snapshot_id"] == f"{RID}@{HEAD_SHA}" and j["kind"] == "index"
    done, _ = poll_until_done(c, j["id"])
    assert done["state"] == "succeeded" and done["progress"] == 1.0 and done["phase"] == "done"
    phases = [e["phase"] for e in done["events"]]
    assert phases.index("fetching") < phases.index("indexing") < phases.index("storing") < phases.index("done")
    assert c.get(f"/api/v1/repos/{RID}/snapshots/{HEAD_SHA}").json()["state"] == "ready"
    assert c.get(f"/api/v1/jobs/{j['id']}", headers={"If-None-Match": f'"{done["version"]}"'}).status_code == 304
    # ready snapshot: a plain index is a conflict, reindex makes a new job
    r = c.post(f"/api/v1/repos/{RID}/index-jobs", json={})
    assert r.status_code == 409 and r.json()["error"]["code"] == "already_indexed"
    r = c.post(f"/api/v1/repos/{RID}/index-jobs", json={"reindex": True})
    assert r.status_code == 202 and r.json()["kind"] == "reindex" and r.json()["id"] != j["id"]
    assert poll_until_done(c, r.json()["id"])[0]["state"] == "succeeded"


def test_active_job_is_not_duplicated(env):
    c, st, h = env
    gate = threading.Event()
    h["r"] = IndexJobRunner(st, run_fn=stub_pipeline(gate))
    a = c.post(f"/api/v1/repos/{RID}/index-jobs", json={"sha": "b" * 40}).json()
    b = c.post(f"/api/v1/repos/{RID}/index-jobs", json={"sha": "b" * 40}).json()
    assert a["id"] == b["id"]
    gate.set()
    assert poll_until_done(c, a["id"])[0]["state"] == "succeeded"


def test_pipeline_crash_fails_job_safely(env):
    c, st, h = env
    h["r"] = IndexJobRunner(st, run_fn=stub_pipeline(fail=RuntimeError("boom /secret/path")))
    j = c.post(f"/api/v1/repos/{RID}/index-jobs", json={"sha": "c" * 40}).json()
    done, _ = poll_until_done(c, j["id"])
    assert done["state"] == "failed" and done["error"]["code"] == "internal_error"
    assert "/secret/path" not in done["error"]["message"]


def test_bad_requests(env):
    c, st, h = env
    r = c.post(f"/api/v1/repos/{RID}/index-jobs", json={"sha": "nothex"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_sha"
    assert c.post("/api/v1/repos/nope/index-jobs", json={}).status_code == 404
    r = c.post(f"/api/v1/repos/{RID}/index-jobs", json={"sha": "d" * 40, "extra": 1})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"


def test_interrupted_jobs_are_failed_on_startup(tmp_path):
    st = Store(tmp_path / "r.sqlite3")
    st.upsert_repo(RID, "github.com", "octo", "idx", "https://github.com/octo/idx")
    sid = st.ensure_snapshot(RID, "e" * 40)
    st.set_snapshot_state(sid, "indexing")
    create_job(st, "old1", RID, "index", sid)
    update_job(st, "old1", state="running", phase="indexing", progress=0.3)
    create_job(st, "old2", RID, "index", sid)
    r = IndexJobRunner(st, run_fn=stub_pipeline())
    assert sorted(r.recovered) == ["old1", "old2"]
    from traces.evidence.store import get_job
    assert {get_job(st, j)["error_code"] for j in ("old1", "old2")} == {"interrupted"}
    assert st.get_snapshot(sid)["state"] == "failed"
    r.shutdown()
