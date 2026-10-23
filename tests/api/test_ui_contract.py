"""UI contract asks: RouteItem.label, per-step hidden counts in trace gaps, and component layer reasons (D-029)."""
from __future__ import annotations

from tests.api.test_views import BASE, _id, client, st  # noqa: F401  (pytest fixtures)


def test_route_label_is_the_recorded_name(client):  # noqa: F811
    http, _sha = client
    rows = http.get(f"{BASE}/routes").json()
    assert rows[0]["label"] == "GET /items"


def test_trace_gap_states_hidden_rejected_per_step(client):  # noqa: F811
    http, _sha = client
    t = http.get(f"{BASE}/trace", params={"from": "a.py::foo", "to": "nope"}).json()
    gaps = [h for h in t["hops"] if h["type"] == "gap"]
    assert gaps, t
    g = gaps[0]
    assert g["hidden_rejected"] == 1
    assert "1 outgoing static relationship" in g["reason"] and "rejected" in g["reason"]
    assert "include_rejected=true" in g["reason"]
    shown = http.get(f"{BASE}/trace", params={"from": "a.py::foo", "to": "nope", "include_rejected": "true"}).json()
    assert shown["hops"][0]["hidden_rejected"] == 0


def test_trace_gap_says_when_nothing_is_hidden(client):  # noqa: F811
    http, _sha = client
    t = http.get(f"{BASE}/trace", params={"from": "c.py::baz", "to": "a.py::foo"}).json()
    gaps = [h for h in t["hops"] if h["type"] == "gap"]
    assert gaps and gaps[0]["hidden_rejected"] == 0
    assert "No outgoing relationship from this step is hidden" in gaps[0]["reason"]


def test_component_reason_and_library_layer_reach_the_api(client, st):  # noqa: F811
    from traces.evidence.types import ComponentDef

    http, _sha = client
    old = http.get(f"{BASE}/components").json()
    assert old[0]["reason"] is None  # rows stored before D-029 carry no reason; the API says null, not a guess
    sid = old[0]["id"] and st.db.execute("SELECT id FROM snapshots WHERE sha=?", ("b1125d8839482cb7bbae603ddc6d0081bf87532e",)).fetchone()[0]
    st.put_components(sid, [ComponentDef(id="component::pkg", name="pkg", layer="library", paths=("a.py", "b.py"),
                                         rule="dir-v1:container-strip+library-v1:no-app-entrypoint", reason="library: 2 of 2 file(s)")])
    rows = http.get(f"{BASE}/components").json()
    assert rows[0]["layer"] == "library" and rows[0]["reason"] == "library: 2 of 2 file(s)"
    nodes = http.get(f"{BASE}/graph").json()["nodes"]
    assert any(n["id"] == "component::pkg" and n.get("layer") == "library" for n in nodes)
