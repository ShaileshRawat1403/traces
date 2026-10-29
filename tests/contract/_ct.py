"""Contract tests CT1 to CT16 (ADAPTER_CONTRACT v2 section 7, with Decision 002-B amendments), ported from
research/task002/tests/ct_evaluate.py. The pass criteria are unchanged except where marked [port]; see
docs/TEST_MAPPING.md. evaluate(run_dir) returns {"CTn": {"result", "evidence", "detail"}} and writes ct_results.json."""
import json, os, re, sqlite3
from collections import Counter
from traces.core.common import Blobs
from traces.fixtures.task002.chain import REPO_SHA as SHA


def evaluate(run_dir):
    RUN = os.path.abspath(str(run_dir)); R = json.load(open(os.path.join(RUN, "inside_result.json")))
    SRC = os.path.join(RUN, "real")
    rel = lambda p: os.path.relpath(p, RUN)
    ADO = R["adapter"]["real"]["out"]
    recs = [json.loads(l) for l in open(os.path.join(ADO, "records.jsonl"))]
    rep = json.load(open(os.path.join(ADO, "report.json")))
    EVP = os.path.join(RUN, "v1", "validation", "evidence.jsonl")
    ev = [json.loads(l) for l in open(EVP)]
    db = sqlite3.connect(f"file:{SRC}/.codegraph/codegraph.db?mode=ro&immutable=1", uri=True); db.row_factory = sqlite3.Row
    out = {}

    def ct(i, ok, evidence, detail):
        out[f"CT{i}"] = {"result": "PASS" if ok else "FAIL", "evidence": evidence, "detail": detail}

    neg = R["negative"]
    ncode = lambda k: (neg[k]["errors"] or {}).get("code")
    nrec = lambda k: os.path.exists(os.path.join(neg[k]["out"], "records.jsonl"))
    # CT1
    ok = ncode("CT1a_version_1.6.3") == "E_VERSION" and ncode("CT1b_wrong_integrity") == "E_VERSION" and not nrec("CT1a_version_1.6.3") and not nrec("CT1b_wrong_integrity") \
         and any(s.startswith("4.1") for s in rep["checks_passed"]) and any("4.2" in s or "4.3" in s for s in rep["checks_passed"])
    ct(1, ok, [rel(neg[k]["out"]) + "/errors.json" for k in ("CT1a_version_1.6.3", "CT1b_wrong_integrity")] + [rel(ADO) + "/report.json"],
       {k: neg[k]["errors"] for k in ("CT1a_version_1.6.3", "CT1b_wrong_integrity")} | {"real_checks_passed": rep["checks_passed"]})
    # CT2
    d2a, d2b = neg["CT2a_edges_provenance_renamed"]["errors"] or {}, neg["CT2b_no_unresolved_refs"]["errors"] or {}
    ct(2, d2a.get("code") == "E_SCHEMA" and "edges.provenance" in d2a.get("detail", "") and d2b.get("code") == "E_SCHEMA" and "unresolved_refs" in d2b.get("detail", "") and not nrec("CT2a_edges_provenance_renamed") and not nrec("CT2b_no_unresolved_refs"),
       [rel(neg[k]["out"]) + "/errors.json" for k in ("CT2a_edges_provenance_renamed", "CT2b_no_unresolved_refs")], {"CT2a": d2a.get("detail"), "CT2b": d2b.get("detail")})
    # CT3
    ks = ("CT3a_byte_changed", "CT3b_head_minus_1", "CT3c_manifest_other_sha")
    ct(3, all(ncode(k) == "E_SHA" and not nrec(k) for k in ks) and R["adapter"]["real"]["exit"] == 0, [rel(neg[k]["out"]) + "/errors.json" for k in ks],
       {k: neg[k]["errors"]["detail"] for k in ks} | {"clean_checkout": R["adapter"]["real"]["stdout"]})
    # CT4: every real edge maps to one normalized value, provenance_raw equals the row
    rows = {f"edges:{r['id']}": dict(r) for r in db.execute("select * from edges")}
    er = [r for r in recs if r["origin"]["row_ref"].startswith("edges:")]
    mism = [r["origin"]["row_ref"] for r in er if {k: v for k, v in r["provenance_raw"]["row"].items()} != {k: v for k, v in rows[r["origin"]["row_ref"]].items() if k in r["provenance_raw"]["row"]} or set(r["provenance_raw"]["row"]) - set(rows[r["origin"]["row_ref"]])]
    cols_missing = [r["origin"]["row_ref"] for r in er if set(rows[r["origin"]["row_ref"]]) - set(r["provenance_raw"]["row"])]
    nm = [r for r in er if r["provenance"] == "codegraph:name-match"]
    ok = len(er) == len(rows) == 4642 and not mism and not cols_missing and all(r["provenance"] for r in er) and len(nm) == 616 and all(r["class"] == "analyzer_inference" for r in nm) and ncode("CT4_resolvedBy_guess") == "E_PROVENANCE_UNKNOWN"  # [002-B] ruling 5 rename
    ct(4, ok, [rel(ADO) + "/records.jsonl", rel(neg["CT4_resolvedBy_guess"]["out"]) + "/errors.json"],
       {"edge_records": len(er), "edge_rows": len(rows), "provenance_raw_row_mismatch": len(mism), "row_columns_missing_in_raw": len(cols_missing), "by_provenance": dict(Counter(r["provenance"] for r in er)), "name_match": len(nm),
        "name_match_classes": dict(Counter(r["class"] for r in nm)), "copy": neg["CT4_resolvedBy_guess"]["errors"]})
    # CT5
    s5 = json.load(open(os.path.join(RUN, "schema_adapter.json"))); st = open(os.path.join(RUN, "schema_selftest.txt")).read().strip().splitlines()
    st_ok = bool(st) and all(l.startswith("PASS ") for l in st)  # [002-B] the self-test must have run and passed (it crashed unnoticed in 1049-3)
    ct(5, s5["invalid"] == 0 and s5["null_required_fields"] == 0 and s5["records"] == len(recs) and st_ok, [rel(RUN) + "/schema_adapter.json", rel(RUN) + "/schema_selftest.txt"], {"schema_check": s5, "validator_self_test": f"{sum(1 for l in st if l.startswith('PASS '))}/{len(st)} PASS" if st else None,
       "note": "jsonschema package not installed (install needs network, plan S4); validated with validators/schema_check.py, a stdlib Draft 2020-12 subset that raises on any keyword it does not implement"})
    # CT6
    c6 = Counter(r["status"] for r in recs); l6 = Counter(r["label"] for r in recs)
    ct(6, c6.get("observed", 0) == 0 and c6.get("verified", 0) == 0 and l6.get("inferred", 0) == len(recs), [rel(ADO) + "/records.jsonl"], {"by_status": dict(c6), "by_label": dict(l6)})
    # CT7
    ck = json.load(open(os.path.join(RUN, "checker_parser.json"))); lr = json.load(open(os.path.join(RUN, "checker_lab_route.json")))  # [port] Lab B verbatim script output dropped: it was evidence only, never in the pass criterion
    shaok = "OK" in open(os.path.join(RUN, "checker_sha256.txt")).read() and "FAILED" not in open(os.path.join(RUN, "checker_sha256.txt")).read()
    nodes_ad = {(r["provenance_raw"]["row"]["kind"], r["provenance_raw"]["row"]["file_path"], r["provenance_raw"]["row"]["name"], r["provenance_raw"]["row"]["start_line"]) for r in recs if r["claim_kind"] == "node"}
    ck_nodes = [(n["kind"], n["file"], n["name"], n["start_line"]) for n in ck["nodes"]]
    joined = sum(1 for n in ck_nodes if n in nodes_ad)
    miss = ck["not_exact"]
    so = [r for r in ev if r["claim_kind"] == "node" and r["from"]["symbol"] == "frontend/src/components/ui/sidebar.tsx::SidebarProvider::setOpen"]
    so_ok = bool(so) and any(l["source"] == "validator" and l["range_kind"] == "declaration" and l["start_line"] == 86 for l in so[0]["locations"]) and "extractor_location_is_body" in so[0]["flags"]
    ok = shaok and ck["total"] == 379 and ck["exact"] == 378 and len(miss) == 1 and "setOpen" in json.dumps(miss[0]) and so_ok and joined == 379
    ct(7, ok, [rel(RUN) + f for f in ("/checker_parser.json", "/checker_lab_route.json", "/checker_sha256.txt")] + [rel(EVP)],
       {"parser": f"{ck['exact']}/{ck['total']}", "miss": miss, "lab_route": f"{lr['exact']}/{lr['total']}", "checker_sha256": open(os.path.join(RUN, "checker_sha256.txt")).read().strip(),
        "checker_nodes_joined_to_adapter_node_records": f"{joined}/{len(ck_nodes)}", "setOpen_after_validation": {"status": so[0]["status"], "status_reason": so[0].get("status_reason"), "flags": so[0]["flags"], "locations": [(l["start_line"], l["end_line"], l["range_kind"], l["source"]) for l in so[0]["locations"]]} if so else None})
    # CT8
    ml = [r for r in recs if r["status"] == "missing_location"]
    mlk = Counter(r["relationship_kind"] for r in ml)
    cont = [r for r in ev if r["originator"]["name"] == "codegraph" and r.get("relationship_kind") == "contains"]
    rec_pass = sum(1 for r in cont if any(c["method"] == "syntax_structure" and c["rule_id"] == "R-contains" and c["result"] == "pass" for c in r["checks"]))
    gained = sum(1 for r in cont if r["locations"])
    exc = {(r["from"]["symbol"].split("::")[-1], r["to"]["symbol"].split("::")[-1]): (r["status"], r.get("status_reason")) for r in cont if r["status"] != "verified"}
    want = {("createSseClient", "abortHandler"): ("unvalidated", "transitive containment, immediate parent not a node"), ("SidebarProvider", "setOpen"): ("unvalidated", "declaration line differs from extractor line")}
    ml_rej_after = sum(1 for r in ev if r["originator"]["name"] == "codegraph" and r["status_history"][0]["to"] == "missing_location" and r["status"] == "rejected")
    ok = len(ml) == 1981 and mlk.get("contains") == 1893 and mlk.get("references") == 88 and not any(r["status"] == "rejected" for r in recs) and rec_pass == 1891 and exc == want and ml_rej_after == 0
    ct(8, ok, [rel(ADO) + "/records.jsonl", rel(EVP)], {"adapter_missing_location": len(ml), "by_kind": dict(mlk), "adapter_rejected": sum(1 for r in recs if r["status"] == "rejected"),
       "R_contains_syntax_structure_pass": rec_pass, "contains_records_with_locations_after_validation": gained, "exceptions": {f"{a} -> {b}": v for (a, b), v in exc.items()}, "missing_location_records_rejected_after_validation": ml_rej_after,
       "note": "R-contains location_recovery adds locations to all 1,893 (setOpen matches as a body location, abortHandler at its real ancestor); 1,891 pass syntax_structure and are verified; the 2 exceptions stay unvalidated"})
    # CT9
    blobs = Blobs(SRC, SHA)
    paths = set()
    for r in recs:
        for l in r["locations"]:
            paths.add(l["file"])
        for k in ("from", "to"):
            if r.get(k):
                paths.add(r[k]["file"])
    bad = [p for p in paths if p.startswith("/") or ".." in p.split("/") or "\\" in p or not blobs.exists(p)]
    ct(9, not bad and ncode("CT9a_absolute_path") == "E_PATH" and ncode("CT9b_dotdot_path") == "E_PATH", [rel(ADO) + "/records.jsonl"] + [rel(neg[k]["out"]) + "/errors.json" for k in ("CT9a_absolute_path", "CT9b_dotdot_path")],
       {"distinct_paths": len(paths), "bad_paths": bad, "CT9a": neg["CT9a_absolute_path"]["errors"]["detail"], "CT9b": neg["CT9b_dotdot_path"]["errors"]["detail"]})
    # CT10
    un = [r for r in recs if r["claim_kind"] == "unresolved_reference"]
    nun = db.execute("select count(*) from unresolved_refs").fetchone()[0]
    ci = [r for r in un if r["from"]["symbol"] == "backend/app/api/routes/items.py::create_item"]
    # [002-B] ruling 2: exact duplicate rows consolidate into one record; every row stays attached (consolidation.members)
    covered = sum(r["consolidation"]["count"] if r.get("consolidation") else 1 for r in un)
    ct(10, covered == nun == 3314 and all(any(l["role"] == "site" for l in r["locations"]) for r in un) and len(ci) == 5 and all(68 <= r["locations"][0]["start_line"] <= 71 for r in ci),
       [rel(ADO) + "/records.jsonl"], {"unresolved_records": len(un), "rows": nun, "rows_covered_incl_consolidated": covered, "consolidated_records": sum(1 for r in un if r.get("consolidation")),
                                       "create_item": sorted((r["locations"][0]["start_line"], r["provenance_raw"]["row"]["reference_name"]) for r in ci)})
    # CT11
    gen = {r["path"] for r in db.execute("select path from files where generated = 1")}
    def rfile(r):
        return r["from"]["file"] if r.get("from") else r["locations"][0]["file"]
    miss11 = [r["claim_id"] for r in recs if rfile(r) in gen and "generated_file" not in r["flags"]]
    extra11 = [r["claim_id"] for r in recs if rfile(r) not in gen and "generated_file" in r["flags"]]
    ct(11, not miss11 and not extra11, [rel(ADO) + "/records.jsonl"], {"generated_files": len(gen), "records_from_generated": sum(1 for r in recs if rfile(r) in gen), "missing_flag": len(miss11), "flag_on_others": len(extra11),
       "rule": "record's file = from.file (source endpoint or node), else its first location"})
    # CT12
    def has(kind, frm, to, line, rk=None):
        for r in recs:
            if r["claim_kind"] != "relationship" or r["relationship_kind"] != kind or r["label"] != "inferred":
                continue
            if frm(r["from"]["symbol"]) and to(r["to"]["symbol"]) and any(l["start_line"] == line and (rk is None or l["range_kind"] == rk) for l in r["locations"]):
                return r["claim_id"]
        return None
    AT = "frontend/src/components/Items/AddItem.tsx"
    want12 = {
        "AddItem calls ItemsService::createItem at AddItem.tsx:56": has("calls", lambda s: s == f"{AT}::AddItem", lambda s: s.endswith("sdk.gen.ts::ItemsService::createItem"), 56),
        "AddItem references onSubmit at AddItem.tsx:88": has("references", lambda s: s == f"{AT}::AddItem", lambda s: s.endswith("::onSubmit"), 88),
        "route POST /items (items.py:61) references create_item": has("references", lambda s: s.startswith("backend/app/api/routes/items.py::") and "POST" in s, lambda s: s == "backend/app/api/routes/items.py::create_item", 61),
        "CurrentUser references get_current_user at deps.py:49": has("references", lambda s: s == "backend/app/api/deps.py::CurrentUser", lambda s: s == "backend/app/api/deps.py::get_current_user", 49),
        "users.py::create_user calls crud.py::create_user at users.py:68": has("calls", lambda s: s == "backend/app/api/routes/users.py::create_user", lambda s: s == "backend/app/crud.py::create_user", 68),
        "login.py::login_access_token calls crud.py::authenticate at login.py:30": has("calls", lambda s: s == "backend/app/api/routes/login.py::login_access_token", lambda s: s == "backend/app/crud.py::authenticate", 30),
        "Items renders AddItem (enclosing_scope at items.tsx:57)": has("renders", lambda s: s == "frontend/src/routes/_layout/items.tsx::Items", lambda s: s == f"{AT}::AddItem", 57, "enclosing_scope")}
    ct(12, all(want12.values()), [rel(ADO) + "/records.jsonl"], want12)
    # CT13
    a13 = [r["claim_id"] for r in recs if r["claim_kind"] == "relationship" and r["from"]["symbol"] == "backend/app/api/routes/items.py::create_item" and r["to"]["file"] == "backend/app/crud.py"]
    b13 = [r["claim_id"] for r in recs if r.get("relationship_kind") == "depends_on"]
    c13 = [r["claim_id"] for r in recs if not r["origin"]["row_ref"].split(":")[0] in ("nodes", "edges", "unresolved_refs") or (r["origin"]["row_ref"].startswith("unresolved_refs:") and r["claim_kind"] != "unresolved_reference") or "impact" in json.dumps(r["origin"])]
    ct(13, not a13 and not b13 and not c13, [rel(ADO) + "/records.jsonl"], {"create_item_to_crud": len(a13), "depends_on": len(b13), "synthesized_from_unresolved_or_impact": len(c13)})
    # CT14
    h = R["canonical_hash"]; ix = R["index_runs"]
    ct(14, len(set(h.values())) == 1 and None not in h.values() and all(v["exit"] == 0 for v in ix.values()), [rel(RUN) + "/inside_result.json"] + [rel(R["adapter"][k]["out"]) + "/records.jsonl" for k in h],
       {"canonical_sha256": h, "index_runs": {k: {"exit": v["exit"], "dir": rel(v["dir"])} for k, v in ix.items()}, "validation_runs_hash": {k: v.get("canonical_hash") for k, v in R["validation"].items()}})
    # CT15
    np_ = open(os.path.join(RUN, "netprobe.log")).read()
    ps = re.search(r"^PROBE_SUMMARY (.*)$", np_, re.M); kv = dict(x.split("=", 1) for x in ps.group(1).split()) if ps else {}
    cs = re.search(r"^CONTROL_SUMMARY (.*)$", np_, re.M)
    # [002-B] no extraction in this run: indexer evidence comes from the reused run's own log, compared with that run's wrapper namespace
    reused = os.path.join(RUN, "netprobe_index_reused.log")  # [port] never present: the port indexes fresh every run
    np_idx = np_
    isum = re.findall(r"^INDEXER_SUMMARY (.*)$", np_idx, re.M)
    iproc = re.findall(r"^INDEXER_PROC pid=\d+ netns=(\S+)", np_idx, re.M)
    ps_idx = re.search(r"^PROBE_SUMMARY (.*)$", np_idx, re.M); kv_idx = dict(x.split("=", 1) for x in ps_idx.group(1).split()) if ps_idx else {}
    s_b, s_a = open(os.path.join(RUN, "snapshot_before.txt")).read(), open(os.path.join(RUN, "snapshot_after.txt")).read()
    strip = lambda s: "\n".join(l for l in s.splitlines()[1:])
    fb = {l.split(" ", 2)[2]: l.split(" ", 2)[:2] for l in open(os.path.join(RUN, "files_before.txt")).read().splitlines() if l.count(" ") >= 2}
    fa = {l.split(" ", 2)[2]: l.split(" ", 2)[:2] for l in open(os.path.join(RUN, "files_after.txt")).read().splitlines() if l.count(" ") >= 2}
    changed = sorted(set(p for p in fa if fb.get(p) != fa[p]) | set(p for p in fb if p not in fa))
    allowed = (RUN + "/",)  # [port] the run dir is the only write scope
    outside = [p for p in changed if not p.startswith(allowed)]
    adapter_ns = [s for s in rep["checks_passed"] if s.startswith("4.7")]
    tele = all(x in np_ for x in ("CODEGRAPH_TELEMETRY=0", "DO_NOT_TRACK=1", "CODEGRAPH_NO_DOWNLOAD=1"))
    ok = kv and all(kv.get(k) == "pass" for k in "abcde") and cs and "e=pass" in cs.group(1) and len(isum) == 3 and all("d_indexer=pass" in s for s in isum) and iproc and all(n == kv_idx.get("wrapper_ns") for n in iproc) and kv_idx.get("wrapper_ns") != kv_idx.get("outer_ns") \
         and kv.get("wrapper_ns") != kv.get("outer_ns") and adapter_ns and tele and strip(s_b) == strip(s_a) and not outside
    ct(15, bool(ok), [rel(RUN) + f for f in ("/netprobe.log", "/snapshot_before.txt", "/snapshot_after.txt", "/files_before.txt", "/files_after.txt")],
       {"probe": kv, "control": cs.group(1) if cs else None, "indexer": isum, "indexer_log": rel(reused) if os.path.exists(reused) else rel(RUN) + "/netprobe.log", "indexer_run_wrapper_ns": kv_idx.get("wrapper_ns"), "indexer_processes_netns": dict(Counter(iproc)), "adapter_netns_check": adapter_ns, "telemetry_env_logged": tele,
        "snapshot_equal": strip(s_b) == strip(s_a), "changed_files_total": len(changed), "changed_outside_allowed_scope": outside[:50]})
    # CT16
    opened = set()
    for k, v in list(R["adapter"].items()):
        p = os.path.join(v["out"], "opened_files.json")
        if os.path.exists(p):
            opened |= set(json.load(open(p)))
    inj_path = os.path.join(RUN, "validator_inputs", "injected.jsonl")
    inj_read = [p for p in opened if "validator_inputs" in p or p == inj_path]
    inj_out = sum(1 for v in R["adapter"].values() for l in open(os.path.join(v["out"], "records.jsonl")) if json.loads(l)["injected"])
    tbl = [t[0] for t in db.execute("select name from sqlite_master where type='table'")]
    hits = []
    for t in tbl:
        for row in db.execute(f'select * from "{t}"'):
            s = json.dumps([str(x) for x in row])
            if "injected" in s or "gitdiagram" in s.lower() or "negative-control" in s or "traces-negative-control" in s:
                hits.append(t); break
    ev_inj = [r for r in ev if r["injected"]]
    src_same = re.search(r"## source\n(.*?)## lead", s_b, re.S).group(1) == re.search(r"## source\n(.*?)## lead", s_a, re.S).group(1)
    ok = not inj_read and inj_out == 0 and not hits and src_same and len(ev_inj) == 3 and all(r["visible_to_reviewer"] for r in ev_inj)
    ct(16, ok, [rel(inj_path), rel(EVP), rel(RUN) + "/snapshot_before.txt", rel(RUN) + "/snapshot_after.txt"] + [rel(v["out"]) + "/opened_files.json" for v in R["adapter"].values()],
       {"adapter_opened_injected_file": inj_read, "injected_records_in_adapter_outputs": inj_out, "index_tables_with_injected_markers": hits, "checkout_snapshot_unchanged": src_same,
        "injected_in_validation_output": [(r["origin"].get("fixture_id") or "N1", r["status"]) for r in ev_inj]})
    res = {"run_id": os.path.basename(RUN), "summary": {k: v["result"] for k, v in out.items()}, "pass": sum(1 for v in out.values() if v["result"] == "PASS"), "tests": out}
    json.dump(res, open(os.path.join(RUN, "ct_results.json"), "w"), indent=1, default=str)
    return out
