"""Whole-run entry point for the INDEX job's 'history' step (docs/contracts/history.md section 8.11, D-H12).

The signature, budget shape, stage order, statuses, reasons and report layout are frozen (section 8.11). Stages run
in STAGE_ORDER and are all or nothing. The run budget is checked before each stage and before every git call (the
cooperative check points); git children additionally get RLIMIT_AS and RLIMIT_CPU derived from the budget. Contract
errors raise HistoryError and publish nothing. No network, no target repository code: every Git access goes through
gitcmd.
"""

from __future__ import annotations

import contextlib
import datetime as _dt
import gc
import math
import os
import resource
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal, cast

from traces.evidence.types import ComponentMap, EvidenceSet, Sha

from .churn import churn, hotspots
from .cochange import cochange
from .config import EXTRACTOR, MAX_MILESTONES_DEFAULT, MAX_MILESTONES_ON_DEMAND, HistoryConfig
from .errors import E_CONFIG, E_EVIDENCE_SET, E_LIMIT, E_SCHEMA, E_SHA, E_TIMEOUT, HistoryError
from .facts import commit_facts
from .gitcmd import CallLimits, GitBudgetExceeded, call_limits
from .ingest import ingest
from .interface import HistoryRepoRef, HistoryResult, Milestone, PrContextProvider
from .lifecycle import lifecycle
from .manifests import manifest_changes
from .milestones import evidence_set_diff, milestone_candidates, milestone_records, select_milestones, snapshot_compare
from .model import HistoryLog
from .pr_context import pr_context
from .records import RunContext, canonical_hash, finalize
from .reverts import reverts
from .shapes import IST, Record, validate_component_map

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


# Tunables kept in one place so Architect1's open-question answers stay easy to change.
GIT_AS_HEADROOM_MB: Final = 512        # RLIMIT_AS per git child = budget.memory_mb + this
GIT_CPU_CEILING_S: int | None = None   # optional fixed RLIMIT_CPU per git child; always capped by remaining time
VALIDATE_EVERY_RECORD: Final = True    # finalize validates every record (Architect1 answer 5)


# Probes (clock, RSS) are module state so tests can inject fakes without touching the frozen signature.
def _rss_mb() -> float:
    try:
        with open("/proc/self/statm", "rb") as f:
            pages = int(f.read().split()[1])
        return pages * os.sysconf("SC_PAGE_SIZE") / (1 << 20)
    except (OSError, ValueError, IndexError):
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # peak, KiB on Linux


@dataclass
class Probes:
    clock: Callable[[], float] = time.monotonic
    rss_mb: Callable[[], float] = _rss_mb


_PROBES = Probes()


@contextlib.contextmanager
def probes(*, clock: Callable[[], float] | None = None, rss_mb: Callable[[], float] | None = None) -> Iterator[None]:
    """Swap the clock and RSS probe (tests). Restored on exit."""
    old = (_PROBES.clock, _PROBES.rss_mb)
    _PROBES.clock = clock or old[0]
    _PROBES.rss_mb = rss_mb or old[1]
    try:
        yield
    finally:
        _PROBES.clock, _PROBES.rss_mb = old


class _Tracker:
    """Budget accounting for one run: monotonic time from entry, RSS growth over the entry value."""

    def __init__(self, budget: RunBudget) -> None:
        self.budget = budget
        self.clock = _PROBES.clock
        self.rss = _PROBES.rss_mb
        self.t0 = self.clock()
        self.rss0 = self.rss()
        self.peak_growth = 0.0
        self.stage_deadline = self.t0 + budget.time_s - budget.finalize_reserve_s

    def elapsed(self) -> float:
        return self.clock() - self.t0

    def check(self) -> None:
        if self.clock() >= self.stage_deadline:
            raise GitBudgetExceeded("budget_time", f"less than finalize_reserve_s ({self.budget.finalize_reserve_s}s) "
                                                   f"of the {self.budget.time_s}s budget remains")
        growth = self.rss() - self.rss0
        self.peak_growth = max(self.peak_growth, growth)
        if growth > self.budget.memory_mb:
            raise GitBudgetExceeded("budget_memory", f"RSS grew {growth:.0f} MiB, over memory_mb "
                                                     f"{self.budget.memory_mb}")

    def limits(self) -> CallLimits:
        return CallLimits(as_bytes=(self.budget.memory_mb + GIT_AS_HEADROOM_MB) << 20, cpu_s=GIT_CPU_CEILING_S,
                          deadline=self.stage_deadline, clock=self.clock, check=self.check)


