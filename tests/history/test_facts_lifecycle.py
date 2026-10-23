"""Step 4: commit facts and lifecycle (contract sections 6.1, 9.2; HT2, HT3, HT6 to HT10)."""

from __future__ import annotations

import pytest

from traces.history import (
    ComponentDef,
    ComponentMap,
    HistoryError,
    RunContext,
    canonical_hash,
    commit_facts,
    ingest,
    lifecycle,
)
from traces.history.ingest import ls_tree_paths, open_runner
from traces.history.lifecycle import identities

from ._repo import BOT, SynthRepo, lines
from ._schema import assert_valid
from .conftest import NO_FILTERS, ref

CTX = RunContext("h-a", "2026-10-21T10:00:00+05:30", "synthetic/repo", "")


def _build(r: SynthRepo) -> dict[str, str]:
    s = {}
    for i in range(4):
        r.write(f"src/pkg/m{i}.py", lines(20, f"m{i}"))
    r.write("README.md", "hi\n")
    s["init"] = r.commit("init")
    for i in range(4):
        r.mv(f"src/pkg/m{i}.py", f"lib/pkg/m{i}.py")
    s["move"] = r.commit("bulk move src -> lib")
    r.write("lib/pkg/m0.py", lines(21, "m0"))
    r.write("web/dist/app.js", "x\n")
    s["bot"] = r.commit("bot bump", BOT)
    r.checkout("-b", "feat")
    r.mv("lib/pkg/m1.py", "lib/pkg/renamed.py")
    r.write(b"odd\tname-\xff.py", "x\n")
    s["feat"] = r.commit("feature")
    r.checkout("main")
    r.write("README.md", "hi there\n")
    s["main"] = r.commit("main work")
    s["merge"] = r.merge("feat")
    r.rm("lib/pkg/m2.py")
    s["del"] = r.commit("delete m2")
    r.write("lib/pkg/m2.py", "brand new\n")
    s["readd"] = r.commit("re-add m2")
    r.write("lib/pkg/copy.py", lines(20, "m3"))
    r.write("lib/pkg/m3.py", lines(20, "m3") + "changed\n")
    s["copy"] = r.commit("copy m3")
    return s


def test_commit_facts_all_observed_and_valid(synth: SynthRepo) -> None:
    s = _build(synth)
    log = ingest(ref(synth), NO_FILTERS)
    res = commit_facts(log)
    assert assert_valid(res.records) == len(res.records)
    nodes = [r for r in res.records if r.get("node_kind") == "commit"]
    assert len(nodes) == len(log.commits)
    assert all(r["status"] == "observed" for r in res.records)
    by_kind = {}
    for r in res.records:
        by_kind.setdefault(r.get("relationship_kind") or r.get("node_kind"), []).append(r)
    assert {"commit", "commit_adds", "renamed_to", "commit_modifies", "commit_deletes", "copied_to"} <= set(by_kind)
    merge_node = next(r for r in nodes if r["from"]["symbol"].endswith(s["merge"]))
    assert "merge_commit" in merge_node["flags"]
    bot = [r for r in res.records if s["bot"] in r["from"]["symbol"]]
    assert bot and all("bot_commit" in r["flags"] for r in bot)
    gen = next(r for r in res.records if r.get("to", {}).get("file") == "web/dist/app.js")
    assert "generated_path" in gen["flags"]
    odd = next(r for r in res.records if "non_utf8_path" in r["flags"])
    assert odd["to"]["file"] == "odd\tname-%FF.py"
    for r in res.records:
        assert r["citations"] and all(len(c["commit"]) == 40 for c in r["citations"])
        assert r["checks"][0]["method"] == "git_object_check" and r["checks"][0]["validator"]["family"] == "git"


