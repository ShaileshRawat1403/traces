"""Builds evidence_record.v0.4.schema.json from the frozen 0.3 schema (Task 002). The 0.4 schema is committed; this
script documents exactly what changed and regenerates it: `python backend/traces/evidence/schema/build_v04.py`.
A unit test checks the committed file equals the output. Decisions: docs/DECISIONS.md D-004 (architect 0.4 rulings)
and the approved history requests in docs/contracts/history.md section 5 (Traces History)."""
import copy
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXT = {"type": "string", "pattern": "^x-[a-z][a-z0-9_]*$"}  # extension values for open enums
SHA = {"type": "string", "pattern": "^[0-9a-f]{40}$"}
PATH = {"type": "string", "pattern": "^(?!/)(?!\\.\\./)(?!.*/\\.\\./).*[^/]$"}
HISTORY_REL = ["commit_adds", "commit_deletes", "commit_modifies", "commit_type_changes", "renamed_to", "copied_to",
               "dependency_added", "dependency_removed", "dependency_version_changed", "component_added", "component_removed",
               "continues_as", "alias_of", "prefix_moved", "co_changed_with", "reverts", "deleted_soon_after_add", "merged_as",
               "documents_rationale", "snapshot_added", "snapshot_removed", "history_impact_candidate"]
HISTORY_CLASSES = ["git_object_fact", "history_pattern", "history_inferred", "documented_rationale", "snapshot_diff"]
HISTORY_FLAGS = ["bot_commit", "generated_path", "merge_commit", "similarity_rename", "rename_detection_limited", "non_utf8_path",
                 "complexity_proxy", "component_map_missing", "pr_sha_mismatch"]
HISTORY_METHODS = ["git_object_check", "git_recount", "quote_match"]
PARSER_FAMILIES = ["cpython-ast", "typescript-compiler"]
STATIC = {"properties": {"evidence_scope": {"const": "static"}}, "required": ["evidence_scope"]}
NONSTATIC = {"properties": {"evidence_scope": {"enum": ["history", "documented"]}}, "required": ["evidence_scope"]}


def merge_if(cond, extra):
    c = copy.deepcopy(cond)
    c.setdefault("properties", {}).update(copy.deepcopy(extra["properties"]))
    c["required"] = sorted(set(c.get("required", [])) | set(extra["required"]))
    return c


