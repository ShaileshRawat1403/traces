"""INDEX acceptance on the Task 002 snapshot: the product index path (POST index-jobs -> worker -> store) reproduces the
baseline for fastapi/full-stack-fastapi-template@b1125d8: 4,642 CodeGraph edges = 4,538 verified + 36 observed +
59 unvalidated + 9 rejected, 12 rejected overall (the 3 injected negatives among them), and the same canonical
hashes as the baseline run. Uses the pinned cache checkout made by the baseline fixture (no network)."""
from __future__ import annotations

import json
import os
import time

import pytest
from fastapi.testclient import TestClient

from traces.api.app import app, get_index_runner, get_store
from traces.core.common import canonical_hash
from traces.evidence.jobs import IndexJobRunner
from traces.evidence.store import Store
from traces.fixtures.task002.chain import REPO_SHA

RID = "github.com__fastapi__full-stack-fastapi-template"


def _offline_ok() -> bool:
    """The baseline needs no network when a run is reused or the pinned target checkout is already cached (as in CI,
    which restores it from the actions cache). Otherwise it would clone from GitHub: a live check."""
    if os.environ.get("TRACES_NETWORK_TESTS") == "1" or os.environ.get("TRACES_BASELINE_RUN"):
        return True
    from traces.core.config import get_settings

    return (get_settings().targets_dir / RID / REPO_SHA / "source" / ".git").exists()


@pytest.mark.skipif(not _offline_ok(), reason="live GitHub checks need TRACES_NETWORK_TESTS=1 (the fsft target is not cached, "
                                              "so the baseline would clone it); or set TRACES_BASELINE_RUN")
def test_product_index_reproduces_task002(baseline_run, tmp_path, monkeypatch):
    monkeypatch.setenv("TRACES_DATA_DIR", str(tmp_path / "data"))
    st = Store(tmp_path / "data" / "traces.sqlite3")
    st.upsert_repo(RID, "github.com", "fastapi", "full-stack-fastapi-template", "https://github.com/fastapi/full-stack-fastapi-template")
    runner = IndexJobRunner(st)
    app.dependency_overrides[get_store] = lambda: st
    app.dependency_overrides[get_index_runner] = lambda: runner
    try:
        c = TestClient(app)
        j = c.post(f"/api/v1/repos/{RID}/index-jobs", json={"sha": REPO_SHA})
        assert j.status_code == 202, j.text
        jid = j.json()["id"]
        t0 = time.time()
        while time.time() - t0 < 900:
            job = c.get(f"/api/v1/jobs/{jid}").json()
            if job["state"] in ("succeeded", "failed"):
                break
            time.sleep(1)
        assert job["state"] == "succeeded", job
        snap = c.get(f"/api/v1/repos/{RID}/snapshots/{REPO_SHA}").json()
        e = snap["stats"]["codegraph_edges"]
        assert (e["total"], e["verified"], e["observed"], e["unvalidated"], e["rejected"]) == (4642, 4538, 36, 59, 9)
        assert snap["stats"]["by_status"]["rejected"] == 12 and snap["stats"]["injected"] == {"rejected": 3}
        assert snap["stats"]["history"]["state"] in ("skipped", "done", "failed")
        p = c.get(f"/api/v1/repos/{RID}/snapshots/{REPO_SHA}/claims", params={"status": "verified", "limit": 1}).json()
        assert p["hidden_counts"].get("rejected") == 12
        run = tmp_path / "data" / "runs" / f"idx-{jid}"
        mine = canonical_hash([json.loads(x) for x in open(run / "v1" / "validation" / "evidence.jsonl")])
        base = canonical_hash([json.loads(x) for x in open(baseline_run / "v1" / "validation" / "evidence.jsonl")])
        assert mine == base and mine.startswith("73db432b")
        adapter = canonical_hash([json.loads(x) for x in open(run / "adapter" / "out" / "records.jsonl")])
        assert adapter.startswith("45600280")
    finally:
        app.dependency_overrides.clear()
        runner.shutdown()
        st.close()
