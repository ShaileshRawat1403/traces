"""Contract test gaps closed after PR #5: HT4 (id recompute), HT12 (combined filters repo), HT21 (rename limit)."""

from __future__ import annotations

import pytest

from traces.history import (
    FilterSpec,
    HistoryConfig,
    HistoryError,
    Thresholds,
    churn,
    cochange,
    commit_facts,
    hotspots,
    ingest,
    lifecycle,
)
from traces.history import records as rec_mod
from traces.history.config import Limits
from traces.history.records import recompute_claim_id

from ._repo import ALICE, BOB, SynthRepo, lines
from ._schema import assert_valid
from .conftest import ref

BOTS = [("dependabot[bot]", "49699333+dependabot[bot]@users.noreply.github.com"),
        ("renovate[bot]", "29139614+renovate[bot]@users.noreply.github.com"),
        ("github-actions[bot]", "41898282+github-actions[bot]@users.noreply.github.com"),
        ("pre-commit-ci[bot]", "66853113+pre-commit-ci[bot]@users.noreply.github.com")]
GENERATED = ["package-lock.json", "src/client/sdk.gen.ts", "dist/app.min.js", "web/dist/app.js", "build/out.o",
             "openapi/schema.ts"]
SOURCE = ["src/app.py", "src/util.py", "distance/calc.py", "rebuild/run.py", "build.py"]
T = Thresholds(min_revs=2, min_shared_revs=2, min_coupling=0.3)


def _ht12_repo(r: SynthRepo) -> None:
    for i in range(3):
        for p in SOURCE:
            r.write(p, "def f():\n" + "".join(f"    x{j} = {i}\n" for j in range(i + 2)))
        for p in GENERATED:
            r.write(p, f"generated {i}\n")
        r.commit(f"human {i}", ALICE if i % 2 == 0 else BOB)
    for k, bot in enumerate(BOTS):
        for p in SOURCE + GENERATED:
            r.write(p, f"bot {k}\n" if not p.endswith(".py") else f"def g():\n    return {k}\n")
        r.commit(f"bot {k}", bot)


def _all_files(res) -> set[str]:  # type: ignore[no-untyped-def]
    out = set()
    for r in res.records:
        for side in ("from", "to"):
            if side in r and "file" in r[side]:
                out.add(r[side]["file"])
    return out


def _cfg(bots: bool = True, gen: bool = True) -> HistoryConfig:
    return HistoryConfig(thresholds=T, filters=FilterSpec(
        extra_generated_paths=frozenset({"openapi/"}), extra_generated_source="evidence:generated_paths",
        exclude_bots_from_patterns=bots, exclude_generated_from_patterns=gen))


def test_ht12_bot_and_generated_filters(synth: SynthRepo) -> None:
    _ht12_repo(synth)
    log = ingest(ref(synth), _cfg())
    ch, hs, cc = churn(log), hotspots(log), cochange(log)
    for res in (ch, hs, cc):
        assert_valid(res.records)
        files = _all_files(res)
        assert not files & set(GENERATED), files & set(GENERATED)
        rem = res.report["filter_removals"]
        assert rem["bot_commits"] == 4 and rem["bot_filter_applied"] is True
        assert sum(rem["bot_commits_by_pattern"].values()) == 4
        rules = rem["generated_changes_by_rule"]
        assert rules["basename package-lock.json"] == 7
        assert rules["basename glob *.gen.*"] == 7 and rules["basename glob *.min.js"] == 7
        assert rules["dir segment dist/"] == 7 and rules["dir segment build/"] == 7
        assert rules["extra_generated_paths dir (evidence:generated_paths)"] == 7
    # whole-segment rule: these are source, not generated
    assert {"distance/calc.py", "rebuild/run.py", "build.py"} <= _all_files(ch)
    # bot commits are excluded from patterns: 3 human revisions per source file
    m = next(r for r in ch.records if r["from"]["file"] == "src/app.py")
    assert m["metrics"]["revisions"] == 3
    # commit facts keep everything, with flags
    facts = commit_facts(log)
    bot_nodes = [r for r in facts.records if r.get("node_kind") == "commit" and "bot_commit" in r["flags"]]
    assert len(bot_nodes) == 4
    gen_facts = {r["to"]["file"] for r in facts.records if "generated_path" in r["flags"] and r.get("to", {}).get("file")}
    assert gen_facts == set(GENERATED)


def test_ht12_turning_filters_off_changes_outputs_and_ids(synth: SynthRepo) -> None:
    _ht12_repo(synth)
    on = ingest(ref(synth), _cfg())
    off_bots = ingest(ref(synth), _cfg(bots=False))
    off_gen = ingest(ref(synth), _cfg(gen=False))
    a = next(r for r in churn(on).records if r["from"]["file"] == "src/app.py")
    b = next(r for r in churn(off_bots).records if r["from"]["file"] == "src/app.py")
    assert b["metrics"]["revisions"] == 7 and a["claim_id"] != b["claim_id"]
    assert set(GENERATED) & _all_files(churn(off_gen))
    ids_on = {r["claim_id"] for r in cochange(on).records}
    ids_off = {r["claim_id"] for r in cochange(off_gen).records}
    assert ids_on and not ids_on & ids_off


def test_ht21_rename_limit_flag(synth: SynthRepo) -> None:
    for i in range(4):
        synth.write(f"old/f{i}.py", lines(30, f"f{i}"))
    synth.commit("init")
    for i in range(4):
        synth.mv(f"old/f{i}.py", f"new/g{i}.py")
        synth.write(f"new/g{i}.py", lines(30, f"f{i}") + "edit\n")
    c2 = synth.commit("inexact renames")
    log = ingest(ref(synth), HistoryConfig(thresholds=Thresholds(rename_limit=1)))
    assert log.by_sha[c2].rename_limited
    assert any("rename detection limited" in w for w in log.warnings)
    facts = commit_facts(log)
    mine = [r for r in facts.records if c2 in r["from"]["symbol"] or c2 in r.get("to", {}).get("symbol", "")]
    assert mine and all("rename_detection_limited" in r["flags"] for r in mine)
    assert_valid(facts.records)
    normal = ingest(ref(synth), HistoryConfig())
    assert not normal.by_sha[c2].rename_limited
    assert sum(c.status == "R" for c in normal.by_sha[c2].changes) == 4


def test_ht21_max_commits_no_records(synth: SynthRepo) -> None:
    for i in range(3):
        synth.write("a.py", f"{i}\n")
        synth.commit(f"c{i}")
    with pytest.raises(HistoryError) as ei:
        ingest(ref(synth), HistoryConfig(limits=Limits(max_commits=2)))
    assert ei.value.code == "E_LIMIT"


def test_ht4_ids_recompute_and_synthetic_cases(synth: SynthRepo, monkeypatch: pytest.MonkeyPatch) -> None:
    _ht12_repo(synth)
    log = ingest(ref(synth), _cfg())
    recs = []
    for fn in (commit_facts, lifecycle, churn, hotspots, cochange):
        recs += list(fn(log).records)
    assert recs
    assert all(recompute_claim_id(r) == r["claim_id"] for r in recs)
    assert len({r["claim_id"] for r in recs}) == len(recs)
    # extractor version is part of the identity
    before = next(r for r in churn(log).records if r["from"]["file"] == "src/app.py")["claim_id"]
    monkeypatch.setitem(rec_mod.EXTRACTOR, "version", "9.9.9")
    after = next(r for r in churn(log).records if r["from"]["file"] == "src/app.py")["claim_id"]
    assert before != after
