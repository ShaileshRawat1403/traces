"""View and history endpoints read stored evidence. They do not invent relationships or promote status."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from traces.api.app import app, get_store
from traces.evidence.store import Store
from traces.evidence.types import ComponentDef

SHA = "b1125d8839482cb7bbae603ddc6d0081bf87532e"
SHA2 = "c" * 40
RID = "github.com__octo__demo"
BASE = f"/api/v1/repos/{RID}/snapshots/{SHA}"
V04 = "traces-evidence/0.4"


def _id(n: int) -> str:
    return "c_" + f"{n:064x}"


def rec(**kw):
    base = {
        "schema_version": V04, "claim_id": _id(1), "run_id": "t", "claim_kind": "relationship", "relationship_kind": "calls",
        "from": {"entity": "symbol", "symbol": "a.py::foo", "file": "a.py"},
        "to": {"entity": "symbol", "symbol": "b.py::bar", "file": "b.py"},
        "statement": "foo calls bar", "class": "framework_rule",
        "originator": {"name": "codegraph", "version": "1.6.2", "role": "extractor"},
        "evidence_scope": "static", "status": "verified", "label": "verified", "injected": False, "flags": [], "qualifier": None,
        "locations": [{"file": "a.py", "start_line": 3, "end_line": 4, "role": "site", "range_kind": "site"}],
    }
    base.update(kw)
    return base


@pytest.fixture()
def st(tmp_path: Path) -> Store:
    s = Store(":memory:")
    s.upsert_repo(RID, "github.com", "octo", "demo", "https://github.com/octo/demo")
    sid = s.upsert_snapshot(RID, SHA, "indexing")
    s.finish_snapshot(sid, extractor={}, languages={"Python": 2}, frameworks=["FastAPI"], generated_paths=[],
                      stats={"files": 2, "history": {"state": "done", "records": 1}})
    s.put_components(sid, [ComponentDef(id="component::pkg", name="pkg", layer="backend", paths=("a.py", "b.py"), rule="dir-v1:container-strip")])
    verified = rec(claim_id=_id(1))
    library = rec(claim_id=_id(2), relationship_kind="library_contract", status="unvalidated", label="inferred",
                  flags=["library_contract"], qualifier="library behavior, not a verified call",
                  **{"from": {"entity": "symbol", "symbol": "b.py::bar", "file": "b.py"},
                     "to": {"entity": "symbol", "symbol": "c.py::baz", "file": "c.py"},
                     "statement": "bar reaches baz through a library"})
    rejected = rec(claim_id=_id(3), status="rejected", label="rejected",
                   **{"from": {"entity": "symbol", "symbol": "a.py::foo", "file": "a.py"},
                      "to": {"entity": "symbol", "symbol": "c.py::baz", "file": "c.py"},
                      "statement": "rejected shortcut"})
    route = rec(claim_id=_id(4), claim_kind="node", relationship_kind=None, node_kind="route",
                status="unvalidated", label="inferred",
                statement="CodeGraph reports a route node 'GET /items' at a.py:10-12.",
                **{"from": {"entity": "symbol", "symbol": "a.py::list_items", "file": "a.py", "start_line": 10}, "to": None,
                   "provenance_raw": {"route_local_path": "/items", "row": {"name": "GET /items"}}})
    route.pop("relationship_kind")
    co = rec(claim_id=_id(5), relationship_kind="co_changed_with", evidence_scope="history", class_="history_pattern",
             status="observed", label="observed", granularity="file", qualifier="changed together in 4 of 5 commits",
             **{"from": {"entity": "file", "symbol": "file::a.py", "file": "a.py"},
                "to": {"entity": "file", "symbol": "file::b.py", "file": "b.py"},
                "statement": "a.py and b.py changed together"})
    co["class"] = co.pop("class_")
    commit = rec(claim_id=_id(6), claim_kind="node", node_kind="commit", evidence_scope="history", class_="git_object_fact",
                 status="observed", label="observed", relationship_kind=None,
                 statement="Commit deadbeef (2020-01-02, 1 parent(s)).",
                 provenance_raw={"committer_time": 20},
                 **{"from": {"entity": "commit", "symbol": "commit::" + "d" * 40}, "to": None})
    commit.pop("relationship_kind")
    commit["class"] = commit.pop("class_")
    hot = rec(claim_id=_id(7), claim_kind="node", node_kind="file_history_metrics", evidence_scope="history",
              class_="history_pattern", status="observed", label="observed", relationship_kind=None,
              statement="a.py changed often. This is a history pattern, not a quality score.",
              **{"from": {"entity": "file", "symbol": "file::a.py", "file": "a.py"}, "to": None})
    hot.pop("relationship_kind")
    hot["class"] = hot.pop("class_")
    mile = rec(claim_id=_id(8), claim_kind="node", node_kind="milestone", evidence_scope="history", class_="git_object_fact",
               status="observed", label="observed", relationship_kind=None, statement="Milestone.",
               provenance_raw={"committer_time": 30},
               **{"from": {"entity": "commit", "symbol": "commit::" + "e" * 40}, "to": None})
    mile.pop("relationship_kind")
    mile["class"] = mile.pop("class_")
    why = rec(claim_id=_id(9), relationship_kind="documents_rationale", evidence_scope="documented", class_="documented_rationale",
              status="observed", label="observed", qualifier="quoted rationale, not proof of intent",
              statement='PR text says "added items". A quote is not proof of intent.')
    why["class"] = why.pop("class_")
    touch = rec(claim_id=_id(10), relationship_kind="commit_modifies", evidence_scope="history", class_="git_object_fact",
                status="observed", label="observed",
                **{"from": {"entity": "commit", "symbol": "commit::" + "d" * 40},
                   "to": {"entity": "file", "symbol": "file::a.py", "file": "a.py"},
                   "statement": "commit modified a.py"})
    touch["class"] = touch.pop("class_")
    s.put_claims(sid, [verified, library, rejected, route, co, commit, hot, mile, why, touch])
    # second snapshot: only the verified edge, so compare sees a difference
    sid2 = s.upsert_snapshot(RID, SHA2, "ready")
    other = rec(claim_id=_id(11), statement="only on the other snapshot",
                **{"from": {"entity": "symbol", "symbol": "a.py::other", "file": "a.py"},
                   "to": {"entity": "symbol", "symbol": "b.py::other", "file": "b.py"}})
    s.put_claims(sid2, [other])
    s.checkout = tmp_path  # type: ignore[attr-defined]
    return s


@pytest.fixture()
def client(st: Store, monkeypatch: pytest.MonkeyPatch):
    root = st.checkout  # type: ignore[attr-defined]
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "t@example.com"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "t"], check=True)
    (root / "a.py").write_text("line1\nline2\nfoo()\nline4\n")
    (root / "README.md").write_text("# Demo notes\n\nNot a capability claim.\n")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "init"], check=True)
    sha = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    # point the source reader at this checkout regardless of the snapshot SHA
    from traces.api import app as appmod

    monkeypatch.setattr(appmod, "_checkout", lambda repo_id, snapshot_sha: root)
    app.dependency_overrides[get_store] = lambda: st
    yield TestClient(app), sha
    app.dependency_overrides.clear()


def test_overview_keeps_facts_and_unknowns_apart(client):
    http, _sha = client
    body = http.get(f"{BASE}/overview")
    assert body.status_code == 200, body.text
    data = body.json()
    kinds = {f["kind"] for group in ("business", "architecture", "implementation", "entry_points", "start_here") for f in data[group]}
    assert {"fact", "unknown", "interpretation"} <= kinds
    text = " ".join(f["text"] for f in data["business"])
    assert "not verified" in text
    assert "FastAPI" in " ".join(f["text"] for f in data["architecture"])
    assert data["counts"]["verified"] == 1
    assert data["counts"]["rejected"] == 1


def test_graph_hides_rejected_and_history(client):
    http, _sha = client
    g = http.get(f"{BASE}/graph").json()
    ids = {e["id"] for e in g["edges"]}
    assert _id(1) in ids
    assert _id(3) not in ids  # rejected shortcut is not architecture
    assert _id(5) not in ids  # co-change is not a code edge
    assert g["hidden_counts"].get("rejected") == 1
    focused = http.get(f"{BASE}/graph", params={"focus": "a.py::foo", "depth": 1, "status": ["verified"]}).json()
    assert {e["id"] for e in focused["edges"]} == {_id(1)}
    assert any(n["id"] == "component::pkg" for n in focused["nodes"])
    by_component = http.get(f"{BASE}/graph", params={"focus": "component::pkg", "depth": 1, "status": ["verified"]}).json()
    assert _id(1) in {e["id"] for e in by_component["edges"]}
    assert any(n["id"] == "component::pkg" for n in by_component["nodes"])


def test_trace_uses_library_hop_and_not_the_rejected_shortcut(client):
    http, _sha = client
    t = http.get(f"{BASE}/trace", params={"from": "a.py::foo", "to": "c.py::baz"}).json()
    kinds = [h["type"] for h in t["hops"]]
    assert kinds == ["edge", "library_contract"]
    assert t["hops"][1]["label"] == "inferred"
    assert t["hops"][1]["reason"]
    assert all(h["claim_id"] != _id(3) for h in t["hops"])
    missing = http.get(f"{BASE}/trace", params={"from": "a.py::foo", "to": "nope"}).json()
    assert missing["hops"][0]["type"] == "gap" and missing["hops"][0]["label"] == "inferred"


def test_routes_do_not_invent_a_method(client):
    http, _sha = client
    rows = http.get(f"{BASE}/routes").json()
    assert rows[0]["path"] == "/items" and rows[0]["method"] == "GET"
    assert rows[0]["claim_id"] == _id(4)


def test_components_count_claims(client):
    http, _sha = client
    rows = http.get(f"{BASE}/components").json()
    assert rows[0]["id"] == "component::pkg" and rows[0]["rule"] == "dir-v1:container-strip"
    assert rows[0]["claim_counts"]["verified"] >= 1


def test_source_reads_git_objects_and_rejects_escape(client, st: Store):
    http, git_sha = client
    from traces.evidence.views import ViewError, source_view

    snap = dict(st.get_snapshot(f"{RID}@{SHA}"))
    snap["sha"] = git_sha  # the fixture snapshot SHA is not this throwaway commit
    body = source_view(st, snap, path="a.py", start=3, end=3, checkout=st.checkout)  # type: ignore[attr-defined]
    assert body["lines"] == ["foo()"] and _id(1) in body["claim_ids"]
    for bad in ("../secrets", "/etc/passwd", "a.py/../../x", "-n"):
        r = http.get(f"{BASE}/source", params={"path": bad})
        assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request", bad
    with pytest.raises(ViewError) as ei:
        source_view(st, snap, path="nope.py", start=1, end=None, checkout=st.checkout)  # type: ignore[attr-defined]
    assert ei.value.status == 404


def test_history_views_do_not_mix_scopes(client):
    http, _sha = client
    timeline = http.get(f"{BASE}/history/timeline").json()
    assert [i["claim_id"] for i in timeline["items"]] == [_id(6)]
    touched = http.get(f"{BASE}/history/timeline", params={"path": "a.py"}).json()
    assert [i["claim_id"] for i in touched["items"]] == [_id(10)]
    hot = http.get(f"{BASE}/history/hotspots").json()
    assert [i["claim_id"] for i in hot["items"]] == [_id(7)]
    co = http.get(f"{BASE}/history/cochange").json()
    assert [i["claim_id"] for i in co["items"]] == [_id(5)]
    assert "caused" not in co["items"][0]["statement"]
    miles = http.get(f"{BASE}/history/milestones").json()
    assert [i["claim_id"] for i in miles["items"]] == [_id(8)]
    why = http.get(f"{BASE}/history/rationale").json()
    assert why["items"][0]["evidence_scope"] == "documented"
    life = http.get(f"{BASE}/history/lifecycle", params={"path": "a.py"}).json()
    assert _id(10) in {i["claim_id"] for i in life["items"]}
    assert _id(1) not in {i["claim_id"] for i in life["items"]}


def test_compare_reports_real_claims_and_hides_rejected(client):
    http, _sha = client
    same = http.get(f"/api/v1/repos/{RID}/compare", params={"base": SHA, "head": SHA}).json()
    assert same["total"] == 0
    diff = http.get(f"/api/v1/repos/{RID}/compare", params={"base": SHA, "head": SHA2}).json()
    ids = {i["claim_id"] for i in diff["items"]}
    assert _id(11) in ids and _id(1) in ids
    assert _id(3) not in ids  # rejected is not "present architecture"
    assert diff["hidden_counts"].get("rejected", 0) >= 1
    assert http.get(f"/api/v1/repos/{RID}/compare", params={"base": "nope", "head": SHA}).status_code == 422
