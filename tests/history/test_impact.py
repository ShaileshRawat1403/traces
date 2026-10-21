"""Step 10: history impact (contract sections 6.1, 8.9, D-H1; HT23, HT24, HT15 ceilings)."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from traces.history import HistoryError, cochange, ingest
from traces.history.impact import BASE_GAPS, SOURCE_ALIAS, SOURCE_COCHANGE, history_impact
from traces.history.records import RunContext, ep_file, make_record, recompute_claim_id

from ._repo import SynthRepo
from ._schema import assert_valid
from .conftest import ref
from .test_cochange import CFG, _build

CTX = RunContext("h-test", "2026-10-21T12:00:00+05:30", "t/synth", "0" * 40)
CODE_KINDS = {"calls", "imports", "depends_on", "reads", "writes", "routes_to", "defines"}


def _co(synth: SynthRepo) -> list[dict[str, Any]]:
    _build(synth)
    return cochange(ingest(ref(synth), CFG)).records


def _alias(src: dict[str, Any], frm: str, to: str, state: str = "none") -> dict[str, Any]:
    ctx = RunContext(src["run_id"], "2026-10-21T12:00:00+05:30", src["repo"], src["repo_sha"])
    rec = make_record(ctx, claim_kind="relationship", kind="alias_of", granularity="file", frm=ep_file(frm),
                      to=ep_file(to), statement=f"Suggested alias: {frm} appears to continue in {to}.",
                      cls="history_inferred", provenance="history:alias-suggest", provenance_raw={},
                      origin={"kind": "history_derived", "derived_from": [src["citations"][0]["commit"]]},
                      qualifier=None, citations=src["citations"][:1], anchor={"range": [None, src["repo_sha"]]},
                      params={"t": 1}, max_status="unvalidated",
                      unvalidated_reason="suggestion from content similarity; identity not established by Git")
    rec["review_state"] = {"state": state, "reviewer": "rev" if state != "none" else None,
                           "at": "2026-10-21T12:00:00+05:30" if state != "none" else None}
    return rec


def test_ht23_impact_separation(synth: SynthRepo) -> None:
    co = _co(synth)
    fake_dep = copy.deepcopy(co[0])
    fake_dep["relationship_kind"] = "imports"
    res = history_impact("a.py", [*co, fake_dep])
    assert res.target == "file::a.py"
    assert set(res.by_source) == {SOURCE_COCHANGE, SOURCE_ALIAS}
    assert all(k.startswith("history:") for k in res.by_source)
    assert res.known_gaps and BASE_GAPS[0] in res.known_gaps
    assert any("not co_changed_with" in g for g in res.known_gaps)
    recs = res.by_source[SOURCE_COCHANGE]
    assert recs
    assert_valid(recs)
    for r in recs:
        assert r["relationship_kind"] == "history_impact_candidate" not in CODE_KINDS
        assert r["status"] == "unvalidated" and r["class"] == "history_pattern" and r["checks"] == []
        assert r["qualifier"].startswith("history signal: changed together in ")
        assert r["from"]["symbol"] == "file::a.py"
        src = r["origin"]["derived_from"][0]
        assert src in {c["claim_id"] for c in co}
        assert recompute_claim_id(r) == r["claim_id"]
        assert "not a code dependency" in r["statement"]
    z = [r for r in recs if r["to"]["symbol"] == "file::z.py"]
    assert z and z[0]["qualifier"] == "history signal: changed together in 3 of 5 commits"
    assert res.parameters["inputs_ignored"] == 1
    assert history_impact("a.py", co).by_source == res.by_source  # deterministic, the dep record had no effect


def test_empty_result_still_has_gaps(synth: SynthRepo) -> None:
    co = _co(synth)
    res = history_impact("file::nothing.py", co)
    assert res.by_source[SOURCE_COCHANGE] == [] and res.by_source[SOURCE_ALIAS] == []
    assert any("no co-change records" in g for g in res.known_gaps)
    res2 = history_impact("x.py", [])
    assert res2.known_gaps and res2.by_source[SOURCE_COCHANGE] == []


def test_limit_and_errors(synth: SynthRepo) -> None:
    co = _co(synth)
    with pytest.raises(HistoryError) as ei:
        history_impact("a.py", co, limit=0)
    assert ei.value.code == "E_CONFIG"
    with pytest.raises(HistoryError):
        history_impact("route::x", co)
    other = copy.deepcopy(co[0])
    other["repo_sha"] = "f" * 40
    with pytest.raises(HistoryError) as ei:
        history_impact("a.py", [*co, other])
    assert ei.value.code == "E_EVIDENCE_SET"
    many = []
    for i in range(5):
        r = copy.deepcopy(co[0])
        r["claim_id"] = f"c_{i:064x}"
        r["to"] = ep_file(f"p{i}.py")
        r["from"] = ep_file("a.py")
        many.append(r)
    res = history_impact("a.py", many, limit=2)
    assert len(res.by_source[SOURCE_COCHANGE]) == 2 and res.parameters["truncated"] == 3
    assert any("not shown (limit 2)" in g for g in res.known_gaps)
    assert [r["to"]["symbol"] for r in res.by_source[SOURCE_COCHANGE]] != []


def test_alias_widens_lookup_and_passes_through(synth: SynthRepo) -> None:
    co = _co(synth)
    al = _alias(co[0], "old/a.py", "a.py", "confirmed")
    res = history_impact("old/a.py", co, aliases=[al])
    assert res.by_source[SOURCE_ALIAS] == [al]
    recs = res.by_source[SOURCE_COCHANGE]
    assert recs and all("x-via_alias" in r["flags"] for r in recs)
    assert all(al["claim_id"] in r["origin"]["derived_from"] for r in recs)
    assert_valid(recs)
    disputed = _alias(co[0], "old/a.py", "a.py", "disputed")
    res2 = history_impact("old/a.py", co, aliases=[disputed])
    assert res2.by_source[SOURCE_ALIAS] == [] and res2.by_source[SOURCE_COCHANGE] == []


def test_ht24_review_state_never_changes_status(synth: SynthRepo) -> None:
    co = _co(synth)
    base = _alias(co[0], "old/a.py", "a.py")
    assert_valid([base])
    for state in ("confirmed", "disputed"):
        r = _alias(co[0], "old/a.py", "a.py", state)
        assert_valid([r])
        for k in ("status", "label", "class", "claim_id", "status_history"):
            assert r[k] == base[k]
        assert recompute_claim_id(r) == base["claim_id"]
    confirmed = _alias(co[0], "old/a.py", "a.py", "confirmed")
    out = history_impact("old/a.py", co, aliases=[confirmed]).by_source[SOURCE_ALIAS][0]
    assert out["status"] == "unvalidated" and out["review_state"]["state"] == "confirmed"
