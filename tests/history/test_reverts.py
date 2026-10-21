"""Step 8: reverts and quick deletes (contract sections 6.1, 9.5)."""

from __future__ import annotations

from traces.history import FilterSpec, HistoryConfig, Thresholds, ingest
from traces.history.reverts import reverts

from ._repo import BOT, SynthRepo, lines
from ._schema import assert_valid
from .conftest import ref


def _build(r: SynthRepo) -> dict[str, str]:
    s = {}
    r.write("a.py", lines(5))
    s["base"] = r.commit("base")
    r.write("a.py", lines(6))
    s["feat"] = r.commit("Add feature")
    r.git("revert", "--no-edit", s["feat"])
    s["rev"] = r.head()
    r.write("b.py", "x\n")
    s["title"] = r.commit("Tweak b")
    r.write("b.py", "y\n")
    s["rev_title"] = r.commit('Revert "Tweak b"')
    r.write("c.py", "z\n")
    s["bot"] = r.commit("Bump dep\n\nUpstream notes: This reverts commit deadbeef1234567.", BOT)
    r.write("d.py", "w\n")
    s["unres"] = r.commit('Revert "Something that never happened"')
    # quick deletes: tick is one day per git call; add, rename, delete within a few days
    r.write("tmp/q.py", "q\n")
    s["qa"] = r.commit("add q")
    r.mv("tmp/q.py", "tmp/q2.py")
    r.commit("rename q")
    r.rm("tmp/q2.py")
    s["qd"] = r.commit("drop q")
    r.write("dist/out.js", "o\n")
    r.commit("add generated")
    r.rm("dist/out.js")
    r.commit("drop generated")
    r.write("long.py", "l\n")
    r.commit("add long")
    for i in range(20):
        r.write("filler.py", f"{i}\n")
        r.commit(f"filler {i}")
    r.rm("long.py")
    r.commit("drop long")
    return s


def test_reverts_and_quick_deletes(synth: SynthRepo) -> None:
    s = _build(synth)
    cfg = HistoryConfig(thresholds=Thresholds(quick_delete_days=30))
    res = reverts(ingest(ref(synth), cfg))
    assert_valid(res.records)
    rv = {(r["from"]["symbol"][8:], r["to"]["symbol"][8:]): r for r in res.records if r["relationship_kind"] == "reverts"}
    assert set(rv) == {(s["rev"], s["feat"]), (s["rev_title"], s["title"])}
    body = rv[(s["rev"], s["feat"])]
    assert body["provenance_raw"]["match"] == "body sha"
    assert body["provenance_raw"]["quote"] == f"This reverts commit {s['feat']}"
    assert body["provenance_raw"]["quote"] in ingest(ref(synth), cfg).by_sha[s["rev"]].message
    assert rv[(s["rev_title"], s["title"])]["provenance_raw"]["match"] == "subject title"
    for r in rv.values():
        assert (r["status"], r["class"], r["label"]) == ("unvalidated", "history_inferred", "inferred")
        assert "not established" in r["status_reason"]
    assert res.report["skipped"] == {"bot": 1}
    assert [u["commit"] for u in res.report["unresolved"]] == [s["unres"]]
    qd = [r for r in res.records if r["relationship_kind"] == "deleted_soon_after_add"]
    files = {(r["from"]["file"], r["to"]["file"]) for r in qd}
    assert ("tmp/q.py", "tmp/q2.py") in files
    assert not any("dist/" in f for pair in files for f in pair)        # generated filter
    assert not any("long.py" in f for pair in files for f in pair)      # outside the window
    q = next(r for r in qd if r["from"]["file"] == "tmp/q.py")
    assert q["status"] == "observed" and q["checks"][0]["method"] == "git_recount"
    assert q["qualifier"].startswith("deleted ") and q["qualifier"].endswith(" days after add")
    assert {c["commit"] for c in q["citations"]} == {s["qa"], s["qd"]}
    assert res.report["quick_deletes"]["skipped"].get("generated_paths") == 1


def test_bot_revert_included_when_filter_off(synth: SynthRepo) -> None:
    s = _build(synth)
    res = reverts(ingest(ref(synth), HistoryConfig(filters=FilterSpec(exclude_bots_from_patterns=False))))
    assert s["bot"] in {u["commit"] for u in res.report["unresolved"]}  # abbreviated sha not in history


def test_window_parameter_changes_ids(synth: SynthRepo) -> None:
    _build(synth)
    a = reverts(ingest(ref(synth), HistoryConfig(thresholds=Thresholds(quick_delete_days=30))))
    b = reverts(ingest(ref(synth), HistoryConfig(thresholds=Thresholds(quick_delete_days=200))))
    qa = {r["claim_id"] for r in a.records if r["relationship_kind"] == "deleted_soon_after_add"}
    qb = {r["claim_id"] for r in b.records if r["relationship_kind"] == "deleted_soon_after_add"}
    assert qa and qb and not qa & qb
    wide = {r["from"]["file"] for r in b.records if r["relationship_kind"] == "deleted_soon_after_add"}
    assert "long.py" in wide and len(qb) == len(qa) + 1
