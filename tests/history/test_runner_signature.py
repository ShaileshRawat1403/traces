"""Phase 1 of the whole-run entry point: frozen signature, budget shape, stage order (contract section 8.11).

These tests pin the surface the INDEX worker binds to. Changing any of it is a contract change."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from traces.evidence.types import ComponentDef, ComponentMap, EvidenceSet
from traces.history import HistoryConfig, HistoryError, HistoryRepoRef, Thresholds
from traces.history import interface as iface
from traces.history.runner import (
    BUDGET_REASONS,
    FINALIZE_STAGE,
    INPUT_REASONS,
    RUN_REPORT_VERSION,
    STAGE_DEPENDS,
    STAGE_ORDER,
    STAGE_STATUSES,
    TRUNCATION_REASONS,
    GitHistoryRunner,
    RunBudget,
    StageOutcome,
    run,
)

REPO = HistoryRepoRef(Path("/nonexistent"), "o/r", "a" * 40)
P = inspect.Parameter


def _shape(fn: object) -> list[tuple[str, object, object, str]]:
    return [(p.name, p.kind, p.default, str(p.annotation)) for p in inspect.signature(fn).parameters.values()]


def test_run_signature_frozen() -> None:
    e = P.empty
    assert _shape(run) == [
        ("repo", P.POSITIONAL_OR_KEYWORD, e, "HistoryRepoRef"),
        ("config", P.POSITIONAL_OR_KEYWORD, e, "HistoryConfig"),
        ("budget", P.KEYWORD_ONLY, None, "RunBudget | None"),
        ("components", P.KEYWORD_ONLY, None, "ComponentMap | None"),
        ("evidence_sets", P.KEYWORD_ONLY, None, "Mapping[Sha, EvidenceSet] | None"),
        ("pr_provider", P.KEYWORD_ONLY, None, "PrContextProvider | None"),
        ("cache_dir", P.KEYWORD_ONLY, None, "Path | None"),
        ("max_milestones", P.KEYWORD_ONLY, 8, "int"),
        ("run_id", P.KEYWORD_ONLY, None, "str | None"),
        ("at", P.KEYWORD_ONLY, None, "str | None"),
    ]
    assert inspect.signature(run).return_annotation == "HistoryResult"


def test_runner_matches_interface_protocol() -> None:
    proto_run = [(n, k, d) for n, k, d, _ in _shape(iface.HistoryRunner.run)]
    mine_run = [(n, k, d) for n, k, d, _ in _shape(GitHistoryRunner.run)]
    assert mine_run == proto_run
    assert [x[:3] for x in _shape(GitHistoryRunner.select_milestones)] == \
        [x[:3] for x in _shape(iface.HistoryRunner.select_milestones)]
    assert [x[:3] for x in _shape(GitHistoryRunner.__init__)] == [
        ("self", P.POSITIONAL_OR_KEYWORD, P.empty), ("config", P.POSITIONAL_OR_KEYWORD, None),
        ("budget", P.POSITIONAL_OR_KEYWORD, None), ("max_milestones", P.KEYWORD_ONLY, 8)]


def test_budget_shape_and_defaults() -> None:
    b = RunBudget()
    assert b.as_dict() == {"time_s": 600.0, "memory_mb": 1024, "max_records": 250_000, "finalize_reserve_s": 30.0,
                           "on_exhausted": "partial"}
    assert b.validate() is b
    bad = [RunBudget(time_s=0), RunBudget(time_s=float("inf")), RunBudget(memory_mb=0), RunBudget(max_records=-1),
           RunBudget(time_s=10, finalize_reserve_s=10), RunBudget(on_exhausted="ignore"),  # type: ignore[arg-type]
           RunBudget(memory_mb=True)]  # type: ignore[arg-type]
    for x in bad:
        with pytest.raises(HistoryError) as ei:
            x.validate()
        assert ei.value.code == "E_CONFIG"


def test_stage_order_and_reason_sets_frozen() -> None:
    assert STAGE_ORDER == ("ingest", "commit_facts", "lifecycle", "churn", "hotspots", "cochange_file",
                           "cochange_component", "manifests", "reverts", "aliases", "milestones",
                           "snapshot_compare", "evidence_set_diff", "pr_context")
    assert FINALIZE_STAGE == "finalize" and RUN_REPORT_VERSION == "traces-history-run/1"
    assert STAGE_STATUSES == ("completed", "truncated", "skipped", "aborted")
    assert BUDGET_REASONS == {"budget_time", "budget_memory", "budget_records"}
    assert not (BUDGET_REASONS & INPUT_REASONS) and not (BUDGET_REASONS & TRUNCATION_REASONS)
    assert set(STAGE_DEPENDS) == set(STAGE_ORDER)
    for s, deps in STAGE_DEPENDS.items():
        assert all(STAGE_ORDER.index(d) < STAGE_ORDER.index(s) for d in deps)
    assert STAGE_DEPENDS["snapshot_compare"] == ("ingest", "milestones")
    o = StageOutcome("aliases", "skipped", "not_in_v1", "alias suggestions are not in v1", 0)
    assert o.as_dict() == {"stage": "aliases", "status": "skipped", "reason": "not_in_v1",
                           "detail": "alias suggestions are not in v1", "records": 0}


def test_preflight_fails_closed_then_phase2_stub() -> None:
    cfg = HistoryConfig()
    cases = [
        (lambda: run(REPO, cfg, budget=RunBudget(time_s=-1)), "E_CONFIG"),
        (lambda: run(HistoryRepoRef(Path("/x"), "o/r", "A" * 40), cfg), "E_SHA"),
        (lambda: run(REPO, HistoryConfig(thresholds=Thresholds(min_revs=0))), "E_CONFIG"),
        (lambda: run(REPO, cfg, max_milestones=21), "E_CONFIG"),
        (lambda: run(REPO, cfg, max_milestones=1), "E_CONFIG"),
        (lambda: run(REPO, cfg, components=ComponentMap("b" * 40, {}, "d" * 64)), "E_COMPONENT_MAP"),
        (lambda: run(REPO, cfg, components=ComponentMap(REPO.sha, {
            "component::a": ComponentDef("component::a", "a", "backend", ("x.py",), "t"),
            "component::b": ComponentDef("component::b", "b", "backend", ("x.py",), "t")}, "d" * 64)),
         "E_COMPONENT_MAP"),
        (lambda: run(REPO, cfg, evidence_sets={"c" * 40: EvidenceSet("o/r", "d" * 40, "traces-evidence/0.4", [])}),
         "E_EVIDENCE_SET"),
    ]
    for fn, code in cases:
        with pytest.raises(HistoryError) as ei:
            fn()
        assert ei.value.code == code
    with pytest.raises(NotImplementedError):
        run(REPO, cfg)
    with pytest.raises(NotImplementedError):
        GitHistoryRunner().run(REPO)
