"""History patterns in explain and the chat bundle: co-change is a pattern, never a cause or code structure.

Inputs are generic synthetic records shaped like docs/contracts/history.md section 6 (no fixture names)."""
from __future__ import annotations

from typing import Any

import pytest

from traces.api.models import ExplainResponse
from traces.explain.engine import PATTERN_CAVEAT, explain_records

from .test_explain import FORM, HANDLER, MODEL, RECORDS, SHA, SID, rec

A, B = "file::web/src/Alpha.tsx", "file::web/src/Beta.tsx"
CRITERIA = {"level": "file", "min_revs": 5, "min_shared_revs": 5, "min_coupling": 0.3, "max_changeset_size": 30,
            "commits": "non-merge commits only", "filters": {"bots": "default", "generated": "default"}}
FORBIDDEN = ("causes", "caused", "because", "depends on", "drives", "breaks")


def history(kind: str, status: str, frm: str, to: str | None, cls: str, **extra: Any) -> dict[str, Any]:
    r = rec(kind, status, frm, to, evidence_scope="history", **extra)
    r["class"] = cls
    r["from"]["file"] = frm.removeprefix("file::")
    if to:
        r["to"]["file"] = to.removeprefix("file::")
    r["locations"] = []
    return r


COCHANGE = history("co_changed_with", "observed", A, B, "history_pattern",
                   statement="Alpha.tsx and Beta.tsx changed together in 7 of 9 commits that touched either file.",
                   qualifier="changed together in 7 of 9 commits", granularity="file",
                   parameters={"digest": "0" * 64, "values": CRITERIA},
                   metrics={"support": 7, "revs_a": 8, "revs_b": 8, "union_commits": 9, "degree": 0.875})
HOTSPOT = history("file_history_metrics", "observed", A, None, "history_pattern", claim_kind="node",
                  statement="Alpha.tsx: 8 revisions, 3 authors.", parameters={"values": {"metric_set": "default", "filters": {}}})
ALIAS = history("alias_of", "unvalidated", A, B, "history_inferred", statement="Beta.tsx may be an alias of Alpha.tsx.")
# A pattern record with the wrong label for its status, and one with "verified" pushed onto it by mistake.
BAD = history("co_changed_with", "verified", B, A, "history_pattern", statement="Beta.tsx and Alpha.tsx changed together in 3 of 4 commits.")
HIST = [COCHANGE, HOTSPOT, ALIAS, BAD]
PATTERN_IDS = {r["claim_id"] for r in HIST}

QUESTIONS = ["which files changed together with Alpha?", "co-change history", "what changes with Alpha.tsx and Beta.tsx",
             "Alpha Beta", "hotspots", "trace from Alpha to Beta"]


def run(question: str, mode: str = "no_llm", focus: tuple[str, ...] = ()) -> dict[str, Any]:
    out = explain_records([*RECORDS, *HIST], snapshot_id=SID, sha=SHA, question=question, focus_claim_ids=focus, mode=mode)
    ExplainResponse.model_validate(out)
    return out


@pytest.mark.parametrize("q", QUESTIONS)
def test_cochange_never_in_code_structure_or_inference(q: str) -> None:
    for mode in ("no_llm", "prepare_bundle"):
        cats = run(q, mode)["categories"]
        assert not PATTERN_IDS & set(cats["code_structure"])
        assert not PATTERN_IDS & set(cats["inference"])


@pytest.mark.parametrize("q", [*QUESTIONS, ""])
def test_pattern_sentences_are_patterns_with_caveat_and_criteria_never_fact(q: str) -> None:
    out = run(q, focus=(COCHANGE["claim_id"], BAD["claim_id"]))
    pattern_sentences = [a for a in out["answer"] if PATTERN_IDS & set(a["claim_ids"])]
    assert pattern_sentences
    for a in pattern_sentences:
        assert a["kind"] == "interpretation"
        assert a["text"].startswith("History pattern (")
        assert PATTERN_CAVEAT in a["text"]
        assert "Criteria: " in a["text"]
        assert not a["text"].startswith("History pattern (verified")
        low = a["text"].lower()
        assert not any(w in low for w in FORBIDDEN), a["text"]
    cc = next(a for a in pattern_sentences if a["claim_ids"] == [COCHANGE["claim_id"]])
    for k in ("min_revs=5", "min_shared_revs=5", "min_coupling=0.3", "max_changeset_size=30", "level=\"file\"",
              'filters={"bots":"default","generated":"default"}'):
        assert k in cc["text"], k
    assert "count was checked against Git" in cc["text"]
    bad = next(a for a in pattern_sentences if a["claim_ids"] == [BAD["claim_id"]])
    assert "a history pattern is never verified" in bad["text"]
    # Each citation carries the record's own label; nothing is relabelled verified.
    for c in out["citations"]:
        if c["claim_id"] in PATTERN_IDS:
            src = next(r for r in HIST if r["claim_id"] == c["claim_id"])
            assert (c["status"], c["label"]) == (src["status"], src["label"])


def test_history_patterns_populated_when_history_records_exist() -> None:
    out = run("which files changed together with Alpha?")
    hp = set(out["categories"]["history_patterns"])
    assert COCHANGE["claim_id"] in hp
    assert hp <= PATTERN_IDS
    assert all(a["kind"] != "fact" for a in out["answer"] if PATTERN_IDS & set(a["claim_ids"]))
    hot = run("hotspots")
    assert HOTSPOT["claim_id"] in hot["categories"]["history_patterns"]


def test_history_question_without_history_records_is_unknown() -> None:
    out = explain_records(RECORDS, snapshot_id=SID, sha=SHA, question="which files changed together?")
    assert out["categories"]["history_patterns"] == []
    assert any(a["kind"] == "unknown" and "history patterns" in a["text"] for a in out["answer"])


def test_code_trace_never_walks_a_cochange_edge() -> None:
    # Only a co-change record links the two files; a trace must not present it as a code path.
    out = run("trace from Alpha to Beta")
    assert not any(a["kind"] == "fact" and "recorded path" in a["text"] for a in out["answer"])
    path = run(f"trace from {FORM.split('::')[-1]} to {HANDLER.split('::')[-1]}")
    assert not PATTERN_IDS & {i for a in path["answer"] for i in a["claim_ids"]}
    assert MODEL  # code records still answer as before


def test_chat_bundle_marks_patterns_with_caveat_and_criteria() -> None:
    out = run("which files changed together with Alpha?", mode="prepare_bundle")
    pb = out["prompt_bundle"]
    items = {e["claim_id"]: e for e in pb["evidence"]}
    assert COCHANGE["claim_id"] in items
    e = items[COCHANGE["claim_id"]]
    assert e["category"] == "history_patterns"
    assert e["criteria"] == CRITERIA
    assert (e["status"], e["label"]) == ("observed", "observed")
    assert e["statement"].startswith("History pattern (") and PATTERN_CAVEAT in e["statement"]
    assert "History pattern" in pb["instructions"] and "never present them as a code dependency or a cause" in pb["instructions"]
    assert pb["prompt"].count("<evidence>") == 1
    for i in pb["evidence"]:
        if i["claim_id"] not in PATTERN_IDS:
            assert "category" not in i