class _Skip(Exception):
    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


@dataclass
class _State:
    repo: HistoryRepoRef
    config: HistoryConfig
    ctx: RunContext
    components: ComponentMap | None
    evidence_sets: Mapping[Sha, EvidenceSet] | None
    pr_provider: PrContextProvider | None
    cache_dir: Path | None
    max_milestones: int
    log: HistoryLog | None = None
    milestones: tuple[Milestone, ...] = ()
    volatile: dict[str, Any] = field(default_factory=dict)


@dataclass
class _StageRun:
    records: list[Record]
    report: Mapping[str, Any]
    truncation: str | None = None
    detail: str = ""


def _recs(x: Sequence[Mapping[str, Any]]) -> list[Record]:
    return cast(list[Record], list(x))


def _need_log(st: _State) -> HistoryLog:
    assert st.log is not None
    return st.log


def _st_ingest(st: _State) -> _StageRun:
    if st.log is None:
        st.log = ingest(st.repo, st.config, cache_dir=st.cache_dir)
    log = st.log
    st.volatile["cache_stats"] = dict(log.cache_stats)
    limited = sum(1 for c in log.commits if c.rename_limited)
    rep = {"stage": "ingest", "commits": len(log.commits), "first_parent": len(log.first_parent),
           "merges": sum(1 for c in log.commits if c.is_merge), "mailmap_blob": log.mailmap_blob,
           "rename_limited_commits": limited, "warnings": list(log.warnings)}
    return _StageRun([], rep, "rename_detection_limited" if limited else None,
                     f"rename detection limited in {limited} commits" if limited else "")


def _simple(fn: Callable[..., HistoryResult], **kw: Any) -> Callable[[_State], _StageRun]:
    def go(st: _State) -> _StageRun:
        extra = {k: getattr(st, v) for k, v in kw.items()}
        res = fn(_need_log(st), ctx=st.ctx, **extra)
        return _StageRun(_recs(res.records), dict(res.report))
    return go


def _st_cochange_component(st: _State) -> _StageRun:
    res = cochange(_need_log(st), level="component", components=st.components, ctx=st.ctx)
    return _StageRun(_recs(res.records), dict(res.report))


def _st_aliases(st: _State) -> _StageRun:
    raise _Skip("not_in_v1", "alias suggestions (section 8.8) are not in v1")


def _st_milestones(st: _State) -> _StageRun:
    log = _need_log(st)
    ms = tuple(select_milestones(log, max_milestones=st.max_milestones, components=st.components))
    if st.evidence_sets:
        extra = sorted(set(st.evidence_sets) - {m.sha for m in ms})
        if extra:
            raise HistoryError(E_EVIDENCE_SET, f"evidence set for {extra[0][:12]} is not a selected milestone "
                                               f"(max_milestones {st.max_milestones})", "milestones")
    res = milestone_records(log, ms, max_milestones=st.max_milestones, ctx=st.ctx)
    st.milestones = ms
    n_cand = len(milestone_candidates(log))
    rep = {**dict(res.report), "candidates": n_cand, "selected": len(ms)}
    capped = n_cand > len(ms)
    return _StageRun(_recs(res.records), rep, "milestone_cap" if capped else None,
                     f"{len(ms)} of {n_cand} candidates kept (max_milestones {st.max_milestones})" if capped else "")


