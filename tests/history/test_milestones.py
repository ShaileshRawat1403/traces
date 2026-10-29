"""Step 9: milestones, snapshot compare, evidence-set diff (contract sections 8.3, 9.7, 9.8; HT19, HT22)."""

from __future__ import annotations

import json

import pytest

from traces.evidence.types import EvidenceSet
from traces.history import HistoryConfig, HistoryError, ingest
from traces.history.milestones import evidence_set_diff, milestone_records, select_milestones, snapshot_compare

from ._repo import BOT, SynthRepo, lines
from ._schema import assert_valid
from .conftest import ref


def _pkg(deps: dict) -> str:
    return json.dumps({"name": "w", "dependencies": deps})


def _build(r: SynthRepo) -> dict[str, str]:
    s = {}
    for i in range(3):
        r.write(f"src/m{i}.py", lines(10, f"m{i}"))
    r.write("package.json", _pkg({"a": "1"}))
    s["first"] = r.commit("first")
    for i in range(10):
        r.write("work.py", lines(11 + i, "w"))
        r.commit(f"work {i}")
    r.checkout("-b", "feat")
    r.write("package.json", _pkg({"a": "1", "b": "2"}))
    s["side_dep"] = r.commit("add b on a branch")
    r.checkout("main")
    r.write("docs/x.md", "x\n")
    r.commit("docs")
    s["merge"] = r.merge("feat")
    for i in range(3):
        r.mv(f"src/m{i}.py", f"lib/m{i}.py")
    s["move"] = r.commit("move src to lib")
    r.write("lib/m1.py", lines(12, "m1"))
    s["bot"] = r.commit("bot edit", BOT)
    r.write("package.json", _pkg({"a": "1", "b": "2", "c": "3"}))
    s["bot_dep"] = r.commit("bot adds c", BOT)
    r.write("lib/m2.py", lines(13, "m2"))
    s["oops"] = r.commit("oops")
    r.git("revert", "--no-edit", s["oops"])
    s["revert"] = r.head()
    for i in range(25):  # cross a calendar year (two ticks per commit)
        r.write("src2.py", f"{i}\n")
        r.commit(f"filler {i}")
    s["head"] = r.head()
    return s


def test_ht22_milestones(synth: SynthRepo) -> None:
    s = _build(synth)
    log = ingest(ref(synth), HistoryConfig())
    a = select_milestones(log)
    assert a == select_milestones(log)
    fp = set(log.first_parent)
    assert all(m.sha in fp and m.reasons for m in a)
    shas = [m.sha for m in a]
    assert shas[0] == s["first"] and shas[-1] == s["head"] and len(a) <= 8
    reasons = {m.sha: m.reasons for m in a}
    assert any(r.startswith("dependency change: +b") for r in reasons.get(s["merge"], ()))  # side branch -> merge
    assert any(r.startswith("bulk move 3 files: src -> lib") for r in reasons[s["move"]])
    assert s["bot"] not in reasons
    assert s["side_dep"] not in reasons  # not on the first-parent chain
    big = select_milestones(log, max_milestones=20)
    assert len(big) <= 20 and set(shas) <= {m.sha for m in big}
    assert any(r.startswith("last first-parent commit of") for m in big for r in m.reasons)
    assert any(r.startswith("explicit revert of") for m in big for r in m.reasons)
    assert any(r.startswith("dependency change: +c") for r in {m.sha: m.reasons for m in big}.get(s["bot_dep"], ()))
    for bad in (21, 1, 0):
        with pytest.raises(HistoryError) as ei:
            select_milestones(log, max_milestones=bad)
        assert ei.value.code == "E_CONFIG"
    recs = milestone_records(log, a)
    assert_valid(recs.records)
    assert all(r["status"] == "observed" and r["qualifier"].startswith("selected milestone: ") for r in recs.records)


def test_snapshot_compare(synth: SynthRepo) -> None:
    s = _build(synth)
    log = ingest(ref(synth), HistoryConfig())
    res = snapshot_compare(log, s["first"], s["head"])
    assert_valid(res.records)
    rep = res.report
    assert rep["renamed"] == 3 and rep["added"] == 3 and rep["removed"] == 0  # docs/x.md, src2.py, work.py
    assert {r["to"]["file"] for r in res.records} == {"docs/x.md", "src2.py", "work.py"}
    assert all(r["status"] == "observed" and r["class"] == "snapshot_diff" for r in res.records)
    with pytest.raises(HistoryError) as ei:
        snapshot_compare(log, "0" * 40, s["head"])
    assert ei.value.code == "E_SHA"


