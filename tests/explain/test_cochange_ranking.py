"""Co-change questions answer from the files they name, ranked by support, never from route or code facts (F-8), and
every sentence that cites a history pattern carries the caveat, summaries included (O-4).

Lab's questions are used verbatim. Records are generic synthetic co-change records shaped like docs/contracts/history.md
section 6; the two Lab paths appear only so the verbatim questions have something to resolve."""
from __future__ import annotations

from typing import Any

import pytest

from traces.api.models import ExplainResponse
from traces.explain.engine import MAX_MATCHES, PATTERN_CAVEAT, explain_records
from traces.explain.intents import classify

from .test_explain import SHA, SID, rec
from .test_history_patterns import CRITERIA, history

LAB_ONE = "Which files changed together with backend/app/crud.py?"
LAB_TWO = "What changes with backend/app/crud.py and backend/tests/api/routes/test_users.py?"
LAB_SMALL = "What changes with alpha.py and beta.py?"

HUB = "file::backend/app/crud.py"
PAIR = "file::backend/tests/api/routes/test_users.py"


def pair(a: str, b: str, support: int, union: int, status: str = "observed") -> dict[str, Any]:
    pa, pb = a.removeprefix("file::"), b.removeprefix("file::")
    return history("co_changed_with", status, a, b, "history_pattern",
                   statement=f"{pa} and {pb} changed together in {support} of {union} commits that touched either file.",
                   qualifier=f"changed together in {support} of {union} commits", granularity="file",
                   parameters={"values": CRITERIA},
                   metrics={"support": support, "union_commits": union, "degree": round(support / union, 4)})


# Eight unrelated pairs with high support: the F-8 failure cited these for a crud.py question.
UNRELATED = [pair(f"file::pkg/mod{i}/a.py", f"file::pkg/mod{i}/b.py", 20 - i, 22) for i in range(8)]
TARGET = pair(HUB, PAIR, 5, 26)
HIGH = pair(HUB, "file::backend/app/models.py", 7, 20)
TIE = pair(HUB, "file::backend/app/core/db.py", 5, 10)  # same support as TARGET, higher ratio: ranks above it
SMALL = pair("file::src/alpha.py", "file::src/beta.py", 4, 6)
# Two files share a basename, so "util.py" alone is ambiguous.
AMB = [pair("file::lib/one/util.py", "file::lib/one/x.py", 6, 8), pair("file::lib/two/util.py", "file::lib/two/y.py", 6, 8)]
ROUTES = [rec("route", "verified", f"backend/app/api/routes/users.py::route:GET /users/{i}", claim_kind="node",
              provenance_raw={"route_local_path": f"/users/{i}"}) for i in range(23)]
HISTORY = [*UNRELATED, TARGET, HIGH, TIE, SMALL, *AMB]
PATTERN_IDS = {r["claim_id"] for r in HISTORY}
ROUTE_IDS = {r["claim_id"] for r in ROUTES}


