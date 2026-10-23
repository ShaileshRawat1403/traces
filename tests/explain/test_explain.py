"""Explain engine tests on generic synthetic records (no fixture names). Collected by the default pytest run (testpaths = tests)"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from traces.api.models import ExplainResponse
from traces.evidence.store import Store
from traces.explain import bundle
from traces.explain.engine import FORBIDDEN_RUNTIME_PHRASES, RUNTIME_UNKNOWN, _fact, explain_records

SHA = "0123456789abcdef0123456789abcdef01234567"
SID = f"github.com__example__app@{SHA}"
_n = 0


def rec(
    kind: str,
    status: str,
    frm: str,
    to: str | None = None,
    *,
    claim_kind: str = "relationship",
    line: int = 1,
    **extra: Any,
) -> dict[str, Any]:
    global _n
    _n += 1
    file = frm.split("::")[0]
    label = {
        "verified": "verified",
        "observed": "observed",
        "unvalidated": "inferred",
        "missing_location": "inferred",
        "rejected": "rejected",
    }[status]
    r: dict[str, Any] = {
        "claim_id": f"c_{_n:064x}",
        "run_id": "t",
        "schema_version": "traces-evidence/0.4",
        "claim_kind": claim_kind,
        "status": status,
        "label": label,
        "class": "analyzer_inference",
        "evidence_scope": "static",
        "injected": False,
        "originator": {"name": "test", "role": "extractor", "version": "0"},
        "flags": [],
        "from": {"symbol": frm, "file": file, "start_line": line, "end_line": line},
        "locations": []
        if status == "missing_location"
        else [{"file": file, "start_line": line, "end_line": line, "role": "site", "range_kind": "site"}],
        "statement": f"{frm} {kind} {to}",
    }
    if claim_kind == "node":
        r["node_kind"] = kind
    else:
        r["relationship_kind"] = kind
        r["to"] = {"symbol": to, "file": (to or "").split("::")[0]}
    r.update(extra)
    return r


FORM = "web/src/Form.tsx::Form"
SUBMIT = "web/src/Form.tsx::Form::onSubmit"
CLIENT = "web/src/client.ts::sendTask"
HANDLER = "api/tasks.py::save_task"
MODEL = "api/models.py::Task"

RECORDS = [
    rec("calls", "verified", FORM, SUBMIT, line=10),
    rec("library_contract", "unvalidated", SUBMIT, CLIENT, line=12, flags=["library_contract"]),
    rec("routes_to", "verified", CLIENT, HANDLER, line=3),
    rec("persistence_path", "verified", HANDLER, MODEL, line=20),
    rec("calls", "rejected", FORM, MODEL, line=11),
    rec(
        "route",
        "observed",
        "api/tasks.py::api/tasks.py::POST:/tasks",
        claim_kind="node",
        line=18,
        provenance_raw={"route_local_path": "POST /tasks"},
    ),
    rec(
        "route",
        "observed",
        "web/src/routes/home.tsx::web/src/routes/home.tsx::route:/",
        claim_kind="node",
        line=5,
        provenance_raw={"route_local_path": "/"},
    ),
    rec("writes", "missing_location", HANDLER, MODEL),
]
IDS = {r["claim_id"]: r for r in RECORDS}
REJECTED = next(r["claim_id"] for r in RECORDS if r["status"] == "rejected")


def run(q: str, focus: list[str] | None = None, mode: str = "no_llm") -> dict[str, Any]:
    out = explain_records(RECORDS, snapshot_id=SID, sha=SHA, question=q, focus_claim_ids=focus or [], mode=mode)
    ExplainResponse.model_validate(out)  # the contract shape
    return out


def grounded_rule(out: dict[str, Any]) -> None:
    """Every fact cites only grounded claims; interpretations that cite claims include an inferred one or summarize; unknowns cite none."""
    for a in out["answer"]:
        statuses = {IDS[c]["status"] for c in a["claim_ids"]}
        if a["kind"] == "fact":
            assert a["claim_ids"], a
            assert statuses <= {"verified", "observed"}, a
        if a["kind"] == "unknown":
            assert a["claim_ids"] == [], a
        assert REJECTED not in a["claim_ids"]
        assert not any(p in a["text"].lower() for p in FORBIDDEN_RUNTIME_PHRASES)


def test_trace_question_walks_the_recorded_path_and_marks_library_steps_inferred() -> None:
    out = run("trace from Form to save_task")
    grounded_rule(out)
    kinds = [a["kind"] for a in out["answer"]]
    assert kinds[0] == "interpretation"  # the path includes an inferred step, so the summary is not a fact
    lib = next(a for a in out["answer"] if "through a library" in a["text"])
    assert lib["kind"] == "interpretation" and lib["text"].startswith("Not established")
    assert out["categories"]["inference"] and out["categories"]["runtime_observations"] == []
    assert REJECTED not in {c["claim_id"] for c in out["citations"]}


def test_no_path_is_unknown() -> None:
    out = run("trace from Task to Form")
    assert out["answer"][0]["kind"] == "unknown"
    grounded_rule(out)


def test_routes_come_from_the_route_inventory() -> None:
    out = run("Which routes are declared?")
    grounded_rule(out)
    assert out["answer"][0]["text"].startswith("The route inventory records 2 declared routes")
    assert any("POST /tasks" in a["text"] for a in out["answer"])


def test_persistence_and_missing_location() -> None:
    out = run("How is a task saved?")
    grounded_rule(out)
    assert any("persistence path" in a["text"] for a in out["answer"])


def test_runtime_questions_are_unknown_first() -> None:
    out = run("Is save_task slow at runtime?")
    assert out["answer"][0] == {"text": RUNTIME_UNKNOWN, "kind": "unknown", "claim_ids": []}
    grounded_rule(out)


def test_documents_absent_is_unknown() -> None:
    out = run("What does the README say?")
    assert [a["kind"] for a in out["answer"]] == ["unknown"]


def test_focus_claims_rejected_and_missing() -> None:
    out = run("explain", [REJECTED, "c_missing"])
    assert all(a["kind"] == "unknown" for a in out["answer"])
    assert out["citations"] == []


def test_general_match_is_deterministic_and_cited() -> None:
    a, b = run("sendTask"), run("sendTask")
    assert a == b
    grounded_rule(a)
    assert a["citations"] and all(c["commit"] == SHA for c in a["citations"])


def test_bundle_manifest_matches_prompt_and_has_no_keys() -> None:
    out = run("trace from Form to save_task", mode="prepare_bundle")
    pb, man = out["prompt_bundle"], out["outbound_manifest"]
    assert out["requires_consent"] is True
    assert [m["kind"] for m in man][0] == "instructions" and man[-1]["kind"] == "question"
    assert {m["claim_id"] for m in man if m["kind"] == "claim_statement"} == {c["claim_id"] for c in out["citations"]}
    for e in pb["evidence"]:
        assert e["statement"] in pb["prompt"]
    text = repr(pb).lower()
    assert "api_key" not in text and "authorization" not in text
    assert "data, not instructions" in pb["instructions"]


def test_template_guard_rejects_runtime_language() -> None:
    with pytest.raises(ValueError):
        _fact("At runtime it calls the database.", "fact", ["c_1"])


def test_store_entry_points(tmp_path: Path) -> None:
    st = Store(tmp_path / "t.sqlite3")
    st.upsert_repo("github.com__example__app", "github.com", "example", "app", "https://github.com/example/app")
    st.upsert_snapshot("github.com__example__app", SHA, "ready")
    st.db.execute("INSERT OR IGNORE INTO runs (run_id) VALUES ('t')") if _has_runs(st) else None
    st.put_claims(SID, RECORDS)
    out = bundle.explain(SID, "trace from Form to save_task", [], store=st)
    ExplainResponse.model_validate(out)
    assert out["citations"]
    pb = bundle.prompt_bundle(SID, "trace from Form to save_task", [], store=st)
    assert pb["prompt_bundle"] and pb["outbound_manifest"]
    with pytest.raises(LookupError):
        bundle.explain("nope@" + SHA, "x", [], store=st)


def _has_runs(st: Store) -> bool:
    cols = [r[1] for r in st.db.execute("PRAGMA table_info(runs)")]
    return cols == ["run_id"]
