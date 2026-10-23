"""Lab findings F-11 (route questions cite the route and the README and manifest evidence), F-8 on JavaScript paths, and
O-12 (directory moves ranked by files moved, then top-level renames first).

Lab's questions are used verbatim. Records are generic synthetic records shaped like the stored ones (route nodes with
route_local_path, dependency_* git facts on dep:: endpoints, co_changed_with and prefix_moved history patterns)."""

from __future__ import annotations

from typing import Any

import pytest

from traces.api.models import ExplainResponse
from traces.explain.engine import PATTERN_CAVEAT, explain_records
from traces.explain.intents import classify

from .test_explain import SHA, SID, rec
from .test_history_patterns import CRITERIA, history

LAB_ROUTE = "What does POST /register do?"
LAB_COCHANGE_JS = "Which files changed together with src/services/user.service.js?"
LAB_MOVE = "When was new-frontend moved to frontend?"
STEP10 = "Commit 9d703df25491 moved 96 files from new-frontend/ to frontend/."

RUNTIME_WORDS = ("sends ", "returns ", "responds", "creates a user", "at runtime it", "when called it")


def route(file: str, line: int, local: str, status: str = "unvalidated") -> dict[str, Any]:
    m, p = local.split(" ", 1)
    return rec(
        "route",
        status,
        f"{file}::{file}::{m}:{p}",
        claim_kind="node",
        line=line,
        provenance_raw={"route_local_path": local},
    )


def dep(kind: str, sha: str, pkg: str, statement: str) -> dict[str, Any]:
    r = rec(
        kind,
        "observed",
        f"commit::{sha}",
        f"dep::npm:package.json:dependencies:{pkg}",
        evidence_scope="history",
        statement=statement,
    )
    r["class"] = "git_object_fact"
    r["locations"] = []
    r["from"] = {"entity": "commit", "symbol": f"commit::{sha}"}
    r["to"] = {"entity": "dependency", "symbol": f"dep::npm:package.json:dependencies:{pkg}"}
    return r


REGISTER = route("src/routes/v1/auth.route.js", 9, "POST /register")
LOGIN = route("src/routes/v1/auth.route.js", 10, "POST /login")
USERS = route("src/routes/v1/user.route.js", 11, "POST /")
MOUNT = route("src/app.js", 50, "USE /v1/auth")
EXPRESS = dep(
    "dependency_added", "a" * 40, "express", "Commit aaaaaaaaaaaa added express ^4.17.1 to package.json (dependencies)."
)
EXPRESS_BUMP = dep(
    "dependency_version_changed",
    "b" * 40,
    "express",
    "Commit bbbbbbbbbbbb changed express in package.json (dependencies) from ^4.17.1 to ^4.18.0.",
)
JEST = dep(
    "dependency_added", "c" * 40, "jest", "Commit cccccccccccc added jest ^26.0.1 to package.json (devDependencies)."
)
OTHER = dep(
    "dependency_added", "d" * 40, "helmet", "Commit dddddddddddd added helmet ^4.1.0 to package.json (dependencies)."
)
STATIC = [REGISTER, LOGIN, USERS, MOUNT]
DEPS = [EXPRESS, EXPRESS_BUMP, JEST, OTHER]
CONTEXT = {"frameworks": ["Express", "Jest"], "readme": ("heading", "RESTful API Node Server Boilerplate")}


def run(
    question: str, records: list[dict[str, Any]], context: dict[str, Any] | None = None, mode: str = "no_llm"
) -> dict[str, Any]:
    out = explain_records(
        records, snapshot_id=SID, sha=SHA, question=question, focus_claim_ids=[], mode=mode, context=context
    )
    ExplainResponse.model_validate(out)
    return out


def ids(out: dict[str, Any]) -> list[str]:
    return [i for a in out["answer"] for i in a["claim_ids"]]


# ------------------------------------------------------------------------------------------------------------ F-11
def test_route_question_is_a_route_intent() -> None:
    assert classify(LAB_ROUTE).name == "route"
    assert classify(LAB_ROUTE).entities == ("POST", "/register")


@pytest.mark.parametrize("mode", ["no_llm", "prepare_bundle"])
def test_route_question_cites_route_readme_and_manifest(mode: str) -> None:
    out = run(LAB_ROUTE, [*STATIC, *DEPS], CONTEXT, mode)
    texts = [a["text"] for a in out["answer"]]
    cited = ids(out)
    assert cited[0] == REGISTER["claim_id"]  # the route claim first
    assert LOGIN["claim_id"] not in cited and USERS["claim_id"] not in cited
    first = out["answer"][0]
    assert (
        first["kind"] == "interpretation" and "src/routes/v1/auth.route.js:9" in first["text"]
    )  # unvalidated: not a fact
    readme = next(a for a in out["answer"] if "README heading" in a["text"])
    assert readme["kind"] == "interpretation" and readme["claim_ids"] == []
    assert (
        "RESTful API Node Server Boilerplate" in readme["text"]
        and "documentation text, not a verified capability" in readme["text"]
    )
    manifests = next(a for a in out["answer"] if a["text"].startswith("Dependency manifests"))
    assert manifests["kind"] == "interpretation" and "Express, Jest" in manifests["text"]
    hist = [a for a in out["answer"] if a["text"].startswith("Manifest history:")]
    assert [a["claim_ids"] for a in hist] == [
        [EXPRESS["claim_id"]],
        [JEST["claim_id"]],
    ]  # added preferred over the bump
    assert all(a["kind"] == "fact" for a in hist)
    assert OTHER["claim_id"] not in cited  # helmet is not a named framework
    assert any(
        a["kind"] == "unknown" and "not established" in a["text"] and "runtime" in a["text"] for a in out["answer"]
    )
    assert not any("no README or manifest records" in t for t in texts)
    for a in out["answer"]:
        if a["kind"] != "unknown":
            assert not any(w in a["text"].lower() for w in RUNTIME_WORDS), a["text"]
    cats = out["categories"]
    assert EXPRESS["claim_id"] not in cats["code_structure"]


