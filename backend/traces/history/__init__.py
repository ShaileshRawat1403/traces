"""Traces history module: native-Git history as evidence records (docs/contracts/history.md).

Read-only, no network. This checkpoint: gitcmd, ingest and cache, filters and config, records, commit facts and
lifecycle.
"""

from .config import FilterSpec, HistoryConfig, Limits, Thresholds
from .errors import HistoryError
from .facts import commit_facts
from .gitcmd import GitRunner
from .ingest import ingest
from .interface import HistoryRepoRef, HistoryResult
from .lifecycle import lifecycle
from .model import Change, Commit, HistoryLog, RepoRef
from .records import RunContext, canonical_hash, claim_id
from .shapes import ComponentDef, ComponentMap, Record, default_context, validate_component_map

__all__ = [
    "Change", "Commit", "ComponentDef", "ComponentMap", "FilterSpec", "GitRunner", "HistoryConfig", "HistoryError",
    "HistoryLog", "HistoryRepoRef", "HistoryResult", "Limits", "Record", "RepoRef", "RunContext", "Thresholds",
    "canonical_hash", "claim_id", "commit_facts", "default_context", "ingest", "lifecycle", "validate_component_map",
]
