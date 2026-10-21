"""Shared evidence types (owned by the Traces seat; consumed by history, explain and the API).
Records are plain JSON objects conforming to traces-evidence/0.4; these types name them for interfaces."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from fnmatch import fnmatch
from typing import Any

EvidenceRecord = Mapping[str, Any]
Sha = str


@dataclass(frozen=True)
class EvidenceSet:
    """All evidence records of one snapshot (repo at sha), already at the current schema version."""
    repo: str
    sha: Sha
    schema_version: str
    records: Sequence[EvidenceRecord]


@dataclass(frozen=True)
class ComponentDef:
    id: str                       # "component::<name>"
    name: str
    layer: str                    # frontend | api | backend | data | infra | docs | tests | other
    paths: tuple[str, ...]        # member file paths at the snapshot
    rule: str                     # deterministic rule id that produced the grouping (D-007)


@dataclass(frozen=True)
class ComponentMap:
    """Deterministic component map for one snapshot; the evidence side produces it, history consumes it (hook H2)."""
    sha: Sha
    components: Mapping[str, ComponentDef]
    digest: str
    _index: Mapping[str, str] = field(default_factory=dict, repr=False, compare=False)

    def component_of(self, path: str) -> str | None:
        if self._index:
            return self._index.get(path)
        for cid, c in sorted(self.components.items()):
            if path in c.paths or any(fnmatch(path, p) for p in c.paths if "*" in p):
                return cid
        return None