def test_facts_deterministic_across_runs(synth: SynthRepo) -> None:
    _build(synth)
    log = ingest(ref(synth), NO_FILTERS)
    a = commit_facts(log, ctx=RunContext("h-1", "2026-10-21T10:00:00+05:30", "synthetic/repo", log.repo.sha))
    b = commit_facts(ingest(ref(synth), NO_FILTERS),
                     ctx=RunContext("h-2", "2026-10-22T11:00:00+05:30", "synthetic/repo", log.repo.sha))
    assert canonical_hash(a.records) == canonical_hash(b.records)
    assert len({r["claim_id"] for r in a.records}) == len(a.records)


def test_replay_equals_ls_tree_with_merge(synth: SynthRepo) -> None:
    _build(synth)
    log = ingest(ref(synth), NO_FILTERS)
    res = lifecycle(log)
    rc = res.report["replay_check"]
    assert rc["replayed_files"] == rc["ls_tree_files"] and not rc["missing_in_replay"] and not rc["extra_in_replay"]


def test_bulk_move_detected_and_observed(synth: SynthRepo) -> None:
    s = _build(synth)
    res = lifecycle(ingest(ref(synth), NO_FILTERS))
    assert assert_valid(res.records)
    (pm,) = [r for r in res.records if r["relationship_kind"] == "prefix_moved"]
    assert (pm["from"]["file"], pm["to"]["file"]) == ("src", "lib")
    assert pm["metrics"]["files"] == 4 and pm["status"] == "observed"
    assert pm["citations"][0]["commit"] == s["move"]


def test_identities_follow_renames_and_split_on_reuse(synth: SynthRepo) -> None:
    s = _build(synth)
    log = ingest(ref(synth), NO_FILTERS)
    with open_runner(log.repo, log.config) as g:
        alive = set(ls_tree_paths(g, log.repo.sha))
    ids = identities(log, alive)
    assert ids.head_path(s["init"], "src/pkg/m1.py") == "lib/pkg/renamed.py"
    assert ids.head_path(s["move"], "lib/pkg/m0.py") == "lib/pkg/m0.py"
    assert ids.head_path(s["init"], "src/pkg/m2.py") is None  # deleted; the later m2.py is a new identity
    assert ids.head_path(s["readd"], "lib/pkg/m2.py") == "lib/pkg/m2.py"
    assert ids.head_path(s["copy"], "lib/pkg/copy.py") == "lib/pkg/copy.py"
    assert ids.head_path(s["init"], "src/pkg/m3.py") == "lib/pkg/m3.py"


def _cmap(sha: str, comps: dict[str, tuple[str, ...]]) -> ComponentMap:
    defs = {cid: ComponentDef(cid, cid.split("::")[-1], "backend", paths, "test-rule") for cid, paths in comps.items()}
    return ComponentMap(sha, defs, "d" * 64)


def test_component_records_are_inferred(synth: SynthRepo) -> None:
    _build(synth)
    log = ingest(ref(synth), NO_FILTERS)
    cm = _cmap(log.repo.sha, {"component::pkg": ("lib/pkg/*",), "component::docs": ("README.md",)})
    res = lifecycle(log, components=cm)
    comp = [r for r in res.records if r["relationship_kind"] == "component_added"]
    assert {r["to"]["symbol"] for r in comp} == {"component::pkg", "component::docs"}
    assert all(r["class"] == "history_inferred" and r["status"] == "unvalidated" for r in comp)
    assert_valid(res.records)


def test_component_map_errors(synth: SynthRepo) -> None:
    _build(synth)
    log = ingest(ref(synth), NO_FILTERS)
    with pytest.raises(HistoryError) as ei:
        lifecycle(log, components=_cmap("0" * 40, {"component::a": ("README.md",)}))
    assert ei.value.code == "E_COMPONENT_MAP"
    with pytest.raises(HistoryError) as ei:
        lifecycle(log, components=_cmap(log.repo.sha, {"component::a": ("README.md",), "component::b": ("README.md",)}))
    assert ei.value.code == "E_COMPONENT_MAP"
