"""Traces history module: native-Git history as evidence records (docs/contracts/history.md).

Read-only, no network. This checkpoint: hardened gitcmd, ingest and cache, filters and config.
"""

from .config import FilterSpec, HistoryConfig, Limits, Thresholds
from .errors import HistoryError
from .gitcmd import GitRunner
from .ingest import ingest
from .model import Change, Commit, HistoryLog, RepoRef

__all__ = ["Change", "Commit", "FilterSpec", "GitRunner", "HistoryConfig", "HistoryError", "HistoryLog", "Limits",
           "RepoRef", "Thresholds", "ingest"]