def run(question: str, records: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    out = explain_records([*ROUTES, *HISTORY] if records is None else records, snapshot_id=SID, sha=SHA, question=question,
                          focus_claim_ids=[])
    ExplainResponse.model_validate(out)
    return out


def cited(out: dict[str, Any]) -> list[str]:
    return [i for a in out["answer"] for i in a["claim_ids"]]


def per_pattern(out: dict[str, Any], ids: set[str] = PATTERN_IDS) -> list[str]:
    """Claim ids of the one-record pattern sentences, in answer order."""
    return [a["claim_ids"][0] for a in out["answer"] if len(a["claim_ids"]) == 1 and a["claim_ids"][0] in ids]


@pytest.mark.parametrize("q,files", [
    (LAB_ONE, ("backend/app/crud.py",)),
    (LAB_TWO, ("backend/app/crud.py", "backend/tests/api/routes/test_users.py")),
    (LAB_SMALL, ("alpha.py", "beta.py")),
])
def test_cochange_intent_extracts_named_files(q: str, files: tuple[str, ...]) -> None:
    it = classify(q)
    assert (it.name, it.entities) == ("cochange", files)


def test_named_file_filter_and_support_ranking() -> None:
    out = run(LAB_ONE)
    ids = per_pattern(out)
    assert ids == [HIGH["claim_id"], TIE["claim_id"], TARGET["claim_id"]]  # support, then ratio
    assert not {r["claim_id"] for r in UNRELATED} & set(cited(out))
    assert TARGET["claim_id"] in out["categories"]["history_patterns"]


def test_two_file_question_cites_the_exact_pair_and_no_route_facts() -> None:
    out = run(LAB_TWO)
    assert per_pattern(out) == [TARGET["claim_id"]]
    assert not ROUTE_IDS & set(cited(out))
    assert out["categories"]["code_structure"] == []


def test_small_two_file_question_by_basename() -> None:
    assert per_pattern(run(LAB_SMALL)) == [SMALL["claim_id"]]


def test_ranking_is_deterministic_and_capped() -> None:
    hub = [pair("file::h/hub.py", f"file::h/p{i:02d}.py", 3 + i % 4, 12) for i in range(MAX_MATCHES + 5)]
    out = run("Which files changed together with h/hub.py?", hub)
    hub_ids = {r["claim_id"] for r in hub}
    ids = per_pattern(out, hub_ids)
    assert len(ids) == MAX_MATCHES
    by_id = {r["claim_id"]: r for r in hub}
    keys = [(-by_id[i]["metrics"]["support"], -by_id[i]["metrics"]["degree"], i) for i in ids]
    assert keys == sorted(keys)
    assert ids == per_pattern(run("Which files changed together with h/hub.py?", list(reversed(hub))), hub_ids)
    summary = out["answer"][0]
    assert f"{MAX_MATCHES + 5} recorded co-change patterns" in summary["text"] and f"the top {MAX_MATCHES}" in summary["text"]


@pytest.mark.parametrize("q,why", [
    ("Which files changed together with nowhere/missing.py?", "No stored file is named"),
    ("Which files changed together with util.py?", "ambiguous"),
    ("What changes with backend/app/models.py and src/alpha.py?", "No recorded co-change pattern links"),
])
def test_no_match_or_ambiguity_is_unknown_never_a_fallback(q: str, why: str) -> None:
    out = run(q)
    assert all(a["kind"] == "unknown" for a in out["answer"]), out["answer"]
    assert any(why in a["text"] for a in out["answer"])
    assert not set(cited(out))


def test_no_cochange_records_is_unknown_not_route_facts() -> None:
    for q in (LAB_ONE, LAB_TWO, "Which files changed together?"):
        out = run(q, ROUTES)
        assert [a["kind"] for a in out["answer"]] == ["unknown"]
        assert not ROUTE_IDS & set(cited(out))


@pytest.mark.parametrize("q", [LAB_ONE, LAB_TWO, LAB_SMALL, "Which files changed together?", "co-change history", "hotspots",
                               "Which files changed together with h/hub.py?"])
def test_every_sentence_citing_a_pattern_has_the_caveat_including_summaries(q: str) -> None:
    out = run(q)
    citing = [a for a in out["answer"] if PATTERN_IDS & set(a["claim_ids"])]
    for a in citing:
        assert a["kind"] == "interpretation"
        assert PATTERN_CAVEAT in a["text"], a["text"]
    summaries = [a for a in citing if len(a["claim_ids"]) > 1]
    if q in (LAB_ONE,):
        assert summaries  # the summary sentence exists and was checked above


def test_guard_adds_the_caveat_to_a_summary_that_lacks_it() -> None:
    # A history_inferred record cited through a focus pin: whatever sentence cites it must carry the caveat.
    inferred = history("history_impact_candidate", "unvalidated", HUB, PAIR, "history_inferred", statement="may be affected")
    out = explain_records([*HISTORY, inferred], snapshot_id=SID, sha=SHA, question="", focus_claim_ids=[inferred["claim_id"]])
    for a in out["answer"]:
        if inferred["claim_id"] in a["claim_ids"]:
            assert PATTERN_CAVEAT in a["text"] and a["kind"] == "interpretation"


def test_guard_runs_over_all_sentences() -> None:
    from traces.explain.engine import build_answer

    answer, _, _ = build_answer([*HISTORY], LAB_ONE)
    for a in answer:
        if PATTERN_IDS & set(a["claim_ids"]):
            assert a["text"].count(PATTERN_CAVEAT) >= 1
