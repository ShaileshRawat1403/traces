"""Validate records against the committed traces-evidence/0.4 schema with both validators the Traces seat uses."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import jsonschema

from traces.evidence.migrate import V04, load_schema
from traces.evidence.schema_check import Validator

_S = load_schema(V04)
_STD = Validator(_S)
_JS = jsonschema.Draft202012Validator(_S, format_checker=jsonschema.FormatChecker())


def schema_errors(rec: Mapping[str, Any]) -> list[str]:
    a = [str(e) for e in _STD.errors(rec)]
    b = [e.message for e in _JS.iter_errors(rec)]
    return a + b


def assert_valid(records: Iterable[Mapping[str, Any]]) -> int:
    n = 0
    for r in records:
        errs = schema_errors(r)
        assert not errs, f"{r.get('claim_id')} {r.get('relationship_kind') or r.get('node_kind')}: {errs[:3]}"
        assert r["status"] != "verified"
        n += 1
    return n