def build(s03):
    n = copy.deepcopy(s03)
    n["$id"] = "https://traces.local/schema/traces-evidence/0.4"
    n["title"] = "Traces evidence record, traces-evidence/0.4"
    n["description"] = ("Traces-owned evidence record 0.4. Extends 0.3 (Task 002) with history and documented-rationale records "
                        "(evidence_scope history|documented, history classes, citations, parameters, metrics), entity-typed endpoints, "
                        "open kinds (x- prefix), the reviewer label rejected, the no_source_location flag and review_state. "
                        "No 0.3 value is removed; 0.3 records migrate with traces.evidence.migrate.")
    P = n["properties"]
    P["schema_version"] = {"const": "traces-evidence/0.4"}
    P["relationship_kind"] = {"anyOf": [{"enum": s03["properties"]["relationship_kind"]["enum"] + HISTORY_REL}, EXT]}
    P["granularity"] = {"anyOf": [{"enum": s03["properties"]["granularity"]["enum"] + ["commit", "component", "dependency", "repo"]}, EXT]}
    P["class"]["enum"] = s03["properties"]["class"]["enum"] + HISTORY_CLASSES
    P["originator"]["properties"]["role"] = {"enum": ["extractor", "external", "fixture", "history_analyzer"]}
    pat = s03["properties"]["provenance"]["pattern"]
    P["provenance"]["pattern"] = pat[:-2] + ("|git:(log|diff-tree|ls-tree|cat-file)"
                                             "|history:(replay|lifecycle|cochange|churn|hotspot|revert-match|manifest-diff|alias-suggest|milestone|snapshot-diff|impact)"
                                             "|github-cache:(pr-body|pr-review-comment|pr-metadata)|x-[a-z0-9-]+:[a-z0-9:-]+)$")
    o = P["origin"]["properties"]
    o["kind"] = {"enum": ["tool_output", "external_document", "fixture", "git_object", "history_derived", "cached_pr"]}
    o["commit"] = SHA
    o["paths"] = {"type": "array", "items": PATH}
    P["evidence_scope"] = {"enum": ["static", "history", "documented"], "description": "runtime stays reserved and invalid"}
    P["label"] = {"enum": ["observed", "verified", "inferred", "rejected"]}
    P["flags"] = {"type": "array", "items": {"anyOf": [{"enum": s03["properties"]["flags"]["items"]["enum"] + ["no_source_location"] + HISTORY_FLAGS}, EXT]}}
    P["citations"] = {"type": "array", "items": {"$ref": "#/$defs/citation"}}
    P["parameters"] = {"type": "object", "additionalProperties": False, "required": ["digest", "values"],
                       "properties": {"digest": {"type": "string", "pattern": "^[0-9a-f]{64}$"}, "values": {"type": "object"}}}
    P["metrics"] = {"type": ["object", "null"]}
    P["review_state"] = {"type": "object", "additionalProperties": False, "required": ["state"],
                         "description": "Reviewer annotation. Never changes status, label or class.",
                         "properties": {"state": {"enum": ["none", "confirmed", "disputed"]}, "reviewer": {"type": ["string", "null"]},
                                        "at": {"type": ["string", "null"], "format": "date-time"}, "note": {"type": "string"}}}
    P["migrated_from"] = {"enum": ["traces-evidence/0.3"], "description": "Set by traces.evidence.migrate"}
    D = n["$defs"]
    ep = D["endpoint"]
    ep["required"] = ["symbol"]
    ep["properties"]["entity"] = {"enum": ["symbol", "file", "commit", "component", "dependency", "repo"]}
    ep["allOf"] = [{"if": {"properties": {"entity": {"enum": ["commit", "component", "dependency", "repo"]}}, "required": ["entity"]},
                    "then": {"properties": {"entity": {"type": "string"}}}, "else": {"required": ["file"]}}]
    D["citation"] = {"type": "object", "additionalProperties": False, "required": ["commit", "parents", "paths"], "properties": {
        "commit": SHA, "parents": {"type": "array", "items": SHA},
        "paths": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["path", "status"], "properties": {
            "path": PATH, "old_path": {"type": ["string", "null"]}, "status": {"enum": ["A", "M", "D", "R", "C", "T"]},
            "similarity": {"type": ["integer", "null"]}, "blob_before": {"type": ["string", "null"]}, "blob_after": {"type": ["string", "null"]}}}},
        "pr": {"type": "object", "additionalProperties": False, "required": ["number"], "properties": {
            "number": {"type": "integer", "minimum": 1}, "merge_commit_sha": {"type": ["string", "null"]}, "fetched_at": {"type": "string", "format": "date-time"}}}}}
    c = D["check"]
    c["properties"]["method"]["enum"] = c["properties"]["method"]["enum"] + HISTORY_METHODS
    c["properties"]["rule_id"] = {"anyOf": [{"enum": c["properties"]["rule_id"]["enum"]}, {"type": "string", "pattern": "^(R|H|X)[A-Za-z0-9_-]*$"}]}
    # independent checks: parser families for code; git or text for history methods (separate Git call path)
    c["allOf"][0]["then"]["properties"]["validator"]["properties"]["family"]["enum"] = PARSER_FAMILIES + ["git", "text"]
    c["allOf"].append({"if": {"properties": {"method": {"enum": ["parser_presence"]}, "independent": {"const": True}}, "required": ["method", "independent"]},
                       "then": {"properties": {"validator": {"properties": {"family": {"enum": PARSER_FAMILIES}}}}}})
    c["allOf"].append({"if": {"properties": {"method": {"enum": HISTORY_METHODS}}, "required": ["method"]},
                       "then": {"properties": {"establishes": {"const": "presence"}, "validator": {"properties": {"family": {"enum": ["git", "text"]}}}}}})
    NA = []
    for rule in s03["allOf"]:
        cond = rule["if"].get("properties", {})
        st = cond.get("status", {})
        if st == {"const": "verified"}:
            r = copy.deepcopy(rule)
            r["then"]["properties"]["evidence_scope"] = {"const": "static"}
            NA.append(r)
        elif st == {"const": "observed"} or st == {"not": {"const": "missing_location"}}:
            NA.append({"if": merge_if(rule["if"], STATIC), "then": rule["then"]})  # 0.3 rule, static records only
        elif st == {"enum": ["unvalidated", "missing_location", "rejected"]}:
            NA.append({"if": {"properties": {"status": {"enum": ["unvalidated", "missing_location", "rejected"]}}, "required": ["status"]}, "then": {"required": ["status_reason"]}})
            NA.append({"if": {"properties": {"status": {"enum": ["unvalidated", "missing_location"]}}, "required": ["status"]}, "then": {"properties": {"label": {"const": "inferred"}}}})
            NA.append({"if": {"properties": {"status": {"const": "rejected"}}, "required": ["status"]}, "then": {"properties": {"label": {"const": "rejected"}}}})
            NA.append({"if": {"properties": {"status": {"const": "missing_location"}}, "required": ["status"]},
                       "then": {"required": ["flags"], "properties": {"flags": {"contains": {"const": "no_source_location"}}}}})
        elif rule["if"].get("properties", {}).get("claim_kind") == {"const": "relationship"} and "status" not in cond:
            NA.append(rule)
        else:
            NA.append(rule)
    # history and documented records: cite commits (locations may be empty), never verified
    NA.append({"if": NONSTATIC, "then": {"required": ["citations"], "properties": {
        "citations": {"minItems": 1}, "status": {"enum": ["observed", "unvalidated", "rejected"]},
        "class": {"enum": HISTORY_CLASSES + ["analyzer_inference"]}}}})
    NA.append({"if": {"properties": {"class": {"enum": HISTORY_CLASSES}}, "required": ["class"]},
               "then": {"properties": {"evidence_scope": {"enum": ["history", "documented"]}, "status": {"not": {"const": "verified"}}}}})
    NA.append({"if": {"properties": {"class": {"const": "history_inferred"}}, "required": ["class"]},
               "then": {"properties": {"status": {"enum": ["unvalidated", "rejected"]}}}})
    NA.append({"if": {"properties": {"class": {"const": "documented_rationale"}}, "required": ["class"]},
               "then": {"properties": {"evidence_scope": {"const": "documented"}}}})
    NA.append({"if": {"properties": {"evidence_scope": {"const": "documented"}}, "required": ["evidence_scope"]},
               "then": {"properties": {"class": {"enum": ["documented_rationale", "analyzer_inference"]}}}})
    NA.append({"if": merge_if({"properties": {"status": {"const": "observed"}}, "required": ["status"]}, NONSTATIC),
               "then": {"required": ["qualifier"], "properties": {"label": {"const": "observed"}, "qualifier": {"type": "string", "minLength": 1},
                        "checks": {"contains": {"type": "object", "required": ["independent", "result", "method"], "properties": {
                            "independent": {"const": True}, "result": {"const": "pass"}, "method": {"enum": HISTORY_METHODS}}}}}}})
    NA.append({"if": {"properties": {"origin": {"properties": {"kind": {"const": "cached_pr"}}, "required": ["kind"]}}, "required": ["origin"]},
               "then": {"properties": {"origin": {"required": ["artifact", "sha256", "quote"]}}}})
    NA.append({"if": {"properties": {"class": {"const": "history_pattern"}}, "required": ["class"]}, "then": {"required": ["parameters"]}})
    n["allOf"] = NA
    return n


if __name__ == "__main__":
    import sys

    s03 = json.loads((HERE / "evidence_record.v0.3.schema.json").read_text())
    text = json.dumps(build(s03), indent=1) + "\n"
    if "--stdout" in sys.argv:
        sys.stdout.write(text)
    else:
        (HERE / "evidence_record.v0.4.schema.json").write_text(text)