def _pairs(shas: Sequence[str]) -> list[tuple[str, str]]:
    return list(zip(shas, shas[1:], strict=False))


def _st_snapshot(st: _State) -> _StageRun:
    log = _need_log(st)
    shas = [m.sha for m in st.milestones]
    if len(shas) < 2:
        raise _Skip("too_few_milestones", f"{len(shas)} milestone(s); a compare needs two")
    out: list[Record] = []
    pairs = []
    for a, b in _pairs(shas):
        res = snapshot_compare(log, a, b, components=st.components, ctx=st.ctx)
        out += _recs(res.records)
        pairs.append({"base": a, "head": b, "records": len(res.records),
                      **{k: res.report[k] for k in ("added", "removed", "renamed", "modified") if k in res.report}})
    return _StageRun(out, {"stage": "snapshot_compare", "pairs": pairs})


def _st_esd(st: _State) -> _StageRun:
    log = _need_log(st)
    sets = st.evidence_sets or {}
    present = [m.sha for m in st.milestones if m.sha in sets]
    if len(present) < 2:
        raise _Skip("no_evidence_sets", f"{len(present)} milestone(s) have an evidence set; a diff needs two")
    out: list[Record] = []
    pairs = []
    for a, b in _pairs(present):
        res = evidence_set_diff(sets[a], sets[b], log=log, ctx=st.ctx)
        out += _recs(res.records)
        pairs.append({"base": a, "head": b, "records": len(res.records)})
    missing = len(st.milestones) - len(present)
    return _StageRun(out, {"stage": "evidence_set_diff", "pairs": pairs, "milestones_without_set": missing},
                     "evidence_sets_missing_for_some_milestones" if missing else None,
                     f"{missing} milestone(s) have no evidence set; pairs use the ones that do" if missing else "")


def _st_pr(st: _State) -> _StageRun:
    res = pr_context(_need_log(st), st.pr_provider, ctx=st.ctx)
    rep = dict(res.report)
    gaps = len(rep.get("prs_missing", [])) + len(rep.get("prs_skipped", []))
    return _StageRun(_recs(res.records), rep, "pr_data_missing_for_some_prs" if gaps else None,
                     f"{gaps} of {rep.get('linked_prs', 0)} linked PRs had no usable cached data" if gaps else "")


STAGE_FUNCS: dict[str, Callable[[_State], _StageRun]] = {
    "ingest": _st_ingest,
    "commit_facts": _simple(commit_facts),
    "lifecycle": _simple(lifecycle, components="components"),
    "churn": _simple(churn, components="components"),
    "hotspots": _simple(hotspots),
    "cochange_file": _simple(cochange),
    "cochange_component": _st_cochange_component,
    "manifests": _simple(manifest_changes),
    "reverts": _simple(reverts),
    "aliases": _st_aliases,
    "milestones": _st_milestones,
    "snapshot_compare": _st_snapshot,
    "evidence_set_diff": _st_esd,
    "pr_context": _st_pr,
}


def _input_skip(stage: str, st: _State) -> tuple[str, str] | None:
    if stage == "cochange_component" and st.components is None:
        return "no_component_map", "no component map supplied"
    if stage == "evidence_set_diff" and not st.evidence_sets:
        return "no_evidence_sets", "no evidence sets supplied"
    if stage == "pr_context" and st.pr_provider is None:
        return "no_pr_provider", "no PR context provider injected (offline default)"
    return None


_VALIDATORS: tuple[Any, Any] | None = None


def _validators() -> tuple[Any, Any]:
    global _VALIDATORS
    if _VALIDATORS is None:
        import importlib

        import jsonschema

        from traces.evidence.migrate import V04, load_schema

        # Imported by name: traces.evidence.schema_check (Traces seat) is not annotated for mypy's strict settings,
        # and following it would report its errors under history's mypy run. Requested as a shared-file fix.
        validator_cls = importlib.import_module("traces.evidence.schema_check").Validator
        schema = load_schema(V04)
        _VALIDATORS = (validator_cls(schema),
                       jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()))
    return _VALIDATORS


