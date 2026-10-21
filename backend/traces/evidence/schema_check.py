"""Minimal JSON Schema 2020-12 validator, CPython stdlib only, for the keywords used by
task002/spec/evidence_record.schema.json. Written because no jsonschema package is installed and
installing one needs network (not approved). Unsupported keywords raise, so nothing is silently skipped.
`format: date-time` is checked (stricter than the 2020-12 default, where format is an annotation)."""
from __future__ import annotations

import copy
import datetime
import json
import re
import sys
from collections.abc import Callable
from typing import Any

Schema = Any  # a JSON Schema node: dict, or True/False

SUPPORTED = {"$schema", "$id", "title", "description", "type", "additionalProperties", "required", "properties", "const", "enum",
             "pattern", "minLength", "minItems", "minimum", "items", "$ref", "allOf", "anyOf", "if", "then", "else", "not", "contains", "format", "$defs"}  # anyOf, else added for schema 0.3 (Decision 002-B)
TYPES: dict[str, type | tuple[type, ...]] = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def is_type(v: Any, t: str) -> bool:
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    return isinstance(v, TYPES[t])


def eq(a: Any, b: Any) -> bool:
    return type(a) == type(b) and a == b if not (isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool)) else a == b


class Validator:
    def __init__(self, schema: Schema) -> None:
        self.root = schema
        self._walk_keywords(schema)

    def _walk_keywords(self, s: Schema) -> None:
        if isinstance(s, dict):
            for k, v in s.items():
                if k not in SUPPORTED:
                    raise ValueError(f"unsupported keyword {k}")
                if k in ("properties", "$defs"):
                    for vv in v.values():
                        self._walk_keywords(vv)
                elif k in ("allOf", "anyOf"):
                    for vv in v:
                        self._walk_keywords(vv)
                elif k in ("items", "if", "then", "else", "not", "contains", "additionalProperties") and isinstance(v, dict):
                    self._walk_keywords(v)

    def errors(self, inst: Any, schema: Schema = None, path: str = "$") -> list[str]:
        s = self.root if schema is None else schema
        out: list[str] = []
        if s is True:
            return out
        if s is False:
            return [f"{path}: false schema"]
        if "$ref" in s:
            ref = s["$ref"]
            assert ref.startswith("#/$defs/")
            out += self.errors(inst, self.root["$defs"][ref.split("/")[-1]], path)
        if "type" in s:
            ts = s["type"] if isinstance(s["type"], list) else [s["type"]]
            if not any(is_type(inst, t) for t in ts):
                return out + [f"{path}: type {type(inst).__name__} not in {ts}"]
        if "const" in s and not eq(inst, s["const"]):
            out.append(f"{path}: {inst!r} != const {s['const']!r}")
        if "enum" in s and not any(eq(inst, e) for e in s["enum"]):
            out.append(f"{path}: {inst!r} not in enum")
        if isinstance(inst, str):
            if "pattern" in s and not re.search(s["pattern"], inst):
                out.append(f"{path}: {inst!r} does not match {s['pattern']}")
            if "minLength" in s and len(inst) < s["minLength"]:
                out.append(f"{path}: shorter than {s['minLength']}")
            if s.get("format") == "date-time":
                try:
                    d = datetime.datetime.fromisoformat(inst)
                    if d.tzinfo is None:
                        out.append(f"{path}: date-time without offset")
                except ValueError:
                    out.append(f"{path}: not a date-time")
        if isinstance(inst, (int, float)) and not isinstance(inst, bool) and "minimum" in s and inst < s["minimum"]:
            out.append(f"{path}: {inst} < minimum {s['minimum']}")
        if isinstance(inst, list):
            if "minItems" in s and len(inst) < s["minItems"]:
                out.append(f"{path}: fewer than {s['minItems']} items")
            if "items" in s:
                for i, v in enumerate(inst):
                    out += self.errors(v, s["items"], f"{path}[{i}]")
            if "contains" in s and not any(not self.errors(v, s["contains"], path) for v in inst):
                out.append(f"{path}: no item matches contains")
        if isinstance(inst, dict):
            for r in s.get("required", []):
                if r not in inst:
                    out.append(f"{path}: missing required {r}")
            props = s.get("properties", {})
            for k, v in inst.items():
                if k in props:
                    out += self.errors(v, props[k], f"{path}.{k}")
                elif s.get("additionalProperties") is False:
                    out.append(f"{path}: additional property {k}")
        for sub in s.get("allOf", []):
            out += self.errors(inst, sub, path)
        if "anyOf" in s and not any(not self.errors(inst, sub, path) for sub in s["anyOf"]):
            out.append(f"{path}: matches no anyOf branch")
        if "if" in s:
            if not self.errors(inst, s["if"], path):
                if "then" in s:
                    out += self.errors(inst, s["then"], path)
            elif "else" in s:
                out += self.errors(inst, s["else"], path)
        if "not" in s and not self.errors(inst, s["not"], path):
            out.append(f"{path}: matches 'not' schema")
        return out


