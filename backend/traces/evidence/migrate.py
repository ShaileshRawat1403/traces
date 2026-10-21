"""Evidence schema migrations. traces-evidence/0.3 (Task 002 pipeline format) -> 0.4 (D-004).

0.3 -> 0.4 changes, nothing else:
- schema_version becomes traces-evidence/0.4 and migrated_from records the old version;
- status rejected: label inferred -> rejected (architect ruling: rejected is its own reviewer-facing label);
- status missing_location: flag no_source_location is added (label stays inferred; never verified).
claim_id, check ids, status, class, provenance, locations and history are untouched, so ids stay stable."""
from __future__ import annotations

import copy
import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

V03 = "traces-evidence/0.3"
V04 = "traces-evidence/0.4"
CURRENT = V04
SCHEMA_DIR = Path(__file__).resolve().parent / "schema"
SCHEMAS = {V03: SCHEMA_DIR / "evidence_record.v0.3.schema.json", V04: SCHEMA_DIR / "evidence_record.v0.4.schema.json"}


def migrate_record_03_to_04(rec: dict[str, Any]) -> dict[str, Any]:
    if rec.get("schema_version") != V03:
        raise ValueError(f"expected {V03}, got {rec.get('schema_version')!r}")
    r = copy.deepcopy(rec)
    r["schema_version"] = V04
    r["migrated_from"] = V03
    if r["status"] == "rejected":
        r["label"] = "rejected"
    if r["status"] == "missing_location":
        flags = r.setdefault("flags", [])
        if "no_source_location" not in flags:
            flags.append("no_source_location")
    return r


def to_current(rec: dict[str, Any]) -> dict[str, Any]:
    v = rec.get("schema_version")
    if v == V04:
        return rec
    if v == V03:
        return migrate_record_03_to_04(rec)
    raise ValueError(f"unknown schema_version {v!r}")


def migrate_jsonl(lines: Iterable[str]) -> Iterator[dict[str, Any]]:
    for line in lines:
        if line.strip():
            yield to_current(json.loads(line))


def load_schema(version: str = CURRENT) -> dict[str, Any]:
    return json.loads(SCHEMAS[version].read_text())
