"""Typed shapes the history package uses internally, bound to the shared types.

Shared record types live in traces.evidence (Traces seat) and the hook points in interface.py (pinned by the
Architect, CONTRACTS.md section 5). This module re-exports them and adds the history-side helpers: the Record alias
for the plain 0.4 JSON objects history builds, the component map check, and the run context factory.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any

from traces.evidence.types import ComponentDef, ComponentMap

from .errors import E_COMPONENT_MAP, HistoryError
from .interface import HistoryRepoRef, HistoryResult
from .records import RunContext

Record = dict[str, Any]  # a traces-evidence/0.4 record (traces.evidence.types.EvidenceRecord) as built by history
IST = _dt.timezone(_dt.timedelta(hours=5, minutes=30))


def validate_component_map(cmap: ComponentMap, sha: str | None = None, stage: str = "components") -> ComponentMap:
    """E_COMPONENT_MAP when the map is not a ComponentMap, is for another SHA, or lists a member path in two
    components. v1 accepts maps built at the pinned SHA only."""
    if not isinstance(cmap, ComponentMap):
        raise HistoryError(E_COMPONENT_MAP, "components must be a traces.evidence.types.ComponentMap", stage)
    if sha is not None and cmap.sha != sha:
        raise HistoryError(E_COMPONENT_MAP, "v1 accepts component maps built at the pinned SHA only", stage)
    seen: dict[str, str] = {}
    for cid, comp in cmap.components.items():
        for m in comp.paths:
            if m in seen and seen[m] != cid:
                raise HistoryError(E_COMPONENT_MAP, f"member {m!r} is in two components", stage)
            seen[m] = cid
    return cmap


def default_context(repo: str, repo_sha: str, run_id: str | None = None) -> RunContext:
    now = _dt.datetime.now(IST).replace(microsecond=0)
    return RunContext(run_id=run_id or f"h-{now.strftime('%Y%m%dT%H%M%S')}", at=now.isoformat(), repo=repo,
                      repo_sha=repo_sha)


__all__ = ["ComponentDef", "ComponentMap", "HistoryRepoRef", "HistoryResult", "IST", "Record", "default_context",
           "validate_component_map"]
