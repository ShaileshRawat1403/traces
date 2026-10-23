"""Decision 002-B regression tests RT1 to RT8, ported from research/task002/tests/regression_002b.py.
Pass criteria unchanged; only imports and paths are portable. evaluate(run_dir) returns {"RTn_...": {"result", "detail"}}
and writes regression_results.json."""
import copy, json, os
from collections import Counter
from traces.core.common import Blobs, claim_id, anchor_of, line_count, normalize_file_range
from traces.fixtures.task002.chain import REPO_SHA
from traces.adapter import codegraph as cg_adapter
from traces.validators import orchestrator as orch_mod
from traces.validators.orchestrator import Orchestrator


def evaluate(run_dir):
    RUN = os.path.abspath(str(run_dir))
    SRC = os.path.join(RUN, "real")
    orch_mod.REPO_SHA = REPO_SHA  # [port] the orchestrator takes the SHA as an argument; L2 synthetic checks call lchecks directly
    EV = [json.loads(l) for l in open(os.path.join(RUN, "v1", "validation", "evidence.jsonl"))]
    ADO = json.load(open(os.path.join(RUN, "inside_result.json")))["adapter"]["real"]["out"]
    AD = [json.loads(l) for l in open(os.path.join(ADO, "records.jsonl"))]
    blobs = Blobs(SRC, REPO_SHA)
    out = {}

    def rt(name, ok, detail):
        out[name] = {"result": "PASS" if ok else "FAIL", "detail": detail}

    def kind(r):
        return r.get("relationship_kind") or r.get("node_kind")

    def recompute(r):
        tn = [r["provenance_raw"]["row"]["reference_name"], r["provenance_raw"]["row"]["reference_kind"]] if r["claim_kind"] == "unresolved_reference" else None
        return claim_id(r["repo_sha"], r["claim_kind"], kind(r), r.get("from"), r.get("to"), r["granularity"], r["originator"], anchor_of(r["locations"]), tn)

    # RT1 claim_id: distinct claims never share an id (real data), ids regenerate deterministically from content
    ids = Counter(r["claim_id"] for r in EV); ida = Counter(r["claim_id"] for r in AD)
    mism = [r["claim_id"] for r in EV if recompute(r) != r["claim_id"]]
    rt("RT1_claim_id_unique_and_regenerable", sum(1 for v in ids.values() if v > 1) == 0 and sum(1 for v in ida.values() if v > 1) == 0 and not mism,
       {"evidence_records": len(EV), "distinct_ids": len(ids), "shared_ids_evidence": sum(1 for v in ids.values() if v > 1), "shared_ids_adapter": sum(1 for v in ida.values() if v > 1),
        "ids_not_regenerated_from_content": len(mism)})

    # RT2 claim_id synthetic: location, target name and extractor identity separate claims; identical content gives the same id
    base = dict(repo_sha=REPO_SHA, claim_kind="unresolved_reference", kind="references", frm={"symbol": "a.ts::f", "file": "a.ts", "start_line": 1, "end_line": 9}, to=None, granularity="statement",
                extractor={"name": "codegraph", "version": "1.6.2"}, anchor=["site", "site", "a.ts", 3, 4, 3, None], target_name=["X", "references"])
    cid = lambda **kw: claim_id(**{**base, **kw})
    cases = {"same content same id": cid() == cid(),
             "other line other id": cid() != cid(anchor=["site", "site", "a.ts", 4, 4, 4, None]),
             "other column other id": cid() != cid(anchor=["site", "site", "a.ts", 3, 9, 3, None]),
             "other target name other id": cid() != cid(target_name=["Y", "references"]),
             "other extractor version other id": cid() != cid(extractor={"name": "codegraph", "version": "1.6.3"}),
             "other declared target range other id": claim_id(REPO_SHA, "relationship", "contains", {"symbol": "f::f", "file": "f", "start_line": 1, "end_line": 9}, {"symbol": "f::g", "file": "f", "start_line": 2, "end_line": 3}, "file", base["extractor"], None, None)
                                                      != claim_id(REPO_SHA, "relationship", "contains", {"symbol": "f::f", "file": "f", "start_line": 1, "end_line": 9}, {"symbol": "f::g", "file": "f", "start_line": 5, "end_line": 6}, "file", base["extractor"], None, None)}
    rt("RT2_claim_id_synthetic", all(cases.values()), cases)

    # RT3 exact duplicates consolidate with history; distinct content under one id is refused
    cons = [r for r in AD if r.get("consolidation")]
    def member_rows_equal_except_id(r):
        rows = [{k: v for k, v in m["provenance_raw"]["row"].items() if k != "id"} for m in r["consolidation"]["members"]]
        return all(x == rows[0] for x in rows) and len({m["row_ref"] for m in r["consolidation"]["members"]}) == len(rows) and r["consolidation"]["count"] == len(rows) \
            and r["origin"]["row_ref"] == r["consolidation"]["members"][0]["row_ref"] and all(m["status_history"] for m in r["consolidation"]["members"])
    rep = json.load(open(os.path.join(ADO, "report.json")))
    rows_in = sum(rep["input_rows"][k] for k in ("nodes", "edges", "unresolved_refs"))
    rows_cov = sum(r["consolidation"]["count"] if r.get("consolidation") else 1 for r in AD)
    ev_cons = [r for r in EV if r.get("consolidation")]
    A = cg_adapter.Adapter.__new__(cg_adapter.Adapter)
    r1 = {"claim_id": "c_x", "origin": {"kind": "tool_output", "artifact": "db", "row_ref": "unresolved_refs:10"}, "provenance_raw": {"table": "unresolved_refs", "row": {"id": 10, "line": 3, "reference_name": "X"}},
          "status_history": [{"from": None, "to": "unvalidated", "at": "t", "run_id": "r", "check_ids": [], "by": "a"}], "statement": "s", "locations": [{"file": "a", "start_line": 3}], "run_id": "r"}
    r2 = copy.deepcopy(r1); r2["origin"]["row_ref"] = "unresolved_refs:9"; r2["provenance_raw"]["row"]["id"] = 9
    merged = A.consolidate([copy.deepcopy(r1), copy.deepcopy(r2)])
    syn_ok = len(merged) == 1 and merged[0]["origin"]["row_ref"] == "unresolved_refs:9" and [m["row_ref"] for m in merged[0]["consolidation"]["members"]] == ["unresolved_refs:9", "unresolved_refs:10"] \
        and all(m["status_history"] for m in merged[0]["consolidation"]["members"]) and merged[0]["consolidation"]["members"][1]["provenance_raw"]["row"]["id"] == 10
    r3 = copy.deepcopy(r2); r3["provenance_raw"]["row"]["reference_name"] = "Y"
    try:
        A.consolidate([copy.deepcopy(r1), r3]); refused = False
    except cg_adapter.AdapterError as e:
        refused = e.code == "E_COLLISION"
    rt("RT3_exact_duplicates_consolidate_with_history", bool(cons) and all(member_rows_equal_except_id(r) for r in cons) and rows_cov == rows_in and len(ev_cons) == len(cons) and syn_ok and refused,
       {"consolidated_records": len(cons), "rows_in_consolidated": sum(r["consolidation"]["count"] for r in cons), "by_claim_kind": dict(Counter(r["claim_kind"] for r in cons)),
        "adapter_input_rows": rows_in, "rows_covered_by_records": rows_cov, "consolidated_in_evidence": len(ev_cons), "synthetic_merge_keeps_both_rows_and_history": syn_ok, "distinct_content_same_id_refused_E_COLLISION": refused})


    # L2 check exercised through the real orchestrator code on synthetic blobs
    class FakeBlobs:
        def __init__(self, files): self.f = files
        def exists(self, p): return p in self.f
        def blob_sha(self, p): return "0" * 40
        def text(self, p): return self.f[p]
        def lines(self, p): return self.f[p].split("\n")
    def l2(text, loc):
        O = Orchestrator.__new__(Orchestrator); O.blobs = FakeBlobs({"x.py": text})
        rec = {"claim_kind": "node", "node_kind": "file", "from": {"symbol": "x.py::x.py", "file": "x.py"}, "relationship_kind": None, "provenance_raw": {"row": {"name": "x.py", "kind": "file"}}, "originator": {"name": "codegraph"}}
        loc = dict({"file": "x.py", "role": "from_decl", "blob_sha": "0" * 40, "line_base": 1, "col_base": 0, "source": "originator", "recovered_by": None, "range_rule": "file"}, **loc)
        return [c["result"] for c in O.lchecks(dict(rec, locations=[loc])) if c["method"] == "L2_range_in_file"][0]
    F = lambda s, e: {"range_kind": "file", "start_line": s, "end_line": e}
    S = lambda s, e: {"range_kind": "site", "range_rule": "expression", "role": "site", "start_line": s, "end_line": e}

    # RT4 EOF with a terminal newline
    t = "a\nb\n"; n = normalize_file_range(dict(F(1, 3), file="x.py"), t)
    real = [r for r in AD if r["claim_kind"] == "node" and r["node_kind"] == "file" and r["from"]["file"] == "frontend/src/client/types.gen.ts"][0]["locations"][0]
    c4 = {"line_count('a\\nb\\n') == 2": line_count(t) == 2, "normalized [1,2], exclusive end 3, original end 3": (n["start_line"], n["end_line"], n["end_exclusive_line"], n["original"]["end_line"], n["terminal_newline"]) == (1, 2, 3, 3, True),
          "L2 passes the normalized file range": l2(t, n) == "pass", "L2 rejects a site on the EOF position (line 3)": l2(t, S(3, 3)) == "fail", "L2 passes a site on line 2": l2(t, S(2, 2)) == "pass",
          "L2 rejects an unnormalized file range ending at 3": l2(t, F(1, 3)) == "fail",
          "real types.gen.ts: original end 948, normalized 947, exclusive 948": (real["original"]["end_line"], real["end_line"], real["end_exclusive_line"]) == (948, 947, 948) and line_count(blobs.text("frontend/src/client/types.gen.ts")) == 947}
    rt("RT4_eof_with_terminal_newline", all(c4.values()), c4)

    # RT5 EOF without a terminal newline (synthetic; no indexed file at b1125d8 lacks one) and the empty blob
    t = "a\nb"; n = normalize_file_range(dict(F(1, 2), file="x.py"), t); e = normalize_file_range(dict(F(1, 1), file="x.py"), "")
    no_nl_real = [p for p in {l["file"] for r in AD for l in r["locations"]} if blobs.text(p) and not blobs.text(p).endswith("\n")]
    c5 = {"line_count('a\\nb') == 2": line_count(t) == 2, "normalized [1,2], exclusive end 3, original end 2": (n["start_line"], n["end_line"], n["end_exclusive_line"], n["original"]["end_line"], n["terminal_newline"]) == (1, 2, 3, 2, False),
          "L2 passes the file range": l2(t, n) == "pass", "L2 passes a site on the last line 2": l2(t, S(2, 2)) == "pass", "L2 rejects a site on line 3": l2(t, S(3, 3)) == "fail",
          "empty blob: 0 lines, range [1,0], exclusive end 1, original end 1": (line_count(""), e["end_line"], e["end_exclusive_line"], e["original"]["end_line"], e["terminal_newline"]) == (0, 0, 1, 1, None),
          "empty blob: L2 passes the empty file range": l2("", e) == "pass", "empty blob: L2 rejects a site on line 1": l2("", S(1, 1)) == "fail"}
    rt("RT5_eof_without_terminal_newline_and_empty", all(c5.values()), dict(c5, indexed_files_without_terminal_newline=len(no_nl_real)))

    # RT6 the EOF position is never an evidence location (every location and every check input in the export)
    bad = []; nloc = 0; nfile = 0
    for r in EV:
        for where, locs in [("locations", r["locations"])] + [(f"check {c['method']}", c["inputs"]) for c in r["checks"]]:
            for l in locs:
                nloc += 1; L = line_count(blobs.text(l["file"]))
                if l["range_kind"] == "file":
                    nfile += 1
                    if not (l["start_line"] == 1 and l["end_line"] == L and l.get("end_exclusive_line") == L + 1 and "original" in l):
                        bad.append((r["claim_id"], where, l["file"], l["start_line"], l["end_line"]))
                elif not (1 <= l["start_line"] <= l["end_line"] <= L):
                    bad.append((r["claim_id"], where, l["file"], l["start_line"], l["end_line"]))
    eps = [(r["claim_id"], k) for r in EV for k in ("from", "to") if r.get(k) and r[k].get("end_line") is not None and r[k]["end_line"] > line_count(blobs.text(r[k]["file"]))]
    rt("RT6_eof_never_an_evidence_location", not bad and not eps, {"locations_checked": nloc, "file_ranges": nfile, "violations": bad[:20], "endpoint_violations": eps[:20]})

    # RT7 corrected distribution and visibility
    edges = [r for r in EV if r["originator"]["name"] == "codegraph" and r["claim_kind"] == "relationship"]
    es = Counter(r["status"] for r in edges)
    obs = [r for r in edges if r["status"] == "observed"]
    rej = [r for r in EV if r["status"] == "rejected"]
    c7 = {"edges": len(edges), "by_status": dict(es), "observed_are_import_statements": all(r["relationship_kind"] == "imports" and r.get("qualifier") == "observed import statement" for r in obs),
          "rejected_total": len(rej), "rejected_codegraph": sum(1 for r in rej if r["originator"]["name"] == "codegraph"), "rejected_injected": sum(1 for r in rej if r["injected"]),
          "rejected_all_visible": all(r["visible_to_reviewer"] for r in rej), "old_class_name_present": sum(1 for r in EV if r["class"] == "unverified_inference")}
    rt("RT7_distribution", len(edges) == 4642 and es.get("verified") == 4538 and es.get("observed") == 36 and es.get("unvalidated") == 59 and es.get("rejected") == 9 and c7["observed_are_import_statements"]
       and len(rej) == 12 and c7["rejected_injected"] == 3 and c7["rejected_all_visible"] and c7["old_class_name_present"] == 0, c7)

    # RT8 class is origin only: same class before and after validation for every adapter record
    cls_a = {(r["claim_id"]): r["class"] for r in AD}
    evc = {r["claim_id"]: r["class"] for r in EV}
    changed = [k for k, v in cls_a.items() if evc.get(k) != v]
    rt("RT8_class_independent_of_status", not changed and all(evc.get(k) for k in cls_a), {"adapter_records": len(cls_a), "class_changed_by_validation": len(changed),
       "verified_by_class": dict(Counter(r["class"] for r in EV if r["status"] == "verified")), "observed_by_class": dict(Counter(r["class"] for r in EV if r["status"] == "observed"))})

    res = {"run_id": os.path.basename(RUN), "summary": {k: v["result"] for k, v in out.items()}, "pass": sum(1 for v in out.values() if v["result"] == "PASS"), "total": len(out), "tests": out}
    json.dump(res, open(os.path.join(RUN, "regression_results.json"), "w"), indent=1, default=str)
    return out