def test_route_question_mounted_path_and_no_match() -> None:
    out = run("What does POST /v1/auth/register do?", STATIC, CONTEXT)
    assert ids(out)[0] == REGISTER["claim_id"]
    miss = run("What does DELETE /register do?", STATIC, CONTEXT)
    assert [a["kind"] for a in miss["answer"]] == ["unknown"] and not ids(miss)


def test_docs_question_uses_readme_and_manifests() -> None:
    out = run("What does this project do?", [*STATIC, *DEPS], CONTEXT)
    assert any("README heading" in a["text"] for a in out["answer"])
    assert EXPRESS["claim_id"] in ids(out)
    none = run("What does this project do?", STATIC, {})
    assert [a["kind"] for a in none["answer"]] == ["unknown"]


# ------------------------------------------------------------------------------------------------------------ F-8 JS
def pair(a: str, b: str, support: int, union: int) -> dict[str, Any]:
    return history(
        "co_changed_with",
        "observed",
        f"file::{a}",
        f"file::{b}",
        "history_pattern",
        statement=f"{a} and {b} changed together in {support} of {union} commits that touched either file.",
        qualifier=f"changed together in {support} of {union} commits",
        granularity="file",
        parameters={"values": CRITERIA},
        metrics={"support": support, "union_commits": union, "degree": round(support / union, 4)},
    )


SVC = "src/services/user.service.js"
JS_HIT = [pair(SVC, "src/controllers/user.controller.js", 6, 14), pair("src/services/index.js", SVC, 4, 20)]
JS_DECOY = [
    pair("src/services/auth.service.js", "src/controllers/auth.controller.js", 9, 10),
    *[pair(f"src/m{i}/x.model.js", f"src/m{i}/x.validation.js", 12 - i, 13) for i in range(8)],
]


@pytest.mark.parametrize("q", [LAB_COCHANGE_JS, "Which files changed together with user.service.js?"])
def test_js_dotted_basename_and_src_path(q: str) -> None:
    out = run(q, [*JS_HIT, *JS_DECOY])
    singles = [a["claim_ids"][0] for a in out["answer"] if len(a["claim_ids"]) == 1]
    assert singles == [r["claim_id"] for r in JS_HIT]  # only pairs with user.service.js, by support
    assert not {r["claim_id"] for r in JS_DECOY} & set(ids(out))
    assert all(PATTERN_CAVEAT in a["text"] for a in out["answer"] if a["claim_ids"])


# ------------------------------------------------------------------------------------------------------------ O-12
def move(frm: str, to: str, files: int, sha: str) -> dict[str, Any]:
    return history(
        "prefix_moved",
        "observed",
        f"file::{frm}/",
        f"file::{to}/",
        "history_pattern",
        granularity="path",
        statement=f"Commit {sha} moved {files} files from {frm}/ to {to}/.",
        qualifier=f"grouped renames, {files} files",
        metrics={"files": files},
        provenance_raw={"files": files},
    )


TOP = move("new-frontend", "frontend", 96, "9d703df25491")
INSIDE_A = move("src/new-frontend/src/pages", "src/new-frontend/src", 7, "b470f59ce296")
INSIDE_B = move("src/new-frontend/src/components", "src/new-frontend/src/components/Common", 4, "e44777f91904")
UNRELATED_MOVE = move("backend/app", "backend", 17, "0b473f5b6f75")


def test_move_question_ranks_the_top_level_rename_first() -> None:
    assert classify(LAB_MOVE).entities == ("new-frontend", "frontend")
    out = run(LAB_MOVE, [INSIDE_A, INSIDE_B, TOP, UNRELATED_MOVE])
    singles = [a for a in out["answer"] if len(a["claim_ids"]) == 1]
    assert [a["claim_ids"][0] for a in singles] == [TOP["claim_id"], INSIDE_A["claim_id"], INSIDE_B["claim_id"]]
    assert STEP10 in singles[0]["text"]
    assert UNRELATED_MOVE["claim_id"] not in ids(out)
    assert all(a["kind"] == "interpretation" and PATTERN_CAVEAT in a["text"] for a in out["answer"] if a["claim_ids"])


def test_move_ties_cross_top_level_first_then_claim_id() -> None:
    inner = move("lib/a", "lib/b", 10, "1111111111aa")
    top = move("old", "new", 10, "2222222222bb")
    other = move("x/a", "x/b", 10, "3333333333cc")
    out = run("Which directories were moved?", [inner, other, top])
    singles = [a["claim_ids"][0] for a in out["answer"] if len(a["claim_ids"]) == 1]
    assert singles[0] == top["claim_id"]
    assert singles[1:] == sorted([inner["claim_id"], other["claim_id"]])
    assert singles == [
        a["claim_ids"][0]
        for a in run("Which directories were moved?", [top, inner, other])["answer"]
        if len(a["claim_ids"]) == 1
    ]


def test_move_without_records_or_match_is_unknown() -> None:
    assert [a["kind"] for a in run(LAB_MOVE, STATIC)["answer"]] == ["unknown"]
    out = run("When was docs moved?", [TOP])
    assert [a["kind"] for a in out["answer"]] == ["unknown"] and not ids(out)
