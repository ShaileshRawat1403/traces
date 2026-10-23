"""Intent routing for no-key explain (acceptance finding F-7, docs/ACCEPTANCE.md on ws/lab-acceptance).

Lab's failing questions are used verbatim. The records are synthetic and generic: a route handler with a dependency, a
decoy symbol whose name contains the asked name, decoy SDK imports, a persistence path, and Git facts for one commit."""
from __future__ import annotations

from typing import Any

import pytest

from traces.api.models import ExplainResponse
from traces.explain.engine import RUNTIME_UNKNOWN, explain_records
from traces.explain.intents import classify

from .test_explain import SHA, SID, rec

HANDLER = "api/routes/items.py::create_item"
DECOY = "api/tests/utils.py::create_random_item"
DEP = "api/deps.py::get_db"
USER = "api/deps.py::get_current_user"
MODEL = "api/models.py::Item"
SDK = "web/src/client/sdk.gen.ts::ItemsService"
SDK_CALLER = "web/src/client/sdk.gen.ts::ItemsService::createItem"
COMMIT = "9d703df25491" + "0" * 28
OTHER_COMMIT = "1111111" + "2" * 33

FIRST_Q = "What does create_item depend on?"  # verbatim from ACCEPTANCE.md F-7
SECOND_Q = "What changed in commit 9d703df25491?"  # verbatim from ACCEPTANCE.md F-7


def git_fact(kind: str, sha: str, path: str, statement: str) -> dict[str, Any]:
    r = rec(kind, "observed", f"commit::{sha}", f"file::{path}", evidence_scope="history", statement=statement,
            origin={"kind": "git_object", "commit": sha, "paths": [path]})
    r["class"] = "git_object_fact"
    r["from"] = {"entity": "commit", "symbol": f"commit::{sha}"}
    r["to"] = {"entity": "file", "symbol": f"file::{path}", "file": path}
    r["locations"] = []
    return r


RECS = [
    rec("function", "observed", HANDLER, claim_kind="node", line=60),
    rec("depends_on", "verified", HANDLER, DEP, line=63),
    rec("depends_on", "verified", HANDLER, USER, line=63),
    rec("uses_model", "verified", HANDLER, MODEL, line=68),
    rec("persistence_path", "verified", HANDLER, DEP, line=68),
    rec("contains", "verified", "api/routes/items.py::api/routes/items.py", HANDLER, line=60),
    rec("calls", "verified", DECOY, MODEL, line=12),
    rec("calls", "verified", DECOY, DEP, line=13),
    rec("imports", "verified", SDK, "web/src/client/core/request.ts::request", line=1),
    rec("calls", "verified", SDK_CALLER, "web/src/client/core/request.ts::request", line=40),
    rec("calls", "rejected", HANDLER, "api/crud.py::api/crud.py", line=70),
    git_fact("commit_renames", COMMIT, "frontend/src/main.tsx", "Commit 9d703df25491 renamed new-frontend/src/main.tsx to frontend/src/main.tsx."),
    git_fact("commit_modifies", COMMIT, "frontend/package.json", "Commit 9d703df25491 modified frontend/package.json (+2 -2)."),
    git_fact("commit_modifies", OTHER_COMMIT, "api/deps.py", "Commit 1111111 modified api/deps.py (+1 -0)."),
]
IDS = {r["claim_id"]: r for r in RECS}


