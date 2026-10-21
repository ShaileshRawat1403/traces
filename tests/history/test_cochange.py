"""Step 6: co-change (contract section 9.4, D-H1; HT15, HT16)."""

from __future__ import annotations

import re

import pytest

from traces.history import (
    ComponentDef,
    ComponentMap,
    FilterSpec,
    HistoryConfig,
    HistoryError,
    Thresholds,
    cochange,
    ingest,
)
from traces.history.cochange import BANNED_WORDS

from ._repo import BOT, SynthRepo
from ._schema import assert_valid
from .conftest import ref

T = Thresholds(min_revs=2, min_shared_revs=2, min_coupling=0.3, max_changeset_size=4)
CFG = HistoryConfig(thresholds=T)
WORDING = re.compile(r"^changed together in (\d+) of (\d+) commits$")


def _build(r: SynthRepo) -> dict[str, str]:
    s = {}
    r.write("z.py", "0\n")
    r.write("a.py", "0\n")
    r.write("c.py", "0\n")
    s["c0"] = r.commit("init")                  # z, a, c together (1)
    for i in range(1, 3):
        r.write("z.py", f"{i}\n")
        r.write("a.py", f"{i}\n")
        r.commit(f"pair {i}")                   # z, a together (2, 3)
    r.write("z.py", "solo\n")
    r.commit("z alone")                         # z alone
    r.write("a.py", "bot\n")
    r.write("z.py", "bot\n")
    r.commit("bot both", BOT)                   # skipped by default
    for i in range(5):
        r.write(f"big{i}.py", "x\n")
    r.write("a.py", "big\n")
    r.write("z.py", "big\n")
    r.commit("large changeset")                 # 7 paths > 4: skipped
    r.checkout("-b", "feat")
    r.write("c.py", "feat\n")
    s["feat"] = r.commit("feat c")
    r.checkout("main")
    r.write("a.py", "main\n")
    r.commit("main a")
    s["merge"] = r.merge("feat")                # merge: never counted
    return s


def _pair(res, a, b):  # type: ignore[no-untyped-def]
    for r in res.records:
        if {r["from"].get("file"), r["to"].get("file")} == {a, b}:
            return r
    return None


def test_cochange_counts_wording_and_status(synth: SynthRepo) -> None:
    _build(synth)
    res = cochange(ingest(ref(synth), CFG))
    assert_valid(res.records)
    r = _pair(res, "a.py", "z.py")
    assert r is not None
    assert (r["from"]["file"], r["to"]["file"]) == ("a.py", "z.py")  # symmetric, ordered
    m = r["metrics"]
    # considered: init, pair1, pair2, z alone, feat c, main a  (bot, large and merge skipped)
    assert (m["support"], m["revs_a"], m["revs_b"], m["union_commits"]) == (3, 4, 4, 5)
    assert (m["commits_considered"], m["commits_skipped_bot"], m["commits_skipped_large"], m["commits_skipped_merge"]) == (6, 1, 1, 1)
    assert m["degree"] == 0.75 and m["confidence_a_to_b"] == 0.75
    assert WORDING.match(r["qualifier"]).groups() == ("3", "5")
    assert "changed together in 3 of 5 commits" in r["statement"]
    low = r["statement"].lower()
    assert not any(w in low for w in BANNED_WORDS)
    assert r["class"] == "history_pattern" and r["relationship_kind"] == "co_changed_with"
    assert r["status"] == "observed" and r["checks"][0]["method"] == "git_recount"
    v = r["parameters"]["values"]
    assert (v["min_revs"], v["min_shared_revs"], v["min_coupling"], v["max_changeset_size"]) == (2, 2, 0.3, 4)
    assert len(r["citations"]) == 3
    for c in r["citations"]:
        assert {p["path"] for p in c["paths"]} == {"a.py", "z.py"}


def test_thresholds_filter_pairs_and_change_ids(synth: SynthRepo) -> None:
    _build(synth)
    log = ingest(ref(synth), CFG)
    base = _pair(cochange(log), "a.py", "z.py")
    strict = ingest(ref(synth), HistoryConfig(thresholds=Thresholds(min_revs=2, min_shared_revs=4, min_coupling=0.3,
                                                                    max_changeset_size=4)))
    assert _pair(cochange(strict), "a.py", "z.py") is None
    other = ingest(ref(synth), HistoryConfig(thresholds=Thresholds(min_revs=2, min_shared_revs=2, min_coupling=0.31,
                                                                   max_changeset_size=4)))
    moved = _pair(cochange(other), "a.py", "z.py")
    assert moved is not None and moved["claim_id"] != base["claim_id"]
    assert _pair(cochange(log), "c.py", "z.py") is None  # one shared commit only


def test_bots_included_when_filter_off(synth: SynthRepo) -> None:
    _build(synth)
    cfg = HistoryConfig(thresholds=T, filters=FilterSpec(exclude_bots_from_patterns=False))
    r = _pair(cochange(ingest(ref(synth), cfg)), "a.py", "z.py")
    assert r["metrics"]["support"] == 4 and r["metrics"]["commits_skipped_bot"] == 0
    assert r["status"] == "observed"


def test_merges_never_counted(synth: SynthRepo) -> None:
    s = _build(synth)
    res = cochange(ingest(ref(synth), CFG))
    for r in res.records:
        assert s["merge"] not in {c["commit"] for c in r["citations"]}


def test_component_level_unvalidated(synth: SynthRepo) -> None:
    _build(synth)
    log = ingest(ref(synth), CFG)
    cm = ComponentMap(log.repo.sha, {
        "component::one": ComponentDef("component::one", "one", "backend", ("a.py",), "t"),
        "component::two": ComponentDef("component::two", "two", "backend", ("z.py",), "t")}, "d" * 64)
    res = cochange(log, level="component", components=cm)
    assert_valid(res.records)
    (r,) = res.records
    assert (r["from"]["symbol"], r["to"]["symbol"]) == ("component::one", "component::two")
    assert r["status"] == "unvalidated" and r["granularity"] == "component"
    assert r["parameters"]["values"]["component_map_digest"] == "d" * 64
    with pytest.raises(HistoryError) as ei:
        cochange(log, level="component")
    assert ei.value.code == "E_COMPONENT_MAP"


def test_statement_never_claims_causation() -> None:
    from traces.history.cochange import statement_for

    s = statement_for("a.py", "b.py", 3, 5, "file").lower()
    assert "not a code dependency" in s
    assert not any(w in s for w in BANNED_WORDS)
