"""Whole-run entry point for the INDEX job's 'history' step (docs/contracts/history.md section 8.11).

PHASE 1: the signature, budget shape, stage order, partial-result flags and report layout are frozen here so the
index worker can bind to them. `run()` validates its inputs (fail closed) and then raises NotImplementedError; the
stage pipeline lands in phase 2 without changing anything in this file's public surface.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

from traces.evidence.types import ComponentMap, EvidenceSet, Sha

from .config import MAX_MILESTONES_DEFAULT, MAX_MILESTONES_ON_DEMAND, HistoryConfig
from .errors import E_CONFIG, E_EVIDENCE_SET, E_SHA, HistoryError
from .interface import HistoryRepoRef, HistoryResult, Milestone, PrContextProvider
from .shapes import validate_component_map

RUN_REPORT_VERSION: Final = "traces-history-run/1"

# Fixed stage order (section 8.11). Never reordered by inputs, config or budget.
STAGE_ORDER: Final[tuple[str, ...]] = (
    "ingest",               # HistoryLog (cache aware)
    "commit_facts",
    "lifecycle",            # component outputs only with a component map
    "churn",
    "hotspots",
    "cochange_file",
    "cochange_component",   # needs a component map
    "manifests",
    "reverts",              # reverts and quick deletes
    "aliases",              # alias_suggestions (8.8); not in v1, always skipped with reason not_in_v1
    "milestones",           # select_milestones(max_milestones) and milestone records
    "snapshot_compare",     # consecutive milestone pairs, oldest first
    "evidence_set_diff",    # consecutive milestone pairs that both have an evidence set
    "pr_context",           # needs a provider
)
FINALIZE_STAGE: Final = "finalize"  # always runs: cross-stage E_COLLISION, E_SCHEMA, sort, records digest

StageStatus = Literal["completed", "truncated", "skipped", "aborted"]
STAGE_STATUSES: Final[tuple[str, ...]] = ("completed", "truncated", "skipped", "aborted")

# Reasons a stage did not complete in full. Budget reasons make the run partial; the others do not.
BUDGET_REASONS: Final[frozenset[str]] = frozenset({"budget_time", "budget_memory", "budget_records"})
INPUT_REASONS: Final[frozenset[str]] = frozenset({
    "no_component_map", "no_evidence_sets", "no_pr_provider", "not_in_v1", "too_few_milestones",
    "dependency_not_completed"})
TRUNCATION_REASONS: Final[frozenset[str]] = frozenset({
    "milestone_cap", "rename_detection_limited", "evidence_sets_missing_for_some_milestones",
    "pr_data_missing_for_some_prs"})
STAGE_REASONS: Final[frozenset[str]] = BUDGET_REASONS | INPUT_REASONS | TRUNCATION_REASONS

# Stage dependencies: a stage whose dependency did not complete (or only truncated is fine) is skipped with
# reason dependency_not_completed. Every stage needs ingest.
STAGE_DEPENDS: Final[Mapping[str, tuple[str, ...]]] = {
    "ingest": (),
    **{s: ("ingest",) for s in STAGE_ORDER[1:] if s not in ("snapshot_compare", "evidence_set_diff")},
    "snapshot_compare": ("ingest", "milestones"),
    "evidence_set_diff": ("ingest", "milestones"),
}


@dataclass(frozen=True)
class RunBudget:
    """Resource budget for one run() call (section 8.11, budget semantics).

    time_s: wall-clock seconds on a monotonic clock from run() entry, git subprocess time included.
    memory_mb: growth of the calling process's resident set size over its value at run() entry, in MiB.
    max_records: total records across stages (finalize counts all kept stages).
    finalize_reserve_s: time kept back for finalize; a stage does not start when less than this remains.
    on_exhausted: "partial" returns completed stages with the run flagged partial; "fail" raises E_TIMEOUT (time)
        or E_LIMIT (memory, records) and publishes nothing.
    """

    time_s: float = 600.0
    memory_mb: int = 1024
    max_records: int = 250_000
    finalize_reserve_s: float = 30.0
    on_exhausted: Literal["partial", "fail"] = "partial"

    def validate(self) -> RunBudget:
        for name in ("time_s", "finalize_reserve_s"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
                raise HistoryError(E_CONFIG, f"budget.{name} must be a finite number > 0", "budget")
        if self.finalize_reserve_s >= self.time_s:
            raise HistoryError(E_CONFIG, "budget.finalize_reserve_s must be below budget.time_s", "budget")
        for name in ("memory_mb", "max_records"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < 1:
                raise HistoryError(E_CONFIG, f"budget.{name} must be a positive integer", "budget")
        if self.on_exhausted not in ("partial", "fail"):
            raise HistoryError(E_CONFIG, "budget.on_exhausted must be 'partial' or 'fail'", "budget")
        return self

    def as_dict(self) -> dict[str, object]:
        return {"time_s": self.time_s, "memory_mb": self.memory_mb, "max_records": self.max_records,
                "finalize_reserve_s": self.finalize_reserve_s, "on_exhausted": self.on_exhausted}


@dataclass(frozen=True)
class StageOutcome:
    """One entry of report["stages"], in STAGE_ORDER. `records` counts the records kept from this stage (0 unless
    completed or truncated). `reason` is None only for completed. `detail` is plain text, no paths outside the repo."""

    stage: str
    status: StageStatus
    reason: str | None
    detail: str
    records: int

    def as_dict(self) -> dict[str, object]:
        return {"stage": self.stage, "status": self.status, "reason": self.reason, "detail": self.detail,
                "records": self.records}


def _validate_inputs(repo: HistoryRepoRef, config: HistoryConfig, budget: RunBudget,
                     components: ComponentMap | None, evidence_sets: Mapping[Sha, EvidenceSet] | None,
                     max_milestones: int) -> None:
    """Preflight, fail closed. Git-level checks (E_REPO, E_SHA via rev-parse, E_SHALLOW, E_GIT_VERSION) run at the
    start of the ingest stage in phase 2 and are errors, never partial results."""
    if not isinstance(repo, HistoryRepoRef):
        raise HistoryError(E_CONFIG, "repo must be a HistoryRepoRef", "preflight")
    if not isinstance(repo.sha, str) or len(repo.sha) != 40 or any(c not in "0123456789abcdef" for c in repo.sha):
        raise HistoryError(E_SHA, "repo.sha must be 40 lowercase hex", "preflight")
    if not isinstance(config, HistoryConfig):
        raise HistoryError(E_CONFIG, "config must be a HistoryConfig", "preflight")
    config.validate()
    if not isinstance(budget, RunBudget):
        raise HistoryError(E_CONFIG, "budget must be a RunBudget", "preflight")
    budget.validate()
    if isinstance(max_milestones, bool) or not isinstance(max_milestones, int) \
            or not 2 <= max_milestones <= MAX_MILESTONES_ON_DEMAND:
        raise HistoryError(E_CONFIG, f"max_milestones must be between 2 and {MAX_MILESTONES_ON_DEMAND}", "preflight")
    if components is not None:
        validate_component_map(components, repo.sha, "preflight")
    if evidence_sets is not None:
        if not isinstance(evidence_sets, Mapping):
            raise HistoryError(E_EVIDENCE_SET, "evidence_sets must map SHA -> EvidenceSet", "preflight")
        for sha, es in evidence_sets.items():
            if not isinstance(es, EvidenceSet) or es.sha != sha:
                raise HistoryError(E_EVIDENCE_SET, "each evidence set must be an EvidenceSet keyed by its own sha",
                                   "preflight")


def run(repo: HistoryRepoRef, config: HistoryConfig, *,
        budget: RunBudget | None = None,
        components: ComponentMap | None = None,
        evidence_sets: Mapping[Sha, EvidenceSet] | None = None,
        pr_provider: PrContextProvider | None = None,
        cache_dir: Path | None = None,
        max_milestones: int = MAX_MILESTONES_DEFAULT,
        run_id: str | None = None,
        at: str | None = None) -> HistoryResult:
    """Run every history stage in STAGE_ORDER under `budget` and return all records plus the run report
    (section 8.11). Phase 1: validates inputs (fail closed), then raises NotImplementedError."""
    _validate_inputs(repo, config, budget or RunBudget(), components, evidence_sets, max_milestones)
    raise NotImplementedError("history run(): phase 2 (stage pipeline) not implemented yet")


class GitHistoryRunner:
    """Concrete runner for hook H1. Satisfies interface.HistoryRunner: config, budget and the milestone cap are fixed
    at construction so the worker's select_milestones() and run() calls agree on milestone SHAs."""

    def __init__(self, config: HistoryConfig | None = None, budget: RunBudget | None = None, *,
                 max_milestones: int = MAX_MILESTONES_DEFAULT) -> None:
        self.config = config or HistoryConfig()
        self.budget = budget or RunBudget()
        self.max_milestones = max_milestones

    def select_milestones(self, repo: HistoryRepoRef, *, max_milestones: int = MAX_MILESTONES_DEFAULT,
                          components: ComponentMap | None = None) -> tuple[Milestone, ...]:
        """Phase 1 stub. Phase 2: ingest (cache_dir from the last run() or none) then milestones.select_milestones."""
        raise NotImplementedError("history select_milestones() via runner: phase 2")

    def run(self, repo: HistoryRepoRef, *, components: ComponentMap | None = None,
            evidence_sets: Mapping[Sha, EvidenceSet] | None = None,
            pr_provider: PrContextProvider | None = None, cache_dir: Path | None = None) -> HistoryResult:
        return run(repo, self.config, budget=self.budget, components=components, evidence_sets=evidence_sets,
                   pr_provider=pr_provider, cache_dir=cache_dir, max_milestones=self.max_milestones)


if TYPE_CHECKING:  # mypy proves GitHistoryRunner satisfies the hook H1 Protocol in interface.py
    from .interface import HistoryRunner

    def _conforms(r: GitHistoryRunner) -> HistoryRunner:
        return r


__all__ = ["BUDGET_REASONS", "FINALIZE_STAGE", "GitHistoryRunner", "INPUT_REASONS", "RUN_REPORT_VERSION",
           "RunBudget", "STAGE_DEPENDS", "STAGE_ORDER", "STAGE_REASONS", "STAGE_STATUSES", "StageOutcome",
           "StageStatus", "TRUNCATION_REASONS", "run"]