def _finalize(records: list[Record]) -> list[Record]:
    out = finalize(records)  # sort by claim_id, E_COLLISION on one id with two contents
    if VALIDATE_EVERY_RECORD:
        std, js = _validators()
        for r in out:
            errs = [str(e) for e in std.errors(r)] + [e.message for e in js.iter_errors(r)]
            if errs or r.get("status") == "verified":
                why = errs[0] if errs else "history records never reach verified"
                raise HistoryError(E_SCHEMA, f"{r.get('claim_id')}: {why[:300]}", FINALIZE_STAGE)
    return out


def _validate_inputs(repo: HistoryRepoRef, config: HistoryConfig, budget: RunBudget,
                     components: ComponentMap | None, evidence_sets: Mapping[Sha, EvidenceSet] | None,
                     max_milestones: int) -> None:
    """Preflight, fail closed. Git-level checks (E_REPO, E_SHA via rev-parse, E_SHALLOW, E_GIT_VERSION) run at the
    start of the ingest stage and are errors, never partial results."""
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
    _check_cap(max_milestones)
    if components is not None:
        validate_component_map(components, repo.sha, "preflight")
    if evidence_sets is not None:
        if not isinstance(evidence_sets, Mapping):
            raise HistoryError(E_EVIDENCE_SET, "evidence_sets must map SHA -> EvidenceSet", "preflight")
        for sha, es in evidence_sets.items():
            if not isinstance(es, EvidenceSet) or es.sha != sha:
                raise HistoryError(E_EVIDENCE_SET, "each evidence set must be an EvidenceSet keyed by its own sha",
                                   "preflight")