def self_test(v: Validator) -> list[tuple[str, bool]]:
    """Known-bad inputs must be rejected; returns list of (case, rejected)."""
    good: dict[str, Any] = {"schema_version": "traces-evidence/0.3", "claim_id": "c_" + "0" * 64, "run_id": "r", "repo": "x", "repo_sha": "0" * 40,
            "claim_kind": "node", "node_kind": "function", "granularity": "symbol", "statement": "s", "class": "source_backed_declaration",
            "originator": {"name": "codegraph", "version": "1.6.2", "role": "extractor"}, "provenance_raw": {}, "provenance": "codegraph:declaration",
            "origin": {"kind": "tool_output"}, "injected": False, "evidence_scope": "static", "locations": [], "checks": [], "status": "missing_location",
            "label": "inferred", "status_reason": "r", "status_history": [{"from": None, "to": "missing_location", "at": "2026-10-21T10:00:00+05:30", "run_id": "r", "check_ids": [], "by": "t"}],
            "visible_to_reviewer": True}
    cases: list[tuple[str, bool]] = []
    cases.append(("good record accepted", not v.errors(good)))

    def bad(name: str, fn: Callable[[dict[str, Any]], Any]) -> None:
        g = copy.deepcopy(good); fn(g); cases.append((name, bool(v.errors(g))))
    bad("missing statement", lambda g: g.pop("statement"))
    bad("evidence_scope runtime", lambda g: g.update(evidence_scope="runtime"))
    bad("verified node", lambda g: g.update(status="verified", label="verified"))
    bad("observed without parser_presence check", lambda g: g.update(status="observed", label="observed", locations=[{"file": "a", "start_line": 1, "end_line": 1, "line_base": 1, "col_base": 0, "range_kind": "declaration", "range_rule": "file", "role": "from_decl", "blob_sha": "0" * 40, "source": "originator"}]))
    bad("unvalidated without reason", lambda g: (g.update(status="unvalidated"), g.pop("status_reason")))
    bad("bad provenance", lambda g: g.update(provenance="codegraph:guess"))
    bad("absolute location path", lambda g: g.update(status="unvalidated", locations=[{"file": "/etc/x", "start_line": 1, "end_line": 1, "line_base": 1, "col_base": 0, "range_kind": "file", "range_rule": "file", "role": "from_decl", "blob_sha": "0" * 40, "source": "originator"}]))
    bad("../ location path", lambda g: g.update(status="unvalidated", locations=[{"file": "../x", "start_line": 1, "end_line": 1, "line_base": 1, "col_base": 0, "range_kind": "file", "range_rule": "file", "role": "from_decl", "blob_sha": "0" * 40, "source": "originator"}]))
    bad("unvalidated with no locations", lambda g: g.update(status="unvalidated"))
    bad("extra property", lambda g: g.update(extra=1))
    bad("library_contract verified", lambda g: g.update(claim_kind="relationship", relationship_kind="library_contract", status="verified", label="verified"))
    bad("persistence_path without qualifier", lambda g: g.update(claim_kind="relationship", relationship_kind="persistence_path"))
    bad("injected with statically_derived", lambda g: g.update(injected=True, **{"class": "statically_derived"}))
    # Decision 002-B cases
    F = {"file": "a", "start_line": 1, "end_line": 2, "line_base": 1, "col_base": 0, "range_kind": "file", "range_rule": "file", "role": "from_decl", "blob_sha": "0" * 40, "source": "originator"}
    bad("old class name unverified_inference", lambda g: g.update(**{"class": "unverified_inference"}))
    bad("file range without original coordinates", lambda g: g.update(status="unvalidated", locations=[dict(F)]))
    bad("non-file range with end_line 0", lambda g: g.update(status="unvalidated", locations=[dict(F, range_kind="site", range_rule="expression", role="site", start_line=1, end_line=0)]))
    bad("non-file range with an EOF boundary field", lambda g: g.update(status="unvalidated", locations=[dict(F, range_kind="site", range_rule="expression", role="site", end_exclusive_line=3)]))
    bad("observed relationship without import-statement qualifier", lambda g: g.update(claim_kind="relationship", relationship_kind="calls", status="observed", label="observed", **{"from": {"symbol": "a::b", "file": "a"}, "to": {"symbol": "a::c", "file": "a"}}))
    bad("consolidation with one member", lambda g: g.update(consolidation={"rule": "r", "count": 1, "members": [{"row_ref": "x", "provenance_raw": {}, "status_history": [{}]}]}))
    good_file = copy.deepcopy(good); good_file.update(status="unvalidated", locations=[dict(F, original={"start_line": 1, "end_line": 3}, end_exclusive_line=3, terminal_newline=True)])
    cases.append(("good normalized file range accepted", not v.errors(good_file)))
    bad("relationship without from/to", lambda g: g.update(claim_kind="relationship", relationship_kind="calls"))
    bad("bad date-time", lambda g: g["status_history"][0].update(at="yesterday"))
    return cases


if __name__ == "__main__":
    schema = json.load(open(sys.argv[1]))
    v = Validator(schema)
    if sys.argv[2] == "--self-test":
        cs = self_test(v)
        for name, ok in cs:
            print(("PASS " if ok else "FAIL ") + name)
        sys.exit(0 if all(ok for _, ok in cs) else 1)
    n = bad = 0
    nulls = 0
    req = schema["required"]
    first: list[tuple[Any, list[str]]] = []
    for line in open(sys.argv[2]):
        r = json.loads(line); n += 1
        e = v.errors(r)
        nulls += sum(1 for k in req if k in r and r[k] is None)
        if e:
            bad += 1
            if len(first) < 10:
                first.append((r.get("claim_id"), e[:5]))
    print(json.dumps({"records": n, "invalid": bad, "valid": n - bad, "null_required_fields": nulls, "first_errors": first}))
    sys.exit(0 if bad == 0 and nulls == 0 else 1)
