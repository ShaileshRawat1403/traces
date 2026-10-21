"""Read-only views over traces-evidence/0.4 records for the explain engine. Pure functions, no store access."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

GROUNDED = ("verified", "observed")
INFERRED = ("unvalidated", "missing_location")
EXPECTED_LABEL = {"verified": "verified", "observed": "observed", "unvalidated": "inferred", "missing_location": "inferred", "rejected": "rejected"}


def short_symbol(symbol: str | None) -> str:
    """Last segment of a CodeGraph symbol id (file::scope::name); a file-level id reads as its basename."""
    if not symbol:
        return "?"
    parts = symbol.split("::")
    name = parts[-1]
    if "/" in name and len(parts) >= 2 and name == parts[0]:
        return name.rsplit("/", 1)[-1]
    if name.startswith("route:"):
        name = name[len("route:"):]
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
    words: frozenset[str] = field(default=frozenset(), compare=False)

    @property
    def grounded(self) -> bool:
        return self.status in GROUNDED and EXPECTED_LABEL.get(self.status) == self.label

    @property
    def inferred(self) -> bool:
        return self.status in INFERRED

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
        words=words_of(fr.get("symbol"), to.get("symbol"), kind, route, first.get("file")),
    )
