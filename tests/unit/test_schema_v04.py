"""traces-evidence/0.4: generator currency, history record kinds (docs/contracts/history.md examples), status caps,
rejected label and no_source_location flag. Every case is checked by both the stdlib checker and jsonschema."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

from traces.evidence.migrate import SCHEMAS, V03, V04, load_schema
from traces.evidence.schema_check import Validator

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "backend/traces/evidence/schema"
S04 = load_schema(V04)
STD = Validator(S04)
JS = jsonschema.Draft202012Validator(S04, format_checker=jsonschema.FormatChecker())
SHA = "b1125d8839482cb7bbae603ddc6d0081bf87532e"
C1, P1, B1, B2 = "1" * 40, "2" * 40, "3" * 40, "4" * 40
AT = "2026-10-21T15:30:00+05:30"


def ok(rec: dict) -> bool:
    a, b = not STD.errors(rec), JS.is_valid(rec)
    assert a == b, f"validators disagree: stdlib={STD.errors(rec)[:3]} jsonschema={[e.message[:160] for e in JS.iter_errors(rec)][:3]}"
    return a


def check(result="pass", method="git_object_check", family="git"):
    return {"check_id": "k_" + "a" * 64, "method": method, "establishes": "presence", "rule_id": None,
            "validator": {"name": "traces-history-gitcheck", "version": "0.1.0", "family": family},
            "reads_originator_output": False, "independent": True, "inputs": [], "result": result,
            "detail": "diff-tree shows M with the same blobs", "run_id": "h-1", "at": AT}


def commit_modifies() -> dict:
    return {
        "schema_version": V04, "claim_id": "c_" + "5" * 64, "run_id": "h-1",
        "repo": "fastapi/full-stack-fastapi-template", "repo_sha": SHA,
        "claim_kind": "relationship", "relationship_kind": "commit_modifies", "granularity": "file",
        "from": {"entity": "commit", "symbol": f"commit::{C1}"},
        "to": {"entity": "file", "symbol": "file::backend/app/api/routes/users.py", "file": "backend/app/api/routes/users.py"},
        "statement": f"Commit {C1[:12]} modified backend/app/api/routes/users.py (+12 -3).",
        "class": "git_object_fact",
        "originator": {"name": "traces-history", "version": "0.1.0", "role": "history_analyzer"},
        "provenance_raw": {"git": "log --name-status -z -M50%", "status": "M", "added": 12, "deleted": 3},
        "provenance": "git:log",
        "origin": {"kind": "git_object", "commit": C1, "paths": ["backend/app/api/routes/users.py"]},
        "injected": False, "evidence_scope": "history", "qualifier": "git tree change",
        "citations": [{"commit": C1, "parents": [P1], "paths": [{"path": "backend/app/api/routes/users.py", "old_path": None, "status": "M",
                                                                   "similarity": None, "blob_before": B1, "blob_after": B2}]}],
        "locations": [], "checks": [check()], "status": "observed", "label": "observed",
        "status_history": [{"from": None, "to": "unvalidated", "at": AT, "run_id": "h-1", "check_ids": [], "by": "traces-history"},
                           {"from": "unvalidated", "to": "observed", "at": AT, "run_id": "h-1", "check_ids": ["k_" + "a" * 64], "by": "traces-history"}],
        "visible_to_reviewer": True,
        "parameters": {"digest": "e" * 64, "values": {"rename_threshold": 50}}, "flags": [],
        "review_state": {"state": "none", "reviewer": None, "at": None},
    }


def cochange() -> dict:
    r = commit_modifies()
    r.update({"relationship_kind": "co_changed_with", "class": "history_pattern", "provenance": "history:cochange",
              "from": {"entity": "file", "symbol": "file::frontend/src/components/Admin/AddUser.tsx", "file": "frontend/src/components/Admin/AddUser.tsx"},
              "to": {"entity": "file", "symbol": "file::frontend/src/components/Admin/EditUser.tsx", "file": "frontend/src/components/Admin/EditUser.tsx"},
              "statement": "AddUser.tsx and EditUser.tsx changed together in 18 of 19 commits. This is a history pattern, not evidence that one change caused the other.",
              "qualifier": "changed together in 18 of 19 commits",
              "origin": {"kind": "history_derived", "derived_from": [C1]},
              "checks": [check(method="git_recount")],
              "metrics": {"support": 18, "revs_a": 19, "revs_b": 19, "degree": 0.95},
              "parameters": {"digest": "e" * 64, "values": {"min_revs": 5, "min_coupling": 0.3}}})
    return r


def rationale() -> dict:
    r = commit_modifies()
    r.update({"relationship_kind": "documents_rationale", "granularity": "commit", "class": "documented_rationale", "evidence_scope": "documented",
              "from": {"entity": "repo", "symbol": "repo::fastapi/full-stack-fastapi-template#694"},
              "to": {"entity": "commit", "symbol": f"commit::{C1}"},
              "statement": 'PR #694 description says: "When choosing Celery I evaluated RQ..."',
              "qualifier": "quoted rationale, not proof of intent", "provenance": "github-cache:pr-body",
              "origin": {"kind": "cached_pr", "artifact": ".cache/github/prs/694.json", "sha256": "f" * 64, "quote": "When choosing Celery I evaluated RQ..."},
              "checks": [check(method="quote_match", family="text")],
              "citations": [{"commit": C1, "parents": [P1], "paths": [], "pr": {"number": 694, "fetched_at": AT, "merge_commit_sha": C1}}]})
    return r


def test_generator_output_is_committed():
    out = subprocess.run([sys.executable, str(SCHEMA_DIR / "build_v04.py"), "--stdout"], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == json.loads((SCHEMA_DIR / SCHEMAS[V04]).read_text()), "run build_v04.py and commit the schema"


def test_schema_is_valid_draft_2020_12():
    jsonschema.Draft202012Validator.check_schema(S04)
    jsonschema.Draft202012Validator.check_schema(load_schema(V03))


@pytest.mark.parametrize("make", [commit_modifies, cochange, rationale])
def test_history_examples_valid(make):
    assert ok(make())


def mutate(make, fn):
    r = copy.deepcopy(make())
    fn(r)
    return r


NEGATIVE = {
    "git fact verified": (commit_modifies, lambda r: r.update(status="verified", label="verified")),
    "history pattern verified": (cochange, lambda r: r.update(status="verified", label="verified")),
    "history pattern without parameters": (cochange, lambda r: r.pop("parameters")),
    "history record with neither citations nor locations": (commit_modifies, lambda r: r.update(citations=[])),
    "history scope with code class": (commit_modifies, lambda r: r.update({"class": "framework_rule"})),
    "history_inferred observed": (cochange, lambda r: r.update({"class": "history_inferred"})),
    "rationale without quote": (rationale, lambda r: r["origin"].pop("quote")),
    "rationale under history scope": (rationale, lambda r: r.update(evidence_scope="history")),
    "observed history without independent check": (commit_modifies, lambda r: r.update(checks=[])),
    "observed history without qualifier": (commit_modifies, lambda r: r.pop("qualifier")),
    "unknown provenance namespace": (commit_modifies, lambda r: r.update(provenance="gitlog")),
    "file entity without file": (commit_modifies, lambda r: r["to"].pop("file")),
    "review_state promotes": (commit_modifies, lambda r: r.update(review_state={"state": "verified", "reviewer": "x", "at": AT})),
}


@pytest.mark.parametrize("name", sorted(NEGATIVE))
def test_history_negatives_rejected(name):
    make, fn = NEGATIVE[name]
    assert not ok(mutate(make, fn)), name


def test_extension_values_accepted():
    r = mutate(cochange, lambda r: r.update(relationship_kind="x-churn_peer", flags=["x-local"]))
    assert ok(r)


def test_alias_suggestion_unvalidated_inferred_valid():
    r = mutate(cochange, lambda r: r.update({"relationship_kind": "alias_of", "class": "history_inferred", "status": "unvalidated", "label": "inferred",
                                             "status_reason": "suggestion from content similarity", "checks": [],
                                             "status_history": r["status_history"][:1]}))
    assert ok(r)
