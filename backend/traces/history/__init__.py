"""Traces history module: native-Git history as evidence records (docs/contracts/history.md).

Read-only, no network. Implemented so far: gitcmd, ingest and cache, filters and config, commit facts, lifecycle,
churn and hotspots, co-change, manifests. Reverts, milestones and snapshot diffs, impact and PR context follow.
"""

from .churn import churn, hotspots
from .cochange import cochange
from .config import FilterSpec, HistoryConfig, Limits, Thresholds
from .errors import HistoryError
from .facts import commit_facts
from .gitcmd import GitRunner
from .ingest import ingest
from .interface import HistoryRepoRef, HistoryResult
from .lifecycle import lifecycle
from .manifests import manifest_changes, manifest_events
from .model import Change, Commit, HistoryLog, RepoRef
from .records import RunContext, canonical_hash, claim_id
from .shapes import ComponentDef, ComponentMap, Record, default_context, validate_component_map

__all__ = [
    "Change", "Commit", "ComponentDef", "ComponentMap", "HistoryRepoRef", "FilterSpec", "GitRunner", "HistoryConfig", "HistoryError", "HistoryLog",
    "HistoryResult", "Limits", "Record", "RepoRef", "RunContext", "Thresholds", "canonical_hash", "churn", "claim_id",
    "cochange", "commit_facts", "default_context", "hotspots", "ingest", "lifecycle", "manifest_changes", "manifest_events", "validate_component_map",
]
