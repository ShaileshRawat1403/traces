"""F5 consistency (Traces seat on b37eef2): with a symbol focus, hidden_counts counts exactly the hidden edges that
include_rejected=true would add to the focused graph (both ends in the neighbourhood, as for shown edges)."""
from __future__ import annotations

from tests.api.test_views import BASE, SHA, _id, client, rec, st  # noqa: F401  (pytest fixtures)


def _far_rejected(st):  # noqa: F811
    sid = st.db.execute("SELECT id FROM snapshots WHERE sha=?", (SHA,)).fetchone()[0]
    far = rec(claim_id=_id(40), status="rejected", label="rejected", statement="bar to a far symbol (rejected)",
              **{"from": {"entity": "symbol", "symbol": "b.py::bar", "file": "b.py"},
                 "to": {"entity": "symbol", "symbol": "z.py::far", "file": "z.py"}})
    st.put_claims(sid, [far])


def _rejected_shown(g):
    return sum(1 for e in g["edges"] if e["status"] == "rejected")


def test_focused_hidden_counts_equal_what_include_rejected_adds(client, st):  # noqa: F811
    _far_rejected(st)
    http, _sha = client
    for depth in (1, 2):
        params = {"focus": "a.py::foo", "depth": depth}
        g = http.get(f"{BASE}/graph", params=params).json()
        shown = http.get(f"{BASE}/graph", params={**params, "include_rejected": "true"}).json()
        assert g["hidden_counts"].get("rejected", 0) == _rejected_shown(shown), (depth, g["hidden_counts"], shown["edges"])
    one = http.get(f"{BASE}/graph", params={"focus": "a.py::foo", "depth": 1}).json()
    # depth 1 from foo: the rejected foo -> baz shortcut is inside the neighbourhood; bar -> far (one more hop) is not
    assert one["hidden_counts"].get("rejected") == 1
    two = http.get(f"{BASE}/graph", params={"focus": "a.py::foo", "depth": 2}).json()
    assert two["hidden_counts"].get("rejected") == 2
    assert http.get(f"{BASE}/graph", params={"focus": "a.py::foo", "depth": 0}).json()["hidden_counts"].get("rejected", 0) == 0