def _rec(sha: str, cid: str, kind: str, frm: tuple[str, str, int], to: tuple[str, str, int], status: str = "observed") -> dict:
    def ep(t: tuple[str, str, int]) -> dict:
        return {"symbol": f"{t[0]}::{t[1]}", "file": t[0], "start_line": t[2], "end_line": t[2] + 3}
    return {"schema_version": "traces-evidence/0.4", "claim_id": cid, "repo_sha": sha, "claim_kind": "relationship",
            "relationship_kind": kind, "granularity": "symbol", "from": ep(frm), "to": ep(to),
            "statement": f"{frm[1]} {kind} {to[1]}", "status": status}


def test_ht19_evidence_set_diff(synth: SynthRepo) -> None:
    s = _build(synth)
    log = ingest(ref(synth), HistoryConfig())
    b, h = s["first"], s["head"]
    base = EvidenceSet("synthetic/repo", b, "traces-evidence/0.4", [
        _rec(b, "c_moved_a", "calls", ("src/m0.py", "f", 1), ("src/m1.py", "g", 5)),            # moves lines + file renames
        _rec(b, "c_gone", "calls", ("src/m0.py", "f", 1), ("src/m2.py", "h", 2)),               # removed
        _rec(b, "c_rej_a", "imports", ("src/m1.py", "x", 1), ("src/m2.py", "y", 1), "rejected"),  # rejected at both
        _rec(b, "c_weak_a", "imports", ("src/m2.py", "p", 1), ("src/m0.py", "q", 1), "unvalidated"),
    ])
    head = EvidenceSet("synthetic/repo", h, "traces-evidence/0.4", [
        _rec(h, "c_moved_b", "calls", ("lib/m0.py", "f", 40), ("lib/m1.py", "g", 90)),
        _rec(h, "c_new", "calls", ("lib/m1.py", "g", 9), ("lib/m2.py", "h", 3), "verified"),      # added
        _rec(h, "c_rej_b", "imports", ("lib/m1.py", "x", 7), ("lib/m2.py", "y", 7), "rejected"),
        _rec(h, "c_rej_new", "imports", ("lib/m0.py", "z", 7), ("lib/m2.py", "y", 7), "rejected"),  # rejected only
    ])
    res = evidence_set_diff(base, head, log=log)
    assert_valid(res.records)
    kinds = sorted((r["relationship_kind"], r["provenance_raw"]["underlying_claim_ids"][0], r["status"]) for r in res.records)
    assert kinds == [("snapshot_added", "c_new", "observed"),
                     ("snapshot_removed", "c_gone", "observed"),
                     ("snapshot_removed", "c_weak_a", "unvalidated")]
    assert res.report["matched"] == 1 and res.report["renames_mapped"] == 3
    assert res.report["rejected_ignored"] == {"base": 1, "head": 2} and res.report["recount_agrees"] is True
    added = next(r for r in res.records if r["relationship_kind"] == "snapshot_added")
    assert added["metrics"] == {"underlying_status_a": None, "underlying_status_b": "verified"}
    assert added["qualifier"] == f"present at {h[:12]}, absent at {b[:12]}"
    assert "start_line" not in added["from"]


def test_evidence_set_diff_aliases_and_errors(synth: SynthRepo) -> None:
    s = _build(synth)
    log = ingest(ref(synth), HistoryConfig())
    b, h = s["first"], s["head"]
    base = EvidenceSet("synthetic/repo", b, "traces-evidence/0.4",
                       [_rec(b, "c1", "calls", ("package.json", "a", 1), ("src/m0.py", "f", 1))])
    head = EvidenceSet("synthetic/repo", h, "traces-evidence/0.4",
                       [_rec(h, "c2", "calls", ("pkg.json", "a", 1), ("lib/m0.py", "f", 1))])
    assert len(evidence_set_diff(base, head, log=log).records) == 2
    alias = {"relationship_kind": "alias_of", "from": {"file": "package.json"}, "to": {"file": "pkg.json"},
             "review_state": {"state": "confirmed"}}
    res = evidence_set_diff(base, head, log=log, aliases=[alias])
    assert res.records == [] and res.report["aliases_applied"] == 1
    unconfirmed = dict(alias, review_state={"state": "none"})
    assert len(evidence_set_diff(base, head, log=log, aliases=[unconfirmed]).records) == 2
    old = EvidenceSet("synthetic/repo", b, "traces-evidence/0.3", [])
    wrong = EvidenceSet("synthetic/repo", b, "traces-evidence/0.4", [_rec(h, "c3", "calls", ("a", "b", 1), ("c", "d", 1))])
    for bad in (old, wrong, EvidenceSet("other/repo", b, "traces-evidence/0.4", [])):
        with pytest.raises(HistoryError) as ei:
            evidence_set_diff(bad, head, log=log)
        assert ei.value.code == "E_EVIDENCE_SET"
