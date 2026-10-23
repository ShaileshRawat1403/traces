"""Read-only views over traces-evidence/0.4 records for the explain engine. Pure functions, no store access."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

GROUNDED = ("verified", "observed")
INFERRED = ("unvalidated", "missing_location")
# History records that describe patterns or inferences over commit history (docs/contracts/history.md 6). They are never
# code structure, never verified and never a "fact" sentence: co-change is a pattern, not a dependency or a cause.
HISTORY_PATTERN_CLASSES = ("history_pattern", "history_inferred")
HISTORY_PATTERN_KINDS = (
    "co_changed_with",
    "history_impact_candidate",
    "file_history_metrics",
    "component_history_metrics",
    "deleted_soon_after_add",
    "prefix_moved",
)
# Criteria keys echoed with a history pattern, in this order, when the record's parameters carry them.
CRITERIA_KEYS = (
    "level",
    "min_revs",
    "min_shared_revs",
    "min_coupling",
    "max_changeset_size",
    "commits",
    "metric_set",
    "rename_normalization",
    "bot_filter",
    "generated_filter",
    "filters",
)
EXPECTED_LABEL = {
    "verified": "verified",
    "observed": "observed",
    "unvalidated": "inferred",
    "missing_location": "inferred",
    "rejected": "rejected",
}


def short_symbol(symbol: str | None) -> str:
    """Last segment of a CodeGraph symbol id (file::scope::name); a file-level id reads as its basename."""
    if not symbol:
        return "?"
    parts = symbol.split("::")
    name = parts[-1]
    if "/" in name and len(parts) >= 2 and name == parts[0]:
        return name.rsplit("/", 1)[-1]
    if name.startswith("route:"):
        name = name[len("route:") :]
    return name


@dataclass(frozen=True)
class ClaimView:
    claim_id: str
    claim_kind: str
    kind: str
    status: str
    label: str
    statement: str
    from_symbol: str | None
    to_symbol: str | None
    file: str | None
    start_line: int | None
    end_line: int | None
    flags: tuple[str, ...] = ()
    status_reason: str | None = None
    route: str | None = None
    record_class: str = ""
    qualifier: str | None = None
    # Echoed criteria of a history pattern as (key, compact JSON value) pairs, in CRITERIA_KEYS order.
    criteria: tuple[tuple[str, str], ...] = ()
    scope: str = ""
    # Full commit SHAs this record is about (commit:: endpoints and origin.commit), for commit questions.
    commits: tuple[str, ...] = ()
    # Co-change support (shared commits), union of commits touching either side, and coupling degree, from metrics.
    support: int | None = None
    union: int | None = None
    degree: float | None = None
    # Files in a grouped directory move (prefix_moved), from metrics or provenance_raw.
    files: int | None = None
    words: frozenset[str] = field(default=frozenset(), compare=False)

    @property
    def history_pattern(self) -> bool:
        """A pattern or inference over commit history (co-change, hotspots, churn, impact candidates, lifecycle guesses)."""
        return self.record_class in HISTORY_PATTERN_CLASSES or self.kind in HISTORY_PATTERN_KINDS

    @property
    def grounded(self) -> bool:
        """Grounded code evidence. A history pattern is never grounded, whatever its status: observed only means its
        counts were rechecked against Git."""
        return self.status in GROUNDED and EXPECTED_LABEL.get(self.status) == self.label and not self.history_pattern

    @property
    def code_structure(self) -> bool:
        """Grounded static code evidence (not a Git or history record)."""
        return self.grounded and self.scope not in ("history", "documented")

    @property
    def inferred(self) -> bool:
        return self.status in INFERRED and not self.history_pattern

    @property
    def rejected(self) -> bool:
        return self.status == "rejected"

    @property
    def where(self) -> str:
        if not self.file:
            return "no source location"
        if self.start_line is None:
            return self.file
        if self.end_line and self.end_line != self.start_line:
            return f"{self.file}:{self.start_line}-{self.end_line}"
        return f"{self.file}:{self.start_line}"


_WORD = re.compile(r"[a-z0-9]+")


def words_of(*texts: str | None) -> frozenset[str]:
    out: set[str] = set()
    for t in texts:
        if not t:
            continue
        # split camelCase and snake_case so "createItem" matches "create item"
        spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", t)
        out.update(w for w in _WORD.findall(spaced.lower()) if len(w) >= 2)
    return frozenset(out)


def _commits_of(record: dict[str, Any]) -> tuple[str, ...]:
    out: list[str] = []
    for end in (record.get("from") or {}, record.get("to") or {}):
        sym = end.get("symbol") if isinstance(end, dict) else None
        if isinstance(sym, str) and sym.startswith("commit::"):
            out.append(sym[len("commit::") :].lower())
    origin = record.get("origin")
    if isinstance(origin, dict) and isinstance(origin.get("commit"), str):
        out.append(origin["commit"].lower())
    return tuple(dict.fromkeys(out))


def criteria_of(record: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    """The record's own criteria, echoed verbatim (compact, key-sorted JSON per value). Reads parameters.values, then
    parameters, then a top-level criteria object."""
    prm = record.get("parameters")
    src: Any = None
    if isinstance(prm, dict):
        src = prm.get("values") if isinstance(prm.get("values"), dict) else prm
    if not isinstance(src, dict) or not any(k in src for k in CRITERIA_KEYS):
        src = record.get("criteria") if isinstance(record.get("criteria"), dict) else src
    if not isinstance(src, dict):
        return ()
    return tuple(
        (k, json.dumps(src[k], sort_keys=True, separators=(",", ":"), ensure_ascii=False))
        for k in CRITERIA_KEYS
        if k in src
    )


def _num(d: Any, key: str) -> float | None:
    v = d.get(key) if isinstance(d, dict) else None
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def endpoint_path(symbol: str | None) -> str | None:
    """The repository path of a file:: endpoint, or the name of a component:: endpoint; None otherwise."""
    if not symbol:
        return None
    for pre in ("file::", "component::"):
        if symbol.startswith(pre):
            return symbol[len(pre) :] or None
    return None


def view(record: dict[str, Any]) -> ClaimView | None:
    """Project a record; returns None for records without a claim_id or status (never guesses a status)."""
    cid, status, label = record.get("claim_id"), record.get("status"), record.get("label")
    if not isinstance(cid, str) or not isinstance(status, str) or not isinstance(label, str):
        return None
    fr = record.get("from") or {}
    to = record.get("to") or {}
    locs = [loc for loc in record.get("locations") or [] if isinstance(loc, dict) and loc.get("file")]
    first = locs[0] if locs else {}
    kind = record.get("relationship_kind") or record.get("node_kind") or ""
    raw = record.get("provenance_raw") or {}
    route = raw.get("route_local_path") if kind == "route" else None
    if kind == "route" and not route:
        route = short_symbol(fr.get("symbol"))
    statement = record.get("statement") or ""
    return ClaimView(
        claim_id=cid,
        claim_kind=str(record.get("claim_kind") or ""),
        kind=str(kind),
        status=status,
        label=label,
        statement=str(statement),
        from_symbol=fr.get("symbol"),
        to_symbol=to.get("symbol"),
        file=first.get("file") or fr.get("file"),
        start_line=first.get("start_line") or fr.get("start_line"),
        end_line=first.get("end_line") or fr.get("end_line"),
        flags=tuple(f for f in record.get("flags") or [] if isinstance(f, str)),
        status_reason=record.get("status_reason") if isinstance(record.get("status_reason"), str) else None,
        route=route,
        record_class=str(record.get("class") or ""),
        qualifier=record.get("qualifier") if isinstance(record.get("qualifier"), str) else None,
        criteria=criteria_of(record),
        scope=str(record.get("evidence_scope") or ""),
        commits=_commits_of(record),
        support=int(sup)
        if (sup := _num(record.get("metrics"), "support") or _num(raw, "support")) is not None
        else None,
        union=int(uni) if (uni := _num(record.get("metrics"), "union_commits")) is not None else None,
        degree=_num(record.get("metrics"), "degree"),
        files=int(fl) if (fl := _num(record.get("metrics"), "files") or _num(raw, "files")) is not None else None,
        words=words_of(fr.get("symbol"), to.get("symbol"), kind, route, first.get("file")),
    )