def run(q: str, focus: list[str] | None = None, records: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    out = explain_records(RECS if records is None else records, snapshot_id=SID, sha=SHA, question=q, focus_claim_ids=focus or [])
    ExplainResponse.model_validate(out)
    return out


def cited_ids(out: dict[str, Any]) -> set[str]:
    return {i for a in out["answer"] for i in a["claim_ids"]}


def symbols(out: dict[str, Any]) -> set[str]:
    return {s for i in cited_ids(out) for s in ((IDS[i].get("from") or {}).get("symbol"), (IDS[i].get("to") or {}).get("symbol")) if s}


def test_lab_dependency_question_lists_the_handlers_own_dependencies() -> None:
    out = run(FIRST_Q)
    syms = symbols(out)
    assert HANDLER in syms and DEP in syms and USER in syms
    assert DECOY not in syms, "create_random_item must not match create_item"
    assert SDK not in syms and SDK_CALLER not in syms, "SDK imports are not create_item's dependencies"
    assert any("create_item depends on get_db" in a["text"] and a["kind"] == "fact" for a in out["answer"])
    assert not any(IDS[i]["status"] == "rejected" for i in cited_ids(out))
    assert not any(IDS[i].get("relationship_kind") == "contains" for i in cited_ids(out))


def test_lab_commit_question_answers_from_that_commit_only() -> None:
    out = run(SECOND_Q)
    ids = cited_ids(out)
    assert ids and all(COMMIT in (IDS[i].get("origin") or {}).get("commit", "") for i in ids)
    assert not any(IDS[i].get("relationship_kind") == "persistence_path" for i in ids)
    assert "frontend/src/main.tsx" in " ".join(a["text"] for a in out["answer"])
    assert set(out["categories"]["code_structure"]).isdisjoint(ids)


def test_commit_question_without_history_is_unknown_not_a_guess() -> None:
    code_only = [r for r in RECS if r.get("evidence_scope") != "history"]
    out = run(SECOND_Q, records=code_only)
    assert [a["kind"] for a in out["answer"]] == ["unknown"]
    assert "no history records" in out["answer"][0]["text"]
    assert out["citations"] == []


@pytest.mark.parametrize("q, intent", [
    (FIRST_Q, "dependencies"),
    (SECOND_Q, "commit"),
    ("What calls get_db?", "dependents"),
    ("Where is create_item used?", "dependents"),
    ("Where is create_item defined?", "definition"),
    ("create_item", "definition"),
    ("trace from create_item to Item", "trace"),
    ("Which routes are declared?", "routes"),
    ("How is an item saved?", "persistence"),
    ("Which files changed together?", "cochange"),
    ("What does the README say?", "docs"),
    ("What are the project dependencies?", "docs"),
    ("Is create_item slow?", "runtime"),
    ("What does create_item do at runtime?", "runtime"),
    ("How fast is the items endpoint in production?", "runtime"),
])
def test_classifier(q: str, intent: str) -> None:
    assert classify(q).name == intent


@pytest.mark.parametrize("q", [
    "What does create depend on?",           # near miss: a prefix of create_item, no symbol of that name
    "What does create_itm depend on?",       # near miss: a typo
    "What does it depend on?",               # no symbol named
    "What changed in the last commit?",      # a commit without a hash
    "What changed in commit 0000000?",       # a hash that is not in the history
    "tell me something interesting",         # no intent
    "items",                                 # a bare word, not a symbol
    "Is this code good?",                    # judgment, unsupported
])
def test_near_misses_are_unknown_with_reason_and_suggestions(q: str) -> None:
    out = run(q)
    assert out["answer"] and all(a["kind"] == "unknown" for a in out["answer"]), out["answer"]
    assert out["citations"] == []
    text = " ".join(a["text"] for a in out["answer"])
    assert "Nothing was guessed" in text and "Try one of" in text


def test_prefix_never_resolves_to_a_longer_name() -> None:
    out = run("What calls create_random?")
    assert all(a["kind"] == "unknown" for a in out["answer"])


@pytest.mark.parametrize("q", ["Is create_item slow?", "What happens at runtime when create_item is called?", "Does get_db crash under load?"])
def test_runtime_questions_are_only_unknown(q: str) -> None:
    out = run(q)
    assert out["answer"] == [{"text": RUNTIME_UNKNOWN, "kind": "unknown", "claim_ids": []}]
    assert out["citations"] == []


def test_ambiguous_symbol_is_unknown() -> None:
    many = [rec("calls", "verified", f"pkg{i}/mod.py::helper", MODEL, line=i + 1) for i in range(5)]
    out = run("What does helper depend on?", records=many)
    assert [a["kind"] for a in out["answer"]] == ["unknown"]
    assert "ambiguous" in out["answer"][0]["text"]


def test_qualified_symbol_disambiguates() -> None:
    many = [rec("calls", "verified", f"pkg{i}/mod.py::helper", MODEL, line=i + 1) for i in range(5)]
    out = run("What does pkg3/mod.py::helper depend on?", records=many)
    assert {IDS_ for a in out["answer"] for IDS_ in a["claim_ids"]} == {many[3]["claim_id"]}


def test_dependents_list_incoming_only() -> None:
    out = run("What calls get_db?")
    froms = {(IDS[i].get("from") or {}).get("symbol") for i in cited_ids(out)}
    assert froms <= {HANDLER, DECOY}
    assert all((IDS[i].get("to") or {}).get("symbol") == DEP for i in cited_ids(out))


def test_focus_claims_still_route_by_schema() -> None:
    dep = next(r for r in RECS if r.get("relationship_kind") == "depends_on")
    out = run("explain", focus=[dep["claim_id"]])
    assert cited_ids(out) == {dep["claim_id"]}
