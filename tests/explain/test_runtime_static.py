"""Lab finding O-13: a runtime question about persistence states runtime behavior as unknown first, then cites the
verified or observed static persistence path as a static fact, never as a runtime claim. Lab's question is verbatim."""

from __future__ import annotations

from traces.explain.engine import RUNTIME_UNKNOWN

from .test_explain import rec
from .test_intents import DEP, HANDLER, RECS, run

LAB_RUNTIME = "Does create_item write to the database at runtime?"  # verbatim from ACCEPTANCE.md O-13
OTHER = "api/routes/items.py::update_item"
RUNTIME_WORDS = ("at runtime it", "when called it", "writes to the database", "is executed", "actually runs")


def test_runtime_persistence_question_cites_the_static_path_after_the_unknown() -> None:
    path = next(r for r in RECS if r.get("relationship_kind") == "persistence_path")
    out = run(LAB_RUNTIME)
    assert out["answer"][0] == {"text": RUNTIME_UNKNOWN, "kind": "unknown", "claim_ids": []}
    assert out["answer"][1:] == [
        {
            "text": "The evidence records that create_item has a statically established persistence path through get_db, "
            "at api/routes/items.py:68 (verified).",
            "kind": "fact",
            "claim_ids": [path["claim_id"]],
        }
    ]
    assert [c["claim_id"] for c in out["citations"]] == [path["claim_id"]]
    text = " ".join(a["text"] for a in out["answer"]).lower()
    assert not any(w in text for w in RUNTIME_WORDS)


def test_only_grounded_paths_of_the_named_symbol_are_cited() -> None:
    extra = [
        rec("persistence_path", "unvalidated", HANDLER, "api/crud.py::save", line=70),
        rec("persistence_path", "verified", OTHER, DEP, line=90),
    ]
    out = run(LAB_RUNTIME, records=RECS + extra)
    cited = {i for a in out["answer"] for i in a["claim_ids"]}
    path = next(r for r in RECS if r.get("relationship_kind") == "persistence_path")
    assert cited == {path["claim_id"]}
    assert out["answer"][0]["kind"] == "unknown"
    assert all(a["kind"] == "fact" for a in out["answer"][1:])


def test_no_grounded_path_leaves_only_the_unknown() -> None:
    recs = [r for r in RECS if r.get("relationship_kind") != "persistence_path"]
    recs.append(rec("persistence_path", "unvalidated", HANDLER, DEP, line=68))
    out = run(LAB_RUNTIME, records=recs)
    assert out["answer"] == [{"text": RUNTIME_UNKNOWN, "kind": "unknown", "claim_ids": []}]
    assert out["citations"] == []
