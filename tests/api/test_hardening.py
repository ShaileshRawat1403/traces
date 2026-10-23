"""Security and evidence-review fixes on the API: no input echo in 422s (F-3), accurate path refusals (F-2), unknown
SHA refused at registration, repo-level AI consent, injected-control markers, honest graph truncation and focus-scoped
hidden counts. In-memory store, fake ls-remote probe, no network."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.api.test_views import RID, SHA, _id, rec
from traces.api.app import app, get_head_probe, get_store, redact
from traces.evidence.store import Store
from traces.evidence.views import ViewError, safe_repo_path
from traces.ingest.remote import RemoteHead

BASE = f"/api/v1/repos/{RID}/snapshots/{SHA}"
HEAD = "a" * 40
KNOWN = "b" * 40


class Probe:
    def __init__(self) -> None:
        self.checked: list[str] = []

    def head(self, ref, *, max_age_s=None):
        return RemoteHead("main", HEAD, "2026-10-23T12:00:00+05:30")

    def commit_exists(self, ref, sha):
        self.checked.append(sha)
        return sha == KNOWN


def _sym(name: str) -> dict:
    f = name.split("::")[0]
    return {"entity": "symbol", "symbol": name, "file": f}


@pytest.fixture()
def st() -> Store:
    s = Store(":memory:")
    s.upsert_repo(RID, "github.com", "octo", "demo", "https://github.com/octo/demo")
    sid = s.upsert_snapshot(RID, SHA, "indexing")
    s.finish_snapshot(sid, extractor={}, languages={"Python": 3}, frameworks=[], generated_paths=[], stats={}, isolation="unshare")
    recs = [
        rec(claim_id=_id(1), **{"from": _sym("a.py::foo"), "to": _sym("b.py::bar")}),
        rec(claim_id=_id(2), **{"from": _sym("b.py::bar"), "to": _sym("c.py::baz")}),
        rec(claim_id=_id(3), **{"from": _sym("x.py::far"), "to": _sym("y.py::away")}),
        # injected negative control, rejected, touching foo
        rec(claim_id=_id(4), status="rejected", label="rejected", injected=True, statement="injected control",
            **{"from": _sym("a.py::foo"), "to": _sym("c.py::baz")}),
        # rejected edges far from foo
        rec(claim_id=_id(5), status="rejected", label="rejected", **{"from": _sym("x.py::far"), "to": _sym("z.py::other")}),
        rec(claim_id=_id(6), status="rejected", label="rejected", **{"from": _sym("y.py::away"), "to": _sym("z.py::other")}),
    ]
    s.put_claims(sid, recs)
    return s


@pytest.fixture()
def probe() -> Probe:
    return Probe()


@pytest.fixture()
def client(st: Store, probe: Probe):
    app.dependency_overrides[get_store] = lambda: st
    app.dependency_overrides[get_head_probe] = lambda: probe
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------- F-3: never echo input, redact sensitive names
@pytest.mark.parametrize("field", ["api_key", "openai_api_key", "authorization", "token", "client_secret"])
def test_validation_error_never_echoes_input(client, field):
    secret = "sk-test-SHOULD-NOT-APPEAR-123"
    r = client.post(f"{BASE}/explain", json={"question": "x", field: secret})
    assert r.status_code == 422 and secret not in r.text
    errs = r.json()["error"]["detail"]["errors"]
    assert errs and all(set(e) == {"loc", "msg", "type"} for e in errs)
    assert ["body", field] in [e["loc"] for e in errs]


def test_validation_error_does_not_echo_ordinary_values(client):
    r = client.post(f"{BASE}/explain", json={"question": "q" * 5000})
    assert r.status_code == 422 and "q" * 50 not in r.text
    r = client.post(f"{BASE}/explain", json={"question": ["not", "a", "string-unique-marker"]})
    assert r.status_code == 422 and "string-unique-marker" not in r.text


def test_redact_any_depth():
    got = redact({"a": 1, "API_Key": "s", "n": [{"x": {"refresh_token": "t", "ok": 2}}], "Authorization": "Bearer z",
                  "nested": {"client_secret": {"deep": "v"}}})
    assert got == {"a": 1, "API_Key": "[redacted]", "n": [{"x": {"refresh_token": "[redacted]", "ok": 2}}],
                   "Authorization": "[redacted]", "nested": {"client_secret": "[redacted]"}}


# ---------------------------------------------------------------- F-2: accurate path refusals
@pytest.mark.parametrize("path", ["-rf.py", "--output=x", "-c", "dir/-x.py", "a b.py", "..hidden.py", "./app/main.py"])
def test_safe_repo_path_accepts_legal_names(path):
    assert safe_repo_path(path) == path.removeprefix("./")


@pytest.mark.parametrize("path,msg", [
    ("", "path is required"),
    ("a\x00b", "NUL or line-break"), ("a\nb", "NUL or line-break"),
    ("a\\b", "forward slashes"),
    ("/etc/passwd", "relative to the repository root"), ("~/.ssh/id_rsa", "relative to the repository root"),
    ("../x", "'..' components"), ("a/../../x", "'..' components"),
    (".", "must name a file"),
])
def test_safe_repo_path_messages_name_the_problem(path, msg):
    with pytest.raises(ViewError) as e:
        safe_repo_path(path)
    assert e.value.status == 422 and msg in e.value.message


# ---------------------------------------------------------------- unknown SHA at registration
def test_register_unknown_sha_is_refused_and_nothing_is_stored(client, st, probe):
    r = client.post("/api/v1/repos", json={"url": "https://github.com/octo/fresh", "sha": "c" * 40})
    assert r.status_code == 422 and r.json()["error"]["code"] == "sha_not_found", r.text
    assert st.get_repo("github.com__octo__fresh") is None and probe.checked == ["c" * 40]


def test_register_known_sha_and_head_skip_or_pass_the_check(client, probe):
    assert client.post("/api/v1/repos", json={"url": "https://github.com/octo/fresh", "sha": KNOWN}).status_code == 201
    assert client.post("/api/v1/repos", json={"url": "https://github.com/octo/fresh", "sha": HEAD}).status_code == 201
    assert client.post("/api/v1/repos", json={"url": "https://github.com/octo/fresh"}).status_code == 201
    assert probe.checked == [KNOWN]  # HEAD is known from ls-remote; no extra fetch


# ---------------------------------------------------------------- repo-level AI consent (D-027)
def test_ai_consent_grant_and_revoke(client):
    r = client.get(f"/api/v1/repos/{RID}").json()
    assert r["external_ai_consent"] is False and r["external_ai_consent_at"] is None and r["external_ai_consent_text_version"] is None
    r = client.put(f"/api/v1/repos/{RID}/ai-consent", json={"consent": True, "consent_text_version": "byok-consent-v1"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["external_ai_consent"] is True and body["external_ai_consent_text_version"] == "byok-consent-v1"
    assert body["external_ai_consent_at"]
    assert client.get(f"/api/v1/repos/{RID}").json()["external_ai_consent"] is True
    r = client.put(f"/api/v1/repos/{RID}/ai-consent", json={"consent": False}).json()
    assert r["external_ai_consent"] is False and r["external_ai_consent_text_version"] is None and r["external_ai_consent_at"]


@pytest.mark.parametrize("body,code", [
    ({"consent": True}, 422), ({"consent": True, "consent_text_version": ""}, 422),
    ({"consent": True, "consent_text_version": "v1", "api_key": "sk-x"}, 422),
    ({"consent": True, "consent_text_version": "has space"}, 422), ({}, 422),
])
def test_ai_consent_validation(client, body, code):
    r = client.put(f"/api/v1/repos/{RID}/ai-consent", json=body)
    assert r.status_code == code and r.json()["error"]["code"] == "invalid_request" and "sk-x" not in r.text


def test_ai_consent_unknown_repo_is_404(client):
    r = client.put("/api/v1/repos/github.com__octo__nope/ai-consent", json={"consent": False})
    assert r.status_code == 404


# ---------------------------------------------------------------- F3: injected controls are marked
def test_injected_control_marked_in_claims_graph_and_trace(client):
    items = client.get(f"{BASE}/claims", params={"include_rejected": True, "limit": 100}).json()["items"]
    inj = [i for i in items if i["claim_id"] == _id(4)]
    assert inj and inj[0]["injected"] is True and "injected_control" in inj[0]["flags"]
    assert all(i["injected"] is False and "injected_control" not in i["flags"] for i in items if i["claim_id"] != _id(4))
    edges = client.get(f"{BASE}/graph", params={"include_rejected": True}).json()["edges"]
    e = [x for x in edges if x["id"] == _id(4)]
    assert e and e[0]["injected"] is True and "injected_control" in e[0]["flags"]
    hops = client.get(f"{BASE}/trace", params={"from": "a.py::foo", "to": "c.py::baz", "include_rejected": True}).json()["hops"]
    assert all("injected" in h for h in hops)


# ---------------------------------------------------------------- F4: truncation is counted
def test_graph_truncation_is_counted_by_status(client):
    g = client.get(f"{BASE}/graph", params={"include_rejected": True, "limit": 3}).json()
    assert g["truncated"] is True and len(g["edges"]) == 3
    assert g["truncated_counts"] == {"rejected": 3}  # rejected sort last; they are reported, not lost
    g = client.get(f"{BASE}/graph", params={"limit": 2}).json()
    assert g["truncated_counts"] == {"verified": 1} and g["hidden_counts"] == {"rejected": 3}
    g = client.get(f"{BASE}/graph").json()
    assert g["truncated"] is False and g["truncated_counts"] == {}


# ---------------------------------------------------------------- F5: hidden counts follow the focus
def test_focused_graph_hidden_counts_are_scoped(client):
    g = client.get(f"{BASE}/graph", params={"focus": "a.py::foo", "depth": 1}).json()
    assert g["hidden_counts"] == {"rejected": 1}  # only the injected edge touches foo's neighbourhood
    g = client.get(f"{BASE}/graph", params={"focus": "x.py::far", "depth": 1}).json()
    assert g["hidden_counts"] == {"rejected": 2}
    assert client.get(f"{BASE}/graph").json()["hidden_counts"] == {"rejected": 3}


def test_snapshot_reports_isolation(client):
    s = client.get(BASE).json()
    assert s["isolation"] == "unshare" and s["unisolated"] is False
