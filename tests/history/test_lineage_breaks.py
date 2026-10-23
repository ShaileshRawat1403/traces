"""D-H15 / HT26: lineage restarts on delete then re-add are flagged, not joined (section 9.2)."""

from __future__ import annotations

from typing import Any

from traces.history import HistoryConfig, Thresholds, churn, cochange, hotspots, ingest, lifecycle
from traces.history.cochange import BANNED_WORDS
from traces.history.lifecycle import LINEAGE_FLAG, identities, lineage_breaks
from traces.history.records import recompute_claim_id

from ._repo import SynthRepo
from ._schema import assert_valid
from .conftest import ref

CFG = HistoryConfig(thresholds=Thresholds(min_revs=2, min_shared_revs=2, min_coupling=0.3, max_changeset_size=4))


def _build(r: SynthRepo) -> dict[str, str]:
    s: dict[str, str] = {}
    r.write("s.py", "def s():\n    return 0\n")
    r.write("u.py", "def u():\n    return 0\n")
    r.write("k.py", "def k():\n    return 0\n")
    r.write("t.py", "t = 0\n")
    r.commit("init")
    for i in range(1, 3):
        r.write("s.py", f"def s():\n    return {i}\n")
        r.write("u.py", f"def u():\n    return {i}\n")
        r.commit(f"s and u {i}")                # pre-delete pair commits: not joined to the re-added s.py
    r.rm("s.py")
    s["del_s"] = r.commit("delete s")
    r.rm("t.py")
    r.commit("delete t 1")
    r.write("t.py", "t = 1\n")
    r.commit("re-add t 1")
    r.rm("t.py")
    r.commit("delete t 2")
    r.write("t.py", "t = 2\n")
    r.commit("re-add t 2")
    r.write("s.py", "class S:\n    def run(self):\n        if True:\n            return 'new'\n")
    s["readd_s"] = r.commit("re-add s")
    for i in range(1, 3):
        r.write("s.py", f"class S:\n    def run(self):\n        if True:\n            return {i}\n")
        r.write("u.py", f"def u():\n    return {i + 10}\n")
        r.commit(f"s and u again {i}")
    for i in range(1, 4):
        r.write("k.py", f"def k():\n    return {i}\n")
        r.write("u.py", f"def u():\n    return {i + 20}\n")
        r.commit(f"k and u {i}")
    return s


def _by_file(recs: Any, prov: str) -> dict[str, Any]:
    return {x["from"]["file"]: x for x in recs if x["provenance"] == prov}


def test_ht26_lineage_breaks_counted_per_head_path(synth: SynthRepo) -> None:
    _build(synth)
    log = ingest(ref(synth), CFG)
    assert lineage_breaks(log, identities(log, {"s.py", "u.py", "k.py", "t.py"})) == {"s.py": 1, "t.py": 2}
    assert lifecycle(log).report["lineage_breaks"] == {"s.py": 1, "t.py": 2}


def test_ht26_churn_and_hotspot_records_flag_only_affected_paths(synth: SynthRepo) -> None:
    _build(synth)
    log = ingest(ref(synth), CFG)
    for fn, prov in ((churn, "history:churn"), (hotspots, "history:hotspot")):
        res = fn(log)
        assert_valid(res.records)
        recs = _by_file(res.records, prov)
        s, t = recs["s.py"], recs["t.py"]
        for rec, n in ((s, 1), (t, 2)):
            assert rec["metrics"]["lineage_breaks"] == n
            assert LINEAGE_FLAG in rec["flags"]
            assert "restarts after" in rec["provenance_raw"]["caveat"]
            assert rec["statement"].endswith(rec["provenance_raw"]["caveat"])
            assert recompute_claim_id(rec) == rec["claim_id"]
            assert "lineage_breaks" not in rec["parameters"]["values"]  # claim_id inputs unchanged
        assert "2 delete and re-add gaps" in t["provenance_raw"]["caveat"]
        for name in ("u.py", "k.py"):
            rec = recs[name]
            assert "lineage_breaks" not in rec["metrics"]
            assert LINEAGE_FLAG not in rec["flags"] and "caveat" not in rec["provenance_raw"]
            assert rec["statement"].endswith("History pattern.")
    # Lineage behaviour unchanged: s.py counts only from its re-add (re-add plus 2 edits), not the 3 earlier commits.
    assert _by_file(churn(log).records, "history:churn")["s.py"]["metrics"]["revisions"] == 3


def test_ht26_cochange_pairs_flag_only_affected_sides(synth: SynthRepo) -> None:
    sh = _build(synth)
    log = ingest(ref(synth), CFG)
    res = cochange(log)
    assert_valid(res.records)
    pairs = {(x["from"]["file"], x["to"]["file"]): x for x in res.records}
    su = pairs[("s.py", "u.py")]
    m = su["metrics"]
    # Unchanged restart: support counts only the 2 commits after the re-add; the 3 earlier s+u commits are not joined.
    assert (m["support"], m["revs_a"]) == (2, 3)
    assert all(c["commit"] not in (sh["del_s"],) for c in su["citations"])
    assert (m["lineage_breaks"], m["lineage_breaks_a"], m["lineage_breaks_b"]) == (1, 1, 0)
    assert LINEAGE_FLAG in su["flags"] and su["provenance_raw"]["caveat"].startswith("History for s.py restarts")
    assert "changed together in 2 of" in su["statement"]
    assert not any(w in su["statement"].lower() for w in BANNED_WORDS)
    assert recompute_claim_id(su) == su["claim_id"]
    ku = pairs[("k.py", "u.py")]
    assert not any(k.startswith("lineage_breaks") for k in ku["metrics"])
    assert ku["flags"] == [] and "caveat" not in ku["provenance_raw"]
    assert ku["statement"].endswith("does not show intent.")
    assert res.report["lineage_break_records"] == 1


def test_ht26_no_gap_repo_has_no_lineage_fields(synth: SynthRepo) -> None:
    synth.write("a.py", "a = 0\n")
    synth.write("b.py", "b = 0\n")
    synth.commit("init")
    for i in range(1, 4):
        synth.write("a.py", f"a = {i}\n")
        synth.write("b.py", f"b = {i}\n")
        synth.commit(f"edit {i}")
    log = ingest(ref(synth), CFG)
    assert lifecycle(log).report["lineage_breaks"] == {}
    for res in (churn(log), hotspots(log), cochange(log)):
        assert res.records
        for rec in res.records:
            assert not any(k.startswith("lineage_breaks") for k in rec["metrics"])
            assert LINEAGE_FLAG not in rec["flags"] and "caveat" not in rec["provenance_raw"]
