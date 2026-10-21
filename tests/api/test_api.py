"""API contract tests against an in-memory store with synthetic 0.4 records (no third-party content)."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.unit.test_schema_v04 import cochange, commit_modifies
from traces.api.app import app, get_store, openapi_json
from traces.evidence.store import JobTransitionError, Store, create_job, update_job

ROOT = Path(__file__).resolve().parents[2]
SHA = "b1125d8839482cb7bbae603ddc6d0081bf87532e"
RID = "github.com__octo__demo"
BASE = f"/api/v1/repos/{RID}/snapshots/{SHA}"


@pytest.fixture()
def st() -> Store:
    s = Store(":memory:")
    s.upsert_repo(RID, "github.com", "octo", "demo", "https://github.com/octo/demo")
    sid = s.upsert_snapshot(RID, SHA, "ready")
    a, b = commit_modifies(), cochange()
    b["claim_id"] = "c_" + "6" * 64
    rej = copy.deepcopy(a)
    rej.update(claim_id="c_" + "7" * 64, status="rejected", label="rejected")
    s.put_claims(sid, [a, b, rej])
    return s


@pytest.fixture()
def client(st: Store):
    app.dependency_overrides[get_store] = lambda: st
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health_and_meta(client):
    h = client.get("/api/v1/health").json()
    assert h["status"] == "ok" and h["store_migration"] >= 1
    m = client.get("/api/v1/meta").json()
    assert m["evidence_schema"] == "traces-evidence/0.4" and m["capabilities"]["graph"] is False


@pytest.mark.parametrize("url", ["http://github.com/a/b", "https://gitlab.com/a/b", "https://github.com/a", "https://github.com/a/b/../c",
                                 "git@github.com:a/b.git", "https://github.com/a/.git", "https://github.com/a/b c"])
def test_register_rejects_bad_urls(client, url):
    r = client.post("/api/v1/repos", json={"url": url})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_repo_url"


def test_register_and_list(client):
    r = client.post("/api/v1/repos", json={"url": "https://github.com/Octo/Other.git"})
    assert r.status_code == 201 and r.json()["id"] == "github.com__octo__other"
    assert {x["id"] for x in client.get("/api/v1/repos").json()} == {RID, "github.com__octo__other"}
    assert client.get(f"/api/v1/repos/{RID}/snapshots").json()[0]["sha"] == SHA


def test_snapshot_errors(client):
    assert client.get(f"/api/v1/repos/{RID}/snapshots/abc").json()["error"]["code"] == "invalid_sha"
    assert client.get(f"/api/v1/repos/{RID}/snapshots/{'0' * 40}").status_code == 404
    assert client.get("/api/v1/repos/nope").status_code == 404


def test_claims_hide_rejected_by_default(client):
    p = client.get(f"{BASE}/claims").json()
    assert p["total"] == 2 and p["hidden_counts"] == {"rejected": 1}
    assert all(i["status"] != "rejected" for i in p["items"])
    p = client.get(f"{BASE}/claims", params={"include_rejected": "true"}).json()
    assert p["total"] == 3 and p["hidden_counts"] == {}
    assert {i["label"] for i in p["items"] if i["status"] == "rejected"} == {"rejected"}


def test_claim_by_id_and_export(client):
    cid = "c_" + "5" * 64
    r = client.get(f"{BASE}/claims/{cid}")
    assert r.status_code == 200 and r.json()["claim_id"] == cid
    assert client.get(f"{BASE}/claims/c_nope").status_code == 404
    e = client.get(f"{BASE}/export")
    assert e.headers["content-type"].startswith("application/x-ndjson")
    assert [json.loads(x)["claim_id"] for x in e.text.splitlines()] == sorted(["c_" + d * 64 for d in "567"])


NOT_IMPLEMENTED = [
    ("get", f"/api/v1/repos/{RID}/head", None), ("post", f"/api/v1/repos/{RID}/index-jobs", {}),
    ("get", f"{BASE}/overview", None), ("get", f"{BASE}/components", None), ("get", f"{BASE}/routes", None),
    ("get", f"{BASE}/graph", None), ("get", f"{BASE}/source?path=README.md", None), ("get", f"{BASE}/trace?from=x", None),
    ("get", f"{BASE}/history/timeline", None), ("get", f"{BASE}/history/lifecycle?path=a", None), ("get", f"{BASE}/history/hotspots", None),
    ("get", f"{BASE}/history/cochange", None), ("get", f"{BASE}/history/milestones", None), ("get", f"{BASE}/history/rationale", None),
    ("get", f"/api/v1/repos/{RID}/compare?base={SHA}&head={SHA}", None),
    ("post", f"{BASE}/explain", {"question": "what is this"}), ("post", f"{BASE}/chat/bundle", {"question": "q", "mode": "prepare_bundle"}),
]


@pytest.mark.parametrize("method,path,body", NOT_IMPLEMENTED)
def test_stubs_return_explicit_501(client, method, path, body):
    r = client.request(method.upper(), path, json=body)
    assert r.status_code == 501
    e = r.json()["error"]
    assert e["code"] == "not_implemented" and e["owner"] and e["milestone"]


def test_explain_refuses_provider_keys(client):
    r = client.post(f"{BASE}/explain", json={"question": "q", "api_key": "sk-test"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"


def test_job_poll_etag(client, st):
    create_job(st, "j1", RID, "index")
    r = client.get("/api/v1/jobs/j1")
    assert r.status_code == 200 and r.headers["etag"] == '"1"' and r.json()["state"] == "queued"
    assert client.get("/api/v1/jobs/j1", headers={"If-None-Match": '"1"'}).status_code == 304
    update_job(st, "j1", state="running", phase="fetching", progress=0.1, message="fetching")
    r = client.get("/api/v1/jobs/j1", headers={"If-None-Match": '"1"'})
    assert r.status_code == 200 and r.headers["etag"] == '"2"' and len(r.json()["events"]) == 2
    assert client.get("/api/v1/jobs/none").status_code == 404


def test_job_state_machine(st):
    create_job(st, "j2", RID, "index")
    with pytest.raises(JobTransitionError):
        update_job(st, "j2", state="succeeded")
    update_job(st, "j2", state="running", progress=0.5)
    with pytest.raises(JobTransitionError):
        update_job(st, "j2", progress=0.4)
    update_job(st, "j2", state="failed", phase="failed", error_code="E_INDEX", error_detail="boom", level="error")
    with pytest.raises(JobTransitionError):
        update_job(st, "j2", state="running")


def test_openapi_committed_copy_is_current():
    committed = (ROOT / "docs/contracts/openapi.json").read_text()
    assert committed == openapi_json(), "regenerate: uv run traces openapi --out docs/contracts/openapi.json"
