"""Alias suggestions (contract 6.1, 8.8, 12, 17; D-H4; HT13, HT24, HT15 ceilings)."""

from __future__ import annotations

import pytest

from traces.history import HistoryConfig, HistoryError, Thresholds, ingest
from traces.history.aliases import alias_suggestions, review_wording, set_review_state
from traces.history.records import RunContext, canonical_hash, recompute_claim_id

from ._repo import SynthRepo
from ._schema import assert_valid
from .conftest import ref

CTX = RunContext("h-test", "2026-10-21T12:00:00+05:30", "t/synth", "0" * 40)


def body(tag: str, n: int) -> str:
    return "".join(f"def {tag}_{i}(x):\n    return x + {i}  # {tag}\n" for i in range(n))


def _build(r: SynthRepo) -> dict[str, str]:
    s = {}
    r.write("pkg/crud/user.py", body("user", 8))
    r.write("pkg/crud/item.py", body("item", 6))
    r.write("pkg/other.py", body("other", 5))
    r.write("logo.bin", b"\x00\x01\x02" * 200)
    r.write("dist/bundle.js", body("bundle", 8))
    s["c0"] = r.commit("init")
    # merge two files into one with heavy edits: Git sees D, D, A (no rename at 50%)
    r.rm("pkg/crud/user.py")
    r.rm("pkg/crud/item.py")
    r.write("pkg/crud.py", body("user", 8) + body("item", 3) + body("new", 20))
    s["merge"] = r.commit("fold crud package into crud.py")
    # a plain rename Git detects: no alias suggestion
    r.mv("pkg/other.py", "pkg/renamed.py")
    s["rename"] = r.commit("rename other")
    # unrelated delete plus add: no suggestion
    r.rm("pkg/renamed.py")
    r.write("pkg/fresh.py", body("fresh", 9))
    s["unrelated"] = r.commit("replace renamed with fresh")
    # binary and generated deletes paired with similar adds are ignored
    r.rm("logo.bin")
    r.write("logo2.bin", b"\x00\x01\x02" * 199 + b"\x09")
    r.rm("dist/bundle.js")
    r.write("dist/bundle2.js", body("bundle", 8) + body("x", 30))
    s["skip"] = r.commit("binary and generated")
    return s


def test_ht13_style_suggestions_are_inferred_unvalidated(synth: SynthRepo) -> None:
    s = _build(synth)
    log = ingest(ref(synth), HistoryConfig())
    res = alias_suggestions(log, ctx=CTX)
    assert_valid(res.records)
    pairs = {(r["from"]["file"], r["to"]["file"]): r for r in res.records}
    assert set(pairs) == {("pkg/crud/user.py", "pkg/crud.py"), ("pkg/crud/item.py", "pkg/crud.py")}
    u = pairs[("pkg/crud/user.py", "pkg/crud.py")]
    assert u["relationship_kind"] == "alias_of" and u["class"] == "history_inferred"
    assert u["status"] == "unvalidated" and u["label"] == "inferred" and u["checks"] == []
    assert u["status_reason"] == "suggestion from content similarity; identity not established by Git"
    assert u["provenance"] == "history:alias-suggest" and u["evidence_scope"] == "history"
    assert u["metrics"]["line_containment"] == 1.0 and u["metrics"]["method"] == "normalized line-set overlap"
    assert pairs[("pkg/crud/item.py", "pkg/crud.py")]["metrics"]["line_containment"] == 0.5
    assert u["citations"][0]["commit"] == s["merge"] and u["provenance_raw"]["head_to"] == "pkg/crud.py"
    assert u["statement"].startswith("Suggested alias: content of pkg/crud/user.py appears to continue in pkg/crud.py")
    assert u["review_state"] == {"state": "none", "reviewer": None, "at": None}
    assert all(recompute_claim_id(r) == r["claim_id"] for r in res.records)
    again = alias_suggestions(ingest(ref(synth), HistoryConfig()),
                              ctx=RunContext("h-2", "2026-10-22T09:00:00+05:30", CTX.repo, CTX.repo_sha))
    assert canonical_hash(again.records) == canonical_hash(res.records)


def test_threshold_changes_outcome_and_ids(synth: SynthRepo) -> None:
    _build(synth)
    base = alias_suggestions(ingest(ref(synth), HistoryConfig()), ctx=CTX)
    strict = alias_suggestions(ingest(ref(synth), HistoryConfig(thresholds=Thresholds(alias_min_similarity=0.6))),
                               ctx=CTX)
    assert len(strict.records) == 1 and strict.records[0]["from"]["file"] == "pkg/crud/user.py"
    assert strict.records[0]["claim_id"] not in {r["claim_id"] for r in base.records}


def test_pairs_cap_skips_and_counts(synth: SynthRepo, monkeypatch: pytest.MonkeyPatch) -> None:
    _build(synth)
    import traces.history.aliases as A
    monkeypatch.setattr(A, "MAX_PAIRS_PER_COMMIT", 1)
    res = alias_suggestions(ingest(ref(synth), HistoryConfig()), ctx=CTX)
    assert res.records == [] and res.report["skipped"]["pairs_over_cap"] >= 1


def test_ht24_review_state_helper(synth: SynthRepo) -> None:
    _build(synth)
    rec = alias_suggestions(ingest(ref(synth), HistoryConfig()), ctx=CTX).records[0]
    assert review_wording(rec) == "suggested, not confirmed"
    c = set_review_state(rec, "confirmed", reviewer="shailesh", at="2026-10-21T17:00:00+05:30", note="checked")
    d = set_review_state(c, "disputed", reviewer="arch1", at="2026-10-21T18:00:00+05:30")
    for x in (c, d):
        assert_valid([x])
        for k in ("status", "label", "class", "claim_id", "status_history", "checks"):
            assert x[k] == rec[k]
        assert recompute_claim_id(x) == rec["claim_id"]
    assert review_wording(c) == "confirmed by shailesh" and review_wording(d) == "disputed by arch1"
    assert rec["review_state"]["state"] == "none"  # input untouched
    assert set_review_state(d, "none", reviewer=None, at=None)["review_state"] == rec["review_state"]
    for bad in (("maybe", "x", "2026-10-21T17:00:00+05:30"), ("confirmed", None, "2026-10-21T17:00:00+05:30"),
                ("confirmed", "x", "2026-10-21T17:00:00"), ("disputed", "x", "yesterday")):
        with pytest.raises(HistoryError) as ei:
            set_review_state(rec, bad[0], reviewer=bad[1], at=bad[2])
        assert ei.value.code == "E_CONFIG"
