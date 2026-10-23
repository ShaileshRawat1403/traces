"""F-9 scope (D-031): unresolved calls are gaps when listing what a symbol calls, not side calls on a from -> to path;
a call already shown as a hop from the same step is not reported again (fsft real-snapshot trace stays 10 steps)."""
from __future__ import annotations

from tests.api.test_views import BASE, SHA, _id, client, rec, st  # noqa: F401  (pytest fixtures)


def _unresolved(st, n, name):  # noqa: F811
    sid = st.db.execute("SELECT id FROM snapshots WHERE sha=?", (SHA,)).fetchone()[0]
    r = rec(claim_id=_id(n), claim_kind="unresolved_reference", relationship_kind=None, status="unvalidated", label="inferred",
            statement=f"CodeGraph reports an unresolved calls reference '{name}' from 'foo'",
            provenance_raw={"row": {"reference_kind": "calls", "reference_name": name, "file_path": "a.py", "line": 3, "col": 0}},
            **{"from": {"entity": "symbol", "symbol": "a.py::foo", "file": "a.py"}, "to": None})
    r.pop("relationship_kind")
    st.put_claims(sid, [r])


def test_listing_names_only_calls_not_already_shown(client, st):  # noqa: F811
    _unresolved(st, 50, "bar")  # the same call as the shown foo -> b.py::bar hop
    _unresolved(st, 51, "sideCall")
    http, _sha = client
    t = http.get(f"{BASE}/trace", params={"from": "a.py::foo"}).json()
    gaps = [h for h in t["hops"] if h["type"] == "gap"]
    assert [g["unresolved_calls"] for g in gaps] == [["sideCall"]]
    assert t["complete"] is False


def test_path_is_judged_by_its_own_hops(client, st):  # noqa: F811
    _unresolved(st, 52, "sideCall")
    http, _sha = client
    t = http.get(f"{BASE}/trace", params={"from": "a.py::foo", "to": "c.py::baz"}).json()
    assert [h["type"] for h in t["hops"]] == ["edge", "library_contract"]
    assert t["complete"] is True and t["incomplete_reasons"] == []
