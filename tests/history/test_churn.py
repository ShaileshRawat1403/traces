"""Step 5: churn and hotspots (contract sections 6.1, 9.3; proxy labelled)."""

from __future__ import annotations

from traces.history import ComponentDef, ComponentMap, FilterSpec, HistoryConfig, Thresholds, churn, hotspots, ingest

from ._repo import ALICE, BOB, BOT, SynthRepo, lines
from ._schema import assert_valid
from .conftest import NO_FILTERS, ref


def _build(r: SynthRepo) -> None:
    r.write("app/core.py", lines(10))                       # +10
    r.write("app/util.py", "def f():\n    if x:\n        return 1\n")
    r.commit("init", ALICE)
    r.write("app/core.py", lines(12))                       # +2
    r.commit("grow", BOB)
    r.mv("app/core.py", "app/main.py")                      # rename keeps identity, 0 churn
    r.commit("rename", ALICE)
    r.write("app/main.py", lines(11))                       # -1
    r.write("package-lock.json", "{}\n")
    r.commit("bot bump", BOT)
    r.checkout("-b", "feat")
    r.write("app/main.py", lines(13))                       # +2 on a branch
    r.commit("feature", BOB)
    r.checkout("main")
    r.write("app/util.py", "def f():\n    if x:\n        if y:\n            return 2\n")
    r.commit("util", ALICE)
    r.merge("feat")                                         # merge is not counted


def _metrics(res, path):  # type: ignore[no-untyped-def]
    return next(r for r in res.records if r["from"]["file"] == path)


def test_churn_counts_non_merge_and_follows_renames(synth: SynthRepo) -> None:
    _build(synth)
    res = churn(ingest(ref(synth), NO_FILTERS))
    assert_valid(res.records)
    m = _metrics(res, "app/main.py")
    assert m["metrics"]["revisions"] == 5      # init, grow, rename, bot bump, feature; merge excluded
    assert (m["metrics"]["added"], m["metrics"]["deleted"]) == (14, 1)
    assert m["status"] == "observed" and m["checks"][0]["method"] == "git_recount"
    assert m["class"] == "history_pattern" and m["parameters"]["values"]["commits"] == "non-merge commits only"
    assert len(m["citations"]) == 5


def test_churn_default_filters_exclude_bots_and_generated(synth: SynthRepo) -> None:
    _build(synth)
    res = churn(ingest(ref(synth), HistoryConfig()))
    m = _metrics(res, "app/main.py")
    assert m["metrics"]["revisions"] == 4 and m["status"] == "observed"
    assert all(r["from"]["file"] != "package-lock.json" for r in res.records)
    assert res.report["skipped_commits"].get("bot") == 1
    assert m["parameters"]["values"]["filters"]["exclude_bots_from_patterns"] is True


def test_component_metrics_unvalidated(synth: SynthRepo) -> None:
    _build(synth)
    log = ingest(ref(synth), NO_FILTERS)
    cm = ComponentMap(log.repo.sha, {"component::app": ComponentDef("component::app", "app", "backend",
                                                                    ("app/main.py", "app/util.py"), "t")}, "d" * 64)
    res = churn(log, components=cm)
    comp = [r for r in res.records if r.get("node_kind") == "component_history_metrics"]
    assert len(comp) == 1 and comp[0]["status"] == "unvalidated" and comp[0]["from"]["symbol"] == "component::app"
    assert comp[0]["metrics"]["revisions"] == 6
    assert_valid(res.records)


def test_hotspots_proxy_labelled(synth: SynthRepo) -> None:
    _build(synth)
    res = hotspots(ingest(ref(synth), NO_FILTERS))
    assert_valid(res.records)
    paths = {r["from"]["file"] for r in res.records}
    assert paths == {"app/main.py", "app/util.py"}  # code extensions only; lockfile excluded
    for r in res.records:
        assert "complexity_proxy" in r["flags"]
        assert "proxy" in r["qualifier"]
        assert 0 <= r["metrics"]["hotspot_score"] <= 1
        assert r["status"] == "observed"
    u = _metrics(res, "app/util.py")
    assert (u["metrics"]["indent_complexity"], u["metrics"]["loc"], u["metrics"]["revisions"]) == (6, 4, 2)
    m = _metrics(res, "app/main.py")
    assert (m["metrics"]["revisions_rank_norm"], m["metrics"]["complexity_rank_norm"]) == (1.0, 0.5)
    assert m["metrics"]["hotspot_score"] == 0.5


def test_hotspots_small_changeset_cap(synth: SynthRepo) -> None:
    synth.write("a.py", "x\n")
    synth.commit("a")
    for i in range(4):
        synth.write(f"b{i}.py", "y\n")
    synth.write("a.py", "x\n    y\n")
    synth.commit("big")
    cfg = HistoryConfig(thresholds=Thresholds(max_changeset_size=3),
                        filters=FilterSpec(exclude_bots_from_patterns=False))
    res = hotspots(ingest(ref(synth), cfg))
    a = _metrics(res, "a.py")
    assert (a["metrics"]["revisions"], a["metrics"]["revisions_small_commits"]) == (2, 1)
    assert a["status"] == "observed"
    assert a["parameters"]["values"]["max_changeset_size"] == 3
