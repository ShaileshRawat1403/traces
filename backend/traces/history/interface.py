"""Hook points between the index worker / API and the history module.

The history module's own contract is docs/contracts/history.md (Traces History seat, its own PR); that document
is authoritative for history's public API. This file pins only what other seats call or inject, so the worker and
API can be written against it before history lands. The History seat may move these names into its package as long
as the signatures below keep working (CONTRACTS.md section 6).

H1  index worker -> history:  HistoryRunner.run(repo=HistoryRepoRef(clone path, sha), ...)
H2  evidence -> history:      ComponentMap (traces.evidence.types) passed as `components`
H3  history -> index worker:  select_milestones(...) returns SHAs; the worker runs the evidence pipeline at each
                              and passes the resulting EvidenceSets back as `evidence_sets`
H4  API/ingest -> history:    PrContextProvider (cached PR JSON); history never touches the network or tokens
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from traces.evidence.types import ComponentMap, EvidenceRecord, EvidenceSet, Sha


@dataclass(frozen=True)
class HistoryRepoRef:
    path: Path      # local clone or bare mirror with full history (made by traces.ingest.fetch)
    repo: str       # "owner/name"
    sha: Sha        # pinned analysis commit


@dataclass(frozen=True)
class CachedComment:
    id: int
    body: str
    path: str | None
    commit_id: Sha | None


@dataclass(frozen=True)
class CachedPr:
    number: int
    merge_commit_sha: Sha | None
    body: str | None
    review_comments: Sequence[CachedComment]
    source_artifact: str     # cache path, relative to TRACES_CACHE_DIR
    sha256: str              # of the cached JSON artifact
    fetched_at: str


class PrContextProvider(Protocol):
    """Implemented by the API/ingest layer (GitHub client, token, cache, rate limits); injected into history."""
    def get(self, pr_number: int) -> CachedPr | None: ...


@dataclass(frozen=True)
class Milestone:
    sha: Sha
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class HistoryResult:
    records: Sequence[EvidenceRecord]   # traces-evidence/0.4, evidence_scope history|documented, sorted by claim_id
    report: Mapping[str, Any]


class HistoryRunner(Protocol):
    def select_milestones(self, repo: HistoryRepoRef, *, max_milestones: int = 8,
                          components: ComponentMap | None = None) -> Sequence[Milestone]: ...

    def run(self, repo: HistoryRepoRef, *, components: ComponentMap | None = None,
            evidence_sets: Mapping[Sha, EvidenceSet] | None = None,
            pr_provider: PrContextProvider | None = None, cache_dir: Path | None = None) -> HistoryResult: ...


class NotImplementedHistory:
    """Placeholder until the History seat merges; every call fails explicitly (no fake data)."""

    def select_milestones(self, repo: HistoryRepoRef, *, max_milestones: int = 8,
                          components: ComponentMap | None = None) -> Sequence[Milestone]:
        raise NotImplementedError("history: not implemented (owner: Traces History, see docs/contracts/history.md)")

    def run(self, repo: HistoryRepoRef, *, components: ComponentMap | None = None,
            evidence_sets: Mapping[Sha, EvidenceSet] | None = None,
            pr_provider: PrContextProvider | None = None, cache_dir: Path | None = None) -> HistoryResult:
        raise NotImplementedError("history: not implemented (owner: Traces History, see docs/contracts/history.md)")
