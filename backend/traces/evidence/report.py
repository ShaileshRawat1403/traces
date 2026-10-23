"""Task 002 steps 8 to 10 summaries from one validation output: chain.json (L1 to L9, H1, H2, N1, N2) and coverage.json.
Port of research/task002/pipeline/report.py (review F7); logic unchanged, paths portable. Read-only over evidence.jsonl.
The baseline pipeline runs it after the first validation; it writes only into the validation directory.
Usage: python -m traces.evidence.report <validation_dir>"""
import json, os, sys
from collections import Counter


def run(VD):
    VD = os.path.abspath(VD)
    ev = [json.loads(l) for l in open(os.path.join(VD, "evidence.jsonl"))]
    FIX = {r["origin"]["fixture_id"]: r for r in ev if r["originator"]["name"] == "traces-lab-fixture"}
    INJ = {(r["origin"].get("fixture_id") or "N1"): r for r in ev if r["injected"]}
    CG = [r for r in ev if r["originator"]["name"] == "codegraph"]

    def brief(r, full=False):
        d = {"claim_id": r["claim_id"], "originator": r["originator"]["name"], "class": r["class"], "provenance": r["provenance"], "kind": r.get("relationship_kind") or r["claim_kind"],
             "from": (r.get("from") or {}).get("symbol"), "to": (r.get("to") or {}).get("symbol"), "status": r["status"], "label": r["label"], "status_reason": r.get("status_reason"),
             "qualifier": r.get("qualifier"), "flags": r["flags"], "injected": r["injected"], "row_ref": r["origin"].get("row_ref"),
             "sites": [f"{l['file']}:{l['start_line']}" + (f"-{l['end_line']}" if l['end_line'] != l['start_line'] else "") + f" ({l['range_kind']}, {l['source']})" for l in r["locations"] if l["role"] == "site"],
             "establishing_checks": [{"check_id": c["check_id"], "method": c["method"], "rule_id": c["rule_id"], "family": c["validator"]["family"], "result": c["result"], "independent": c["independent"], "detail": c["detail"][:600]}
                                     for c in r["checks"] if c["establishes"] == "relationship" or (c["method"] == "parser_presence")]}
        if full:
            d["all_locations"] = [f"{l['file']}:{l['start_line']}-{l['end_line']} {l['role']} {l['range_kind']} {l['source']}" for l in r["locations"]]
        return d


    def cg(pred):
        return [r for r in CG if pred(r)]


    IT, AT, SDK, ITEMS, DEPS, MODELS = "frontend/src/routes/_layout/items.tsx", "frontend/src/components/Items/AddItem.tsx", "frontend/src/client/sdk.gen.ts", "backend/app/api/routes/items.py", "backend/app/api/deps.py", "backend/app/models.py"
    sym = lambda r, k: (r.get(k) or {}).get("symbol") or ""
    rk = lambda r: r.get("relationship_kind")
    row_line = lambda r: (r["provenance_raw"].get("row") or {}).get("line")
    LINKS = {
        "L1": (["L1"], cg(lambda r: rk(r) == "renders" and sym(r, "from") == f"{IT}::Items" and sym(r, "to") == f"{AT}::AddItem"), []),
        "L2": (["L2A", "L2B"], cg(lambda r: rk(r) == "references" and sym(r, "from") == f"{AT}::AddItem" and sym(r, "to").endswith("::onSubmit") and row_line(r) == 88),
               cg(lambda r: r["claim_kind"] == "unresolved_reference" and r["locations"][0]["file"] == AT and r["locations"][0]["start_line"] == 69)),
        "L3": (["L3"], cg(lambda r: rk(r) == "calls" and sym(r, "from") == f"{AT}::AddItem" and sym(r, "to") == f"{SDK}::ItemsService::createItem" and row_line(r) == 56), []),
        "L4": (["L4"], [], cg(lambda r: rk(r) == "references" and sym(r, "from") == f"{SDK}::ItemsService::createItem" and "itemsCreateItemData" in sym(r, "to"))),
        "L5": (["L5"], cg(lambda r: rk(r) == "references" and sym(r, "from").startswith(f"{ITEMS}::") and "POST" in sym(r, "from") and sym(r, "to") == f"{ITEMS}::create_item" and row_line(r) == 61), []),
        "L6": (["L6"], [], cg(lambda r: (rk(r) == "imports" and sym(r, "from") == f"{ITEMS}::{ITEMS}" and sym(r, "to").endswith("::SessionDep")) or (sym(r, "from") == f"{DEPS}::SessionDep" and sym(r, "to") == f"{DEPS}::get_db"))),
        "L7": (["L7"], [], cg(lambda r: (rk(r) == "imports" and sym(r, "from") == f"{ITEMS}::{ITEMS}" and sym(r, "to").endswith("::CurrentUser")) or (sym(r, "from") == f"{DEPS}::CurrentUser" and sym(r, "to") == f"{DEPS}::get_current_user"))),
        "L8": (["L8"], [], cg(lambda r: r["claim_kind"] == "unresolved_reference" and r["locations"][0]["file"] == ITEMS and 68 <= r["locations"][0]["start_line"] <= 71)),
        "L9": (["L9A", "L9B"], [], cg(lambda r: r["claim_kind"] == "node" and sym(r, "from") in (f"{MODELS}::Item", f"{MODELS}::ItemPublic"))),
    }
    chain = {"run_id": ev[0]["run_id"], "repo_sha": ev[0]["repo_sha"], "rule": "EXPECTED_CHAIN 'How a link reaches verified': fixture claim(s) verified and every CodeGraph claim for the same link verified or unvalidated with a stated reason", "links": {}}
    for L, (fids, same, ctx) in LINKS.items():
        fx = [FIX[f] for f in fids]
        same_ok = all(r["status"] == "verified" or (r["status"] == "unvalidated" and r.get("status_reason")) for r in same)
        st = "verified" if all(r["status"] == "verified" for r in fx) and same_ok else "not verified"
        why = None if st == "verified" else "; ".join([f"{r['origin']['fixture_id']}: {r['status']} ({r.get('status_reason')})" for r in fx if r["status"] != "verified"] + [f"CodeGraph {r['claim_id']}: {r['status']}" for r in same if not (r["status"] == "verified" or (r["status"] == "unvalidated" and r.get("status_reason")))])
        chain["links"][L] = {"link_status": st, "reason": why, "fixture_claims": [brief(r, True) for r in fx], "codegraph_same_link": [brief(r) for r in same], "codegraph_context": [brief(r) for r in ctx]}
    chain["transitive_L7"] = {k: brief(FIX[k], True) for k in ("L7T1", "L7T2")}
    chain["library_hops"] = {k: brief(FIX[k], True) for k in ("H1", "H2")}
    chain["negative_controls"] = {k: brief(v, True) for k, v in sorted(INJ.items())}
    chain["summary"] = {L: v["link_status"] for L, v in chain["links"].items()}
    json.dump(chain, open(os.path.join(VD, "chain.json"), "w"), indent=1, ensure_ascii=False)

    # ---------- coverage (step 10) ----------
    c = lambda it: dict(sorted(Counter(it).items(), key=lambda kv: str(kv[0])))
    edges = [r for r in CG if r["claim_kind"] == "relationship"]
    cov = {"run_id": ev[0]["run_id"], "records_total": len(ev),
           "by_originator": c(r["originator"]["name"] for r in ev), "injected": c(r["injected"] for r in ev),
           "codegraph": {"records": len(CG), "by_claim_kind": c(r["claim_kind"] for r in CG), "by_status": c(r["status"] for r in CG), "by_label": c(r["label"] for r in CG),
                         "by_class": c(r["class"] for r in CG), "by_provenance": c(r["provenance"] for r in CG),
                         "by_claim_kind_status": c(f"{r['claim_kind']}|{r['status']}" for r in CG),
                         "edges": {"count": len(edges), "with_normalized_provenance": sum(1 for r in edges if r["provenance"].startswith("codegraph:")),
                                   "with_originator_and_version": sum(1 for r in edges if r["originator"]["name"] == "codegraph" and r["originator"]["version"] == "1.6.2"),
                                   "with_location_after_validation": sum(1 for r in edges if r["locations"]), "by_status": c(r["status"] for r in edges), "by_label": c(r["label"] for r in edges),
                                   "by_kind_status": c(f"{r['relationship_kind']}|{r['status']}" for r in edges), "by_provenance_status": c(f"{r['provenance']}|{r['status']}" for r in edges),
                                   "raw_provenance_unset": sum(1 for r in edges if (r["provenance_raw"]["row"].get("provenance") is None)), "raw_provenance_unset_baseline_plan": 4351},
                         "name_match_616_by_label": c(r["label"] for r in edges if r["provenance"] == "codegraph:name-match"),
                         "name_match_616_by_status": c(r["status"] for r in edges if r["provenance"] == "codegraph:name-match")},
           "fixture": {k: {"status": v["status"], "label": v["label"]} for k, v in sorted(FIX.items())},
           "injected_records": {k: {"status": v["status"], "label": v["label"], "visible_to_reviewer": v["visible_to_reviewer"]} for k, v in sorted(INJ.items())}}
    cont = [r for r in edges if r["relationship_kind"] == "contains"]
    rc = lambda r, m, res: any(ch["method"] == m and ch.get("rule_id") == "R-contains" and ch["result"] == res for ch in r["checks"])
    cov["recovery"] = {"contains_total": len(cont), "R_contains_location_recovery_pass": sum(1 for r in cont if rc(r, "location_recovery", "pass")),
                       "R_contains_syntax_structure_pass": sum(1 for r in cont if rc(r, "syntax_structure", "pass")), "contains_with_locations": sum(1 for r in cont if r["locations"]),
                       "contains_by_status": c(r["status"] for r in cont), "expected": "all 1,893 gain a location; 1,891 verified; 2 exceptions unvalidated (EVIDENCE_SCHEMA 7)",
                       "contains_not_verified": [{"from": sym(r, "from"), "to": sym(r, "to"), "status": r["status"], "reason": r.get("status_reason")} for r in cont if r["status"] != "verified"]}
    vr = [r for r in edges if r["provenance"] == "codegraph:value-ref"]
    cov["recovery"]["value_ref"] = {"total": len(vr), "location_recovery_pass": sum(1 for r in vr if any(ch["method"] == "location_recovery" and ch["result"] == "pass" for ch in r["checks"])), "by_status": c(r["status"] for r in vr)}
    jsx = [r for r in edges if r["provenance"] == "codegraph:synthesized:jsx-render"]
    cov["recovery"]["jsx_render_R_enclosing"] = {"total": len(jsx), "location_recovery_pass": sum(1 for r in jsx if any(ch["method"] == "location_recovery" and ch.get("rule_id") == "R-enclosing" and ch["result"] == "pass" for ch in r["checks"])), "by_status": c(r["status"] for r in jsx)}
    # Decision 002-B: EOF normalization, import statements, consolidation, claim_id uniqueness
    def all_locs(r):
        yield from r["locations"]
        for ch in r["checks"]:
            yield from ch["inputs"]
    eof_recs = [r for r in ev if any(l.get("original") and l["original"]["end_line"] == l["end_line"] + 1 for l in r["locations"])]
    eof_locs = sum(1 for r in ev for l in r["locations"] if l.get("original") and l["original"]["end_line"] == l["end_line"] + 1)
    imp_obs = [r for r in edges if r["status"] == "observed"]
    cons = [r for r in ev if r.get("consolidation")]
    ids = Counter(r["claim_id"] for r in ev)
    cov["decision_002B"] = {
        "eof": {"records_with_normalized_file_range": len(eof_recs), "file_range_locations_normalized": eof_locs,
                "by_claim_kind_status": c(f"{r['claim_kind']}|{r.get('relationship_kind') or r.get('node_kind')}|{r['status']}" for r in eof_recs),
                "rule": "whole-file range [1, n] with exclusive end boundary n + 1; the EOF position after a final newline is never an addressable line or evidence location; original coordinates kept in location.original"},
        "import_statements_observed": {"count": len(imp_obs), "by_language": c(r["from"]["file"].rsplit(".", 1)[-1] for r in imp_obs), "qualifier": sorted({r.get("qualifier") for r in imp_obs}, key=str)},
        "consolidation": {"records": len(cons), "rows": sum(r["consolidation"]["count"] for r in cons), "by_claim_kind": c(r["claim_kind"] for r in cons)},
        "claim_id": {"records": len(ev), "distinct": len(ids), "shared_ids": sum(1 for v in ids.values() if v > 1)}}
    cov["notes"] = {"verified_without_independent_pass": sum(1 for r in ev if r["status"] == "verified" and not any(ch["independent"] and ch["result"] == "pass" and ch["establishes"] == "relationship" for ch in r["checks"])),
                    "L2_line_count_rule": "Decision 002-B: L2 counts addressable lines (newline count, plus 1 when the blob does not end in a newline); whole-file ranges end on the last addressable line with an exclusive EOF boundary"}
    json.dump(cov, open(os.path.join(VD, "coverage.json"), "w"), indent=1, ensure_ascii=False)
    return chain, cov


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        raise SystemExit("usage: python -m traces.evidence.report <validation_dir>")
    chain, _ = run(argv[0])
    print("report: chain", chain["summary"])


if __name__ == "__main__":
    main()