def _check_cap(max_milestones: object) -> int:
    if isinstance(max_milestones, bool) or not isinstance(max_milestones, int) \
            or not 2 <= max_milestones <= MAX_MILESTONES_ON_DEMAND:
        raise HistoryError(E_CONFIG, f"max_milestones must be between 2 and {MAX_MILESTONES_ON_DEMAND}", "preflight")
    return max_milestones


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
    (section 8.11)."""
    return _run(repo, config, budget=budget, components=components, evidence_sets=evidence_sets,
                pr_provider=pr_provider, cache_dir=cache_dir, max_milestones=max_milestones, run_id=run_id, at=at)


def _run(repo: HistoryRepoRef, config: HistoryConfig, *, budget: RunBudget | None,
         components: ComponentMap | None, evidence_sets: Mapping[Sha, EvidenceSet] | None,
         pr_provider: PrContextProvider | None, cache_dir: Path | None, max_milestones: int,
         run_id: str | None, at: str | None, log: HistoryLog | None = None) -> HistoryResult:
    b = budget or RunBudget()
    _validate_inputs(repo, config, b, components, evidence_sets, max_milestones)
    tr = _Tracker(b)
    now = _dt.datetime.now(IST).replace(microsecond=0)
    ctx = RunContext(run_id=run_id or f"h-{now.strftime('%Y%m%dT%H%M%S')}", at=at or now.isoformat(),
                     repo=repo.repo, repo_sha=repo.sha)
    st = _State(repo, config, ctx, components, evidence_sets, pr_provider, cache_dir, max_milestones, log=log)
    outcomes: list[StageOutcome] = []
    stage_reports: dict[str, Any] = {}
    kept: list[Record] = []
    done: set[str] = set()
    exhausted: tuple[str, str] | None = None
    stage_elapsed: dict[str, float] = {}

    def exhaust(stage: str, reason: str, detail: str) -> tuple[str, str]:
        if b.on_exhausted == "fail":
            raise HistoryError(E_TIMEOUT if reason == "budget_time" else E_LIMIT, detail, stage)
        return reason, detail

    for stage in STAGE_ORDER:
        if exhausted is not None:
            outcomes.append(StageOutcome(stage, "skipped", exhausted[0],
                                         f"not started: budget exhausted earlier ({exhausted[1]})", 0))
            continue
        skip = _input_skip(stage, st)
        if skip is None and any(d not in done for d in STAGE_DEPENDS[stage]):
            skip = ("dependency_not_completed",
                    "needs " + ", ".join(d for d in STAGE_DEPENDS[stage] if d not in done))
        if skip is not None:
            outcomes.append(StageOutcome(stage, "skipped", skip[0], skip[1], 0))
            continue
        try:
            tr.check()
        except GitBudgetExceeded as e:
            exhausted = exhaust(stage, e.reason, e.detail)
            outcomes.append(StageOutcome(stage, "skipped", e.reason, f"not started: {e.detail}", 0))
            continue
        t_stage = tr.clock()
        try:
            with call_limits(tr.limits()):
                sr = STAGE_FUNCS[stage](st)
        except _Skip as sk:
            outcomes.append(StageOutcome(stage, "skipped", sk.reason, sk.detail, 0))
            continue
        except GitBudgetExceeded as e:
            exhausted = exhaust(stage, e.reason, e.detail)
            outcomes.append(StageOutcome(stage, "aborted", e.reason, f"stopped, output discarded: {e.detail}", 0))
            continue
        except MemoryError:
            gc.collect()
            exhausted = exhaust(stage, "budget_memory", "MemoryError inside the stage")
            outcomes.append(StageOutcome(stage, "aborted", "budget_memory",
                                         "stopped, output discarded: MemoryError inside the stage", 0))
            continue
        finally:
            stage_elapsed[stage] = round(tr.clock() - t_stage, 3)
        n = len(sr.records)
        if len(kept) + n > b.max_records:
            detail = f"{len(kept)} kept + {n} from this stage exceeds max_records {b.max_records}"
            exhausted = exhaust(stage, "budget_records", detail)
            outcomes.append(StageOutcome(stage, "aborted", "budget_records", f"output discarded: {detail}", 0))
            continue
        kept += sr.records
        done.add(stage)
        stage_reports[stage] = sr.report
        outcomes.append(StageOutcome(stage, "truncated" if sr.truncation else "completed", sr.truncation,
                                     sr.detail, n))

    t_fin = tr.clock()
    records = _finalize(kept)
    finalize_s = round(tr.clock() - t_fin, 3)
    partial = [{"stage": o.stage, "reason": o.reason, "detail": o.detail} for o in outcomes
               if o.reason in BUDGET_REASONS]
    warnings: list[str] = []
    for o in outcomes:
        for w in (stage_reports.get(o.stage) or {}).get("warnings", []) or []:
            warnings.append(f"{o.stage}: {w}")
    log_ = st.log if "ingest" in done else None
    report: dict[str, Any] = {
        "report_version": RUN_REPORT_VERSION,
        "repo": repo.repo, "repo_sha": repo.sha,
        "history_version": EXTRACTOR["version"],
        "git_version": log_.git_version if log_ is not None else None,
        "config_digest": config.digest(), "config": config.as_dict(),
        "budget": b.as_dict(),
        "inputs": {"components_digest": components.digest if components is not None else None,
                   "evidence_set_shas": sorted(evidence_sets or {}), "pr_provider": pr_provider is not None,
                   "max_milestones": max_milestones},
        "complete": not partial,
        "partial_reasons": partial,
        "stage_order": list(STAGE_ORDER),
        "stages": [{**o.as_dict(), "report": stage_reports.get(o.stage)} for o in outcomes],
        "milestones": [{"sha": m.sha, "reasons": list(m.reasons)} for m in st.milestones]
        if "milestones" in done else [],
        "records": len(records),
        "records_digest": canonical_hash(records),
        "warnings": warnings,
        "volatile": {"run_id": ctx.run_id, "at": ctx.at, "elapsed_s": round(tr.elapsed(), 3),
                     "stage_elapsed_s": stage_elapsed, "finalize_s": finalize_s,
                     "rss_growth_mb": round(max(tr.peak_growth, tr.rss() - tr.rss0), 1), **st.volatile},
    }
    return HistoryResult(records, report)


class GitHistoryRunner:
    """Concrete runner for hook H1. Config, budget and the milestone cap are fixed at construction; the cap is a
    ceiling: select_milestones may ask for fewer, never more (E_CONFIG). The ingested log from select_milestones is
    reused by run() for the same repo, SHA and config, so both see the same history."""

    def __init__(self, config: HistoryConfig | None = None, budget: RunBudget | None = None, *,
                 max_milestones: int = MAX_MILESTONES_DEFAULT) -> None:
        self.config = (config or HistoryConfig()).validate()
        self.budget = (budget or RunBudget()).validate()
        self.max_milestones = _check_cap(max_milestones)
        self._log: tuple[tuple[str, str, str, str], HistoryLog] | None = None

    @staticmethod
    def _key(repo: HistoryRepoRef, config: HistoryConfig) -> tuple[str, str, str, str]:
        return (str(repo.path), repo.repo, repo.sha, config.digest())

    def select_milestones(self, repo: HistoryRepoRef, *, max_milestones: int = MAX_MILESTONES_DEFAULT,
                          components: ComponentMap | None = None,
                          config: HistoryConfig | None = None) -> tuple[Milestone, ...]:
        _check_cap(max_milestones)
        if max_milestones > self.max_milestones:
            raise HistoryError(E_CONFIG, f"max_milestones {max_milestones} is above this runner's cap "
                                         f"{self.max_milestones}", "milestones")
        cfg = (config or self.config).validate()
        if components is not None:
            validate_component_map(components, repo.sha, "milestones")
        key = self._key(repo, cfg)
        if self._log is None or self._log[0] != key:
            tr = _Tracker(self.budget)
            try:
                with call_limits(tr.limits()):
                    self._log = (key, ingest(repo, cfg))
            except GitBudgetExceeded as e:
                raise HistoryError(E_TIMEOUT if e.reason == "budget_time" else E_LIMIT, e.detail, "milestones") from e
        return tuple(select_milestones(self._log[1], max_milestones=max_milestones, components=components))

    def run(self, repo: HistoryRepoRef, *, config: HistoryConfig | None = None, budget: RunBudget | None = None,
            components: ComponentMap | None = None,
            evidence_sets: Mapping[Sha, EvidenceSet] | None = None,
            pr_provider: PrContextProvider | None = None, cache_dir: Path | None = None) -> HistoryResult:
        cfg = config or self.config
        log = self._log[1] if self._log is not None and self._log[0] == self._key(repo, cfg) else None
        return _run(repo, cfg, budget=budget or self.budget, components=components, evidence_sets=evidence_sets,
                    pr_provider=pr_provider, cache_dir=cache_dir, max_milestones=self.max_milestones,
                    run_id=None, at=None, log=log)


if TYPE_CHECKING:  # mypy proves GitHistoryRunner satisfies the hook H1 Protocol in interface.py
    from .interface import HistoryRunner

    def _conforms(r: GitHistoryRunner) -> HistoryRunner:
        return r


__all__ = ["BUDGET_REASONS", "FINALIZE_STAGE", "GIT_AS_HEADROOM_MB", "GitHistoryRunner", "INPUT_REASONS",
           "Probes", "RUN_REPORT_VERSION", "STAGE_FUNCS", "probes",
           "RunBudget", "STAGE_DEPENDS", "STAGE_ORDER", "STAGE_REASONS", "STAGE_STATUSES", "StageOutcome",
           "StageStatus", "TRUNCATION_REASONS", "run"]
