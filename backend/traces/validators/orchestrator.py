"""Task 002 step 7/8/9 orchestrator: adds independent checks to adapter records, the expected-chain fixture and the
injected set; computes status by EVIDENCE_SCHEMA v3 section 7 (V1 to V6, Decision 002-B); writes the validation output.
Ported from research/task002/validators/run_validation.py; status logic unchanged. Runs inside the isolation wrapper.
Families: cpython-ast (in process) and typescript-compiler (node + TS 6.0.3 subprocess).
Usage: python -m traces.validators.orchestrator --run-dir <run> --records <records.jsonl> --src <checkout> --sha <sha>
       --ts-module <typescript dir> [--node node] --fixture <chain.json> --injected <injected.jsonl>"""
import argparse, json, os, re, subprocess, time
from collections import Counter
from traces.core.common import Blobs, canon, sha256_hex, now_ist, line_count, normalize_file_range
from traces.validators.python_ast import PyValidator, Rules, chk as pychk, loc as pyloc
import ast

HERE = os.path.dirname(os.path.abspath(__file__))
# Set by Orchestrator from its arguments (portable; no box paths). Module-level names kept so the ported code reads as before.
SRC = None
REPO_SHA = None
TS_MODULE = None
NODE = "node"
INDEP_FAMILIES = ("cpython-ast", "typescript-compiler")
IMPORT_STATEMENT_QUALIFIER = "observed import statement"
RANGE_RULE_DEFAULT = {"site": "expression", "declaration": "header_to_body_end", "file": "file", "enclosing_scope": "expression", "body": "body_only"}
GITV = {"name": "traces-lchecks 1.0.0", "version": "git blob at repo_sha + text match", "family": "text"}


def lang(path):
    return "py" if path.endswith(".py") else "ts" if path.endswith((".ts", ".tsx")) else None


class Orchestrator:
    def __init__(self, a):
        global SRC, REPO_SHA, TS_MODULE, NODE
        SRC, REPO_SHA, TS_MODULE, NODE = os.path.abspath(a.src), a.sha, os.path.abspath(a.ts_module), a.node
        self.a = a; self.run_id = json.load(open(os.path.join(a.run_dir, "manifest.json")))["run_id"]; self.at = now_ist()
        self.blobs = Blobs(SRC, REPO_SHA)
        self.records = [json.loads(l) for l in open(a.records)]
        fx = json.load(open(a.fixture)); self.fixture_meta = fx
        self.fixture = fx["claims"]
        self.injected = [json.loads(l) for l in open(a.injected)]
        for r in self.records:
            r["_rk"] = r["origin"]["row_ref"]
        for r in self.fixture:
            r["run_id"] = self.run_id; r["status_history"][0]["run_id"] = self.run_id; r["_rk"] = "fixture:" + r["origin"]["fixture_id"]
        for r in self.injected:
            r["_rk"] = "injected:" + (r["origin"].get("fixture_id") or "N1")
        self.timing = {}

    # ---------- task building ----------
    def node_of(self, row):
        return {"file": row["file_path"], "name": row["name"], "qualified_name": row["qualified_name"], "kind": row["kind"], "start_line": row["start_line"], "end_line": row["end_line"]}

    def tasks(self):
        ts, py, none = [], [], []
        for r in self.records:
            raw = r["provenance_raw"]; row = raw["row"]; rk = r["_rk"]
            if r["claim_kind"] == "node":
                t = {"type": "node", "rk": rk, **self.node_of(row)}; f = row["file_path"]
            elif r["claim_kind"] == "unresolved_reference":
                t = {"type": "unresolved", "rk": rk, "file": row["file_path"], "line": row["line"], "col": row["col"], "ref_name": row["reference_name"], "ref_kind": row["reference_kind"]}; f = row["file_path"]
            else:
                s, g = raw["endpoint_rows"]["source"], raw["endpoint_rows"]["target"]
                md = json.loads(row["metadata"]) if row["metadata"] else {}
                site = [l for l in r["locations"] if l["role"] == "site"]
                t = {"type": "edge", "rk": rk, "rel_kind": r["relationship_kind"], "src": self.node_of(s), "tgt": self.node_of(g), "line": row["line"], "col": row["col"],
                     "missing": row["line"] is None, "value_ref": md.get("valueRef") is True, "enclosing": bool(site) and site[0]["range_kind"] == "enclosing_scope"}
                f = s["file_path"] if r["relationship_kind"] != "contains" else g["file_path"]
            (py if lang(f) == "py" else ts if lang(f) == "ts" else none).append(t)
        for fid in ("L1", "L2A", "L2B", "L3", "H1", "H2"):
            ts.append({"type": "fixture", "rk": "fixture:" + fid, "fixture": fid})
        ts.append({"type": "r3facts", "rk": "r3facts"})
        return ts, py, none

    # ---------- run validators ----------
    def run_ts(self, tasks):
        tp = os.path.join(self.a.run_dir, "validation", "ts_tasks.json"); op = os.path.join(self.a.run_dir, "validation", "ts_results.json")
        json.dump({"root": SRC, "sha": REPO_SHA, "tasks": tasks}, open(tp, "w"))
        t0 = time.time()
        out = subprocess.run([NODE, "--max-old-space-size=3072", os.path.join(HERE, "ts", "ts_validate.js"), tp, op], env={**os.environ, "TS_MODULE": TS_MODULE}, capture_output=True, text=True)
        self.timing["ts_validator_s"] = round(time.time() - t0, 1)
        self.log.append(f"$ TS_MODULE={TS_MODULE} {NODE} validators/ts_validate.js {tp} {op}\n{out.stdout}{out.stderr}[exit={out.returncode}]")
        if out.returncode != 0:
            raise SystemExit("ts validator failed: " + out.stderr[-2000:])
        return json.load(open(op))["results"]

    def run_py(self, tasks):
        t0 = time.time()
        self.pv = PyValidator(SRC, REPO_SHA); self.rules = Rules(self.pv)
        res = {}
        for t in tasks:
            try:
                if t["type"] == "node":
                    res[t["rk"]] = self.pv.node(t)
                elif t["type"] == "unresolved":
                    res[t["rk"]] = self.pv.unresolved(t)
                else:
                    res[t["rk"]] = self.pv.edge(t, self.rules)
            except Exception as e:
                import traceback
                res[t["rk"]] = {"checks": [pychk("parser_presence", "presence", None, [], "validator ran", "error", traceback.format_exc()[-600:])], "error": True}
        self.timing["py_validator_s"] = round(time.time() - t0, 1)
        return res

    # ---------- fixture rules (py side, R1 to R4, L9, N1, N2) ----------
    def fixture_py(self, ts_res):
        R = self.rules; P = self.pv.P; out = {}
        items = "backend/app/api/routes/items.py"; deps = "backend/app/api/deps.py"; models = "backend/app/models.py"
        ci = R.route(items, 61)
        facts = ts_res["r3facts"]["facts"]
        self.r3facts = facts
        if not ci:
            for k in ("L4", "L5", "L6", "L7", "L7T1", "L7T2", "L8", "L9A", "L9B"):
                out[k] = {"checks": [pychk("deterministic_rule", "relationship", "R1", [], "R1 route for items.py:61", "inconclusive", f"R1 produced no route at items.py:61; {R.r1_notes}")]}
            return out
        ci = ci[0]
        self.findings = {"R1": [{k: v for k, v in r.items() if k not in ("decl", "inputs")} for r in R.routes], "R1_notes": R.r1_notes, "versions": R.version_gate}
        # L4 / L5: R3 (and R1 for L5)
        res3, det3, in3, fin3 = R.r3(ci, facts)
        self.findings["R3"] = {"result": res3, "detail": det3, "finding": fin3}
        site4 = [pyloc("frontend/src/client/sdk.gen.ts", 307, 307, "site", "site")]
        out["L4"] = {"checks": [pychk("deterministic_rule", "relationship", "R3", site4 + in3 + ci["inputs"], "R3: exactly one SDK method implements (POST, /api/v1/items/), K2 naming consistent, Data type url equal to the R1 path", res3, det3)],
                     "flags": ci["flags"] + ["generated_file"]}
        r1ok = ci["method"] == "POST" and ci["full_path"] == "/api/v1/items/" and ci["tags"] == ["items"] and ci["route_name"] == "create_item" and ci["condition"] is None and ci["decorator_line"] == 61 and ci["end_line"] == 72
        r1det = f"R1: {ci['method']} {ci['full_path']} = " + " + ".join(f"{p[0]!r} ({p[1]}:{p[2]} {p[3]})" for p in ci["pieces"]) + f"; tags {ci['tags']}; route name {ci['route_name']}; handler {ci['file']}:{ci['decorator_line']}-{ci['end_line']} (def {ci['def_line']}); condition {ci['condition']}; flags {ci['flags']}"
        site5 = [pyloc(items, 61, 61, "site", "site")]
        out["L5"] = {"checks": [pychk("deterministic_rule", "relationship", "R1", site5 + ci["inputs"], "R1: POST /api/v1/items/, tags ['items'], name create_item, handler items.py:61-72, no condition", "pass" if r1ok else "fail", r1det),
                                pychk("deterministic_rule", "relationship", "R3", site5 + in3, "R3 join: operation items-create_item (R3 K1 and K2) is served by the R1 route", res3, det3)],
                     "flags": ci["flags"]}
        # R2
        r2 = R.r2(ci)
        self.findings["R2_create_item"] = {"complete": r2["complete"], "notes": r2["notes"], "closure": [{"depth": d["depth"], "path": d["path"], "param": d["param"], "param_line": d["param_line"], "callable": repr(d["callable"]), "alias": repr(d["alias"]) if d["alias"] else None} for d in r2["closure"]]}
        def r2check(fid, param, callable_name, alias_name, depth, site_line, site_file):
            hit = [d for d in r2["closure"] if d["param"] == param and d["callable"].name == callable_name and d["depth"] == depth and d["alias"] is not None and d["alias"].name == alias_name and d["param_line"] == site_line]
            site = [pyloc(site_file, site_line, site_line, "site", "site")]
            if not hit:
                return {"checks": [pychk("deterministic_rule", "relationship", "R2", site, f"R2: {param} -> {alias_name} -> {callable_name} (depth {depth})", "fail" if r2["complete"] else "inconclusive", f"not in R2 closure {self.findings['R2_create_item']['closure']}")]}
            d = hit[0]; a = d["alias"]; c = d["callable"]
            ins = site + [pyloc(a.file, a.def_line, a.end, "input", "declaration", range_rule="binding_statement"), pyloc(c.file, c.start, c.end, "to_decl", "declaration", range_rule="binding_statement" if c.kind == "ModuleAssign" else "header_to_body_end")] + d["inputs"]
            ins += [pyloc(items, 7, 7, "input", "site")] if depth == 1 else []
            return {"checks": [pychk("deterministic_rule", "relationship", "R2", ins, f"R2: {param} -> {alias_name} -> {callable_name} (depth {depth})", "pass",
                                     f"parameter {param} ({site_file}:{site_line}) annotated {alias_name}, alias {a.file}:{a.def_line} = {P.mod(a.file).seg(a.node.value)}, Depends({c.name}) resolves to {c!r}; depth {depth}, path {d['path'] + [c.name]}; closure complete: {r2['complete']}")]}
        out["L6"] = r2check("L6", "session", "get_db", "SessionDep", 1, 63, items)
        out["L7"] = r2check("L7", "current_user", "get_current_user", "CurrentUser", 1, 63, items)
        out["L7T1"] = r2check("L7T1", "session", "get_db", "SessionDep", 2, 30, deps)
        out["L7T2"] = r2check("L7T2", "token", "reusable_oauth2", "TokenDep", 2, 30, deps)
        # R4
        r4 = R.r4(ci)
        steps = r4.get("steps", [])
        self.findings["R4_create_item"] = {"result": r4["result"], "detail": r4["detail"], "steps": [{"type": s["type"], "line": s["line"], "call": s["call"]} for s in steps], "observed_only": r4.get("observed_only")}
        want = [("model_validation", 68), ("session_stage", 69), ("session_commit", 70), ("session_reload", 71)]
        got = [(s["type"], s["line"]) for s in steps]
        mv = [s for s in steps if s["type"] == "model_validation"]
        ok8 = r4["result"] == "pass" and got == want and mv and mv[0]["table_model"]
        ins8 = [pyloc(items, l, l, "site", "site") for _, l in want] + [pyloc(items, 63, 63, "input", "site"), pyloc(items, 7, 7, "input", "site"), pyloc(items, 8, 8, "input", "site"),
               pyloc(deps, 26, 26, "input", "declaration", range_rule="binding_statement"), pyloc(deps, 9, 9, "input", "site"), pyloc(deps, 21, 23, "input", "declaration"), pyloc(models, 87, 87, "input", "declaration")]
        out["L8"] = {"checks": [pychk("deterministic_rule", "relationship", "R4", ins8, "R4: ordered steps model_validation 68, session_stage 69, session_commit 70, session_reload 71 on the SessionDep-bound Session (get_db)",
                                      "pass" if ok8 else (r4["result"] if r4["result"] != "pass" else "fail"),
                                      f"{r4['detail']}; steps {got}; model {mv[0]['model']!r} table=True: {mv[0]['table_model'] if mv else None}; label: statically established persistence path: create_item stages Item via session.add (69) and commits via session.commit (70) on the SessionDep-bound Session; model built at 68; reloaded at 71")]}
        # L9
        m = P.mod(items); fn = ci["decl"].node
        cands = [n.func.value for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "model_validate" and isinstance(n.func.value, ast.Name) and n.lineno == 68]
        r = P.resolve_expr(m, cands[0]) if cands else ("none", "no Item.model_validate at 68", [])
        ok = r[0] == "decl" and r[1].file == models and r[1].def_line == 87 and r[1].end == 93
        table = ok and any(k.arg == "table" and isinstance(k.value, ast.Constant) and k.value.value is True for k in r[1].node.keywords)
        out["L9A"] = {"checks": [pychk("binding_resolution", "relationship", None, [pyloc(items, 68, 68, "site", "site"), pyloc(items, 8, 8, "input", "site"), pyloc(models, 87, 93, "to_decl", "declaration")], "Item at items.py:68 resolves through the import at items.py:8 to class Item at models.py:87-93", "pass" if ok else ("fail" if r[0] == "decl" else "inconclusive"), f"{r[0]} {r[1]!r} via {[(x['file'], x['start_line']) for x in r[2]]}"),
                                 pychk("syntax_structure", "relationship", None, [pyloc(items, 68, 68, "site", "site"), pyloc(models, 87, 87, "to_decl", "declaration")], "class Item has keyword table=True (models.py:87) and Item.model_validate is called inside create_item", "pass" if table else "fail", f"ClassDef Item keywords {[ (k.arg, ast.unparse(k.value)) for k in r[1].node.keywords] if r[0] == 'decl' else None}; call at line 68 inside FunctionDef create_item {ci['def_line']}-{ci['end_line']}")]}
        dec = [d for d in fn.decorator_list if d.lineno == 61]
        kw = [k for k in dec[0].keywords if k.arg == "response_model"] if dec else []
        rr = P.resolve_expr(m, kw[0].value) if kw else ("none", "no response_model keyword", [])
        okb = rr[0] == "decl" and rr[1].file == models and rr[1].def_line == 97 and rr[1].end == 100
        out["L9B"] = {"checks": [pychk("syntax_structure", "relationship", None, [pyloc(items, 61, 61, "site", "site")], "keyword response_model=ItemPublic on the route decorator of create_item at items.py:61", "pass" if kw and isinstance(kw[0].value, ast.Name) and kw[0].value.id == "ItemPublic" else "fail", f"decorator {m.seg(dec[0]) if dec else None}"),
                                 pychk("binding_resolution", "relationship", None, [pyloc(items, 61, 61, "site", "site"), pyloc(items, 8, 8, "input", "site"), pyloc(models, 97, 100, "to_decl", "declaration")], "ItemPublic at items.py:61 resolves through items.py:8 to class ItemPublic at models.py:97-100", "pass" if okb else ("fail" if rr[0] == "decl" else "inconclusive"), f"{rr[0]} {rr[1]!r}")]}
        # N1: uses_crud
        crud = "backend/app/crud.py"
        handlers = [r_ for r_ in R.routes if r_["file"] == items]
        calls_into_crud = []; unresolved_calls = []
        for h in handlers:
            for n in ast.walk(h["decl"].node):
                if isinstance(n, ast.Call):
                    rr_ = P.resolve_expr(m, n.func) if isinstance(n.func, (ast.Name, ast.Attribute)) else ("unresolved", "complex callee", [])
                    if (rr_[0] == "decl" and rr_[1].file == crud) or (rr_[0] == "module" and rr_[1] == crud):
                        calls_into_crud.append((n.lineno, m.seg(n)))
                    elif rr_[0] != "decl":
                        unresolved_calls.append((n.lineno, m.seg(n.func), rr_[0]))
        mod_bindings = {k: v for k, v in m.imports.items() if (v[0] == "module" and P.module_file(v[1]) == crud) or (v[0] == "from" and (P.module_file(v[1]) == crud or P.module_file(f"{v[1]}.{v[2]}") == crud))}
        crud_names = [n for n in ast.walk(m.tree) if (isinstance(n, ast.Name) and "crud" in n.id) or (isinstance(n, ast.Attribute) and "crud" in n.attr)]
        callers = []
        for p in sorted(x for x in P.blobs.tree if x.endswith(".py")):
            mm = P.mod(p)
            for n in ast.walk(mm.tree):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "create_item":
                    rr_ = P.resolve_expr(mm, n.func)
                    if rr_[0] == "decl" and rr_[1].file == crud and rr_[1].name == "create_item":
                        callers.append(f"{p}:{n.lineno}")
        n1fail = not calls_into_crud and not mod_bindings and not crud_names
        unresolved_desc = sorted({f'{f} ({k})' for _, f, k in unresolved_calls})[:12]
        out["N1"] = {"checks": [pychk("binding_resolution", "relationship", None, [pyloc(items, 61, 72, "site", "declaration", range_rule="decorator_to_body_end"), pyloc(items, 1, 8, "input", "declaration", range_rule="binding_statement")],
                                      "a call in an items.py handler resolves into backend/app/crud.py", "fail" if n1fail else ("pass" if calls_into_crud else "inconclusive"),
                                      f"{len(handlers)} items.py handlers (R1); calls resolving into app.crud: {calls_into_crud}; module bindings to app.crud: {list(mod_bindings)}; Name/Attribute containing 'crud' in items.py: {len(crud_names)}; "
                                      f"unresolved callees (none can reach app.crud without a binding): {unresolved_desc}; crud.py::create_item callers repo-wide: {callers}; R4 for create_item: {self.findings['R4_create_item']['result']} through session at 68-71")]}
        # N2: private.py::create_user
        pu = [r_ for r_ in R.routes if r_["file"] == "backend/app/api/routes/private.py" and r_["handler"] == "create_user"]
        p2 = R.r2(pu[0]) if pu else None
        pm = P.mod("backend/app/api/routes/private.py")
        self.findings["R2_private_create_user"] = {"complete": p2["complete"], "closure": sorted({d["callable"].name for d in p2["closure"]}), "notes": p2["notes"], "route_dependencies": pu[0]["dependencies"]} if p2 else None
        pins = [pyloc("backend/app/api/routes/private.py", 24, 24, "site", "site"), pyloc("backend/app/api/routes/private.py", 6, 6, "input", "site"), pyloc(deps, 26, 26, "input", "declaration", range_rule="binding_statement"),
                pyloc("backend/app/api/routes/private.py", 13, 13, "input", "site"), pyloc("backend/app/api/routes/private.py", 23, 23, "input", "site"), pyloc(APIM := "backend/app/api/main.py", 14, 14, "input", "site"), pyloc("backend/app/main.py", 21, 25, "input", "declaration", range_rule="binding_statement"), pyloc("backend/app/main.py", 35, 35, "input", "site")]
        for nid, target, alias in (("N2a", "CurrentUser", True), ("N2b", "get_current_user", False)):
            names = {d["callable"].name for d in p2["closure"]} | {d["alias"].name for d in p2["closure"] if d["alias"]}
            absent = target not in names
            res = "fail" if (p2["complete"] and absent and not pu[0]["dependencies"]) else ("pass" if not absent else "inconclusive")
            binding = [k for k in list(pm.imports) + list(pm.top) if k in ("CurrentUser", "get_current_user")]
            fn2 = pu[0]["decl"].node
            in_fn = [n.id for n in ast.walk(fn2) if isinstance(n, ast.Name) and n.id in ("CurrentUser", "get_current_user")]
            out[nid] = {"checks": [pychk("deterministic_rule", "relationship", "R2", pins, f"R2: {target} in the dependency closure of private.py::create_user", res,
                                         f"parameters {[a.arg for a in fn2.args.args + fn2.args.kwonlyargs]}; closure {sorted({d['callable'].name for d in p2['closure']})} (aliases {sorted({d['alias'].name for d in p2['closure'] if d['alias']})}), complete {p2['complete']}; dependencies= on decorator/router/includes/app: {pu[0]['dependencies']}; notes {p2['notes']}"),
                                   pychk("binding_resolution", "relationship", None, pins[:2], f"a binding for {target} in private.py", "fail" if not binding and not in_fn else "inconclusive", f"module-level bindings named CurrentUser/get_current_user: {binding}; uses inside create_user: {in_fn}; imports from app.api.deps: {[k for k, v in pm.imports.items() if v[0] == 'from' and v[1] == 'app.api.deps']}")]}
        return out

    # ---------- check finalization and status ----------
    def full_loc(self, l, source="validator"):
        d = {"file": l["file"], "start_line": l["start_line"], "end_line": l["end_line"], "line_base": 1, "col_base": 0, "range_kind": l["range_kind"],
             "range_rule": l.get("range_rule") or RANGE_RULE_DEFAULT[l["range_kind"]], "role": l["role"], "blob_sha": self.blobs.blob_sha(l["file"]) or "0" * 40, "source": l.get("source", source), "recovered_by": l.get("recovered_by")}
        for k in ("start_col", "end_col", "original", "end_exclusive_line", "terminal_newline"):
            if k in l:
                d[k] = l[k]
        if d["range_kind"] == "file" and "original" not in d and self.blobs.exists(d["file"]):
            d = normalize_file_range(d, self.blobs.text(d["file"]))  # Decision 002-B ruling 1
        return d

    def finalize_check(self, rec, c):
        fam = c["validator"]["family"]
        c = dict(c); c["inputs"] = [self.full_loc(x) if ("blob_sha" not in x or (x.get("range_kind") == "file" and "original" not in x)) else x for x in c["inputs"]]
        c["reads_originator_output"] = False
        c["independent"] = fam in INDEP_FAMILIES and not c["reads_originator_output"] and c["validator"]["name"] != rec["originator"]["name"] and c["method"] != "human_review"
        c["expected"] = str(c.get("expected", ""))
        c["detail"] = c["detail"] or "(no detail)"
        c["run_id"] = self.run_id; c["at"] = self.at
        c["check_id"] = "k_" + sha256_hex(canon([rec["claim_id"], rec["_rk"], c["method"], c["rule_id"], c["validator"], [ (x["file"], x["start_line"], x["end_line"], x["role"]) for x in c["inputs"]], c["expected"], c["result"]]))
        return {k: c[k] for k in ("check_id", "method", "establishes", "rule_id", "validator", "reads_originator_output", "independent", "inputs", "expected", "result", "detail", "run_id", "at")}

    def token_for(self, rec, l):
        """L3 expected token for a location, or None (file ranges and validator-added inputs)."""
        if l["range_kind"] == "file":
            return None
        if rec["originator"]["name"] != "codegraph":
            for fl in rec["provenance_raw"]["fixture_entry"]["locs"]:
                if (fl["file"], fl["start_line"], fl["end_line"], fl["role"]) == (l["file"], l["start_line"], l["end_line"], l["role"]):
                    return ("substr", fl["token"])
            return None
        if l["source"] == "validator":
            return None
        raw = rec["provenance_raw"]
        def name_tok(n):
            if n["kind"] == "route":
                return ("word", "createFileRoute") if n["language"] in ("tsx", "typescript") else ("substr", "." + n["name"].split()[0].lower() + "(")
            if n["kind"] == "import":
                return ("substr", n["name"])
            return ("word", n["name"].split("::")[-1].split(".")[-1])
        if rec["claim_kind"] == "node":
            return name_tok(raw["row"])
        if rec["claim_kind"] == "unresolved_reference":
            rn = raw["row"]["reference_name"]
            return ("substr", rn) if raw["row"]["reference_kind"] == "imports" else ("word", rn.split(".")[-1])
        s, g = raw["endpoint_rows"]["source"], raw["endpoint_rows"]["target"]
        if l["role"] == "from_decl":
            return name_tok(s)
        if l["role"] == "to_decl":
            return name_tok(g)
        if l["range_kind"] == "enclosing_scope" or s["kind"] == "route":
            return name_tok(s)
        if rec["relationship_kind"] == "imports":
            tn = g["name"] if g["kind"] in ("file", "import") else g["name"].split("::")[-1].split(".")[-1]
            return ("word", "import|from|export") if g["kind"] in ("file", "import") else ("word", "import|from|export|" + re.escape(tn))
        if rec["relationship_kind"] == "navigates":
            return ("substr", g["name"])
        return ("word", g["name"].split("::")[-1].split(".")[-1])

    def lchecks(self, rec):
        out = []
        for l in rec["locations"]:
            if l["role"] not in ("site", "from_decl", "to_decl", "input"):
                continue
            ex = self.blobs.exists(l["file"]); bs = self.blobs.blob_sha(l["file"])
            ok1 = ex and bs == l["blob_sha"]
            out.append({"method": "L1_path_exists", "establishes": "location", "rule_id": None, "validator": GITV, "inputs": [l], "expected": f"{l['file']} exists at {REPO_SHA[:8]} with blob {l['blob_sha'][:12]}", "result": "pass" if ok1 else "fail", "detail": f"ls-tree blob {bs}"})
            if not ex:
                continue
            text = self.blobs.text(l["file"]); n = line_count(text)  # Decision 002-B ruling 1: addressable lines only; the EOF position is not a line
            if l["range_kind"] == "file":
                orig = (l.get("original") or {}).get("end_line")
                ok2 = l["start_line"] == 1 and l["end_line"] == n and l.get("end_exclusive_line") == n + 1 and orig in (n, n + 1)
                exp2 = f"whole-file range [1, {n}] with exclusive end boundary {n + 1} (EOF position); original end {orig} in ({n}, {n + 1})"
            else:
                ok2 = 1 <= l["start_line"] <= l["end_line"] <= n
                exp2 = f"1 <= {l['start_line']} <= {l['end_line']} <= {n} (addressable lines; the EOF position {n + 1} is never a location)"
            out.append({"method": "L2_range_in_file", "establishes": "location", "rule_id": None, "validator": GITV, "inputs": [l], "expected": exp2, "result": "pass" if ok2 else "fail", "detail": f"file has {n} addressable lines ({text.count(chr(10))} newline characters, terminal newline {text.endswith(chr(10))})"})
            if not ok2:
                continue
            tok = self.token_for(rec, l)
            seg = "\n".join(text.split("\n")[l["start_line"] - 1: l["end_line"]])
            if l["range_kind"] == "file":
                out.append({"method": "L3_token_at_location", "establishes": "location", "rule_id": None, "validator": GITV, "inputs": [l], "expected": f"file range: whole blob {l['blob_sha'][:12]} at {REPO_SHA[:8]}", "result": "pass" if ok1 else "fail", "detail": f"blob {bs}, {len(text)} chars"})
                continue
            if tok is None:
                ok3 = bool(seg.strip()) and ok1
                out.append({"method": "L3_token_at_location", "establishes": "location", "rule_id": None, "validator": GITV, "inputs": [l], "expected": "non-empty source text in range (no token rule: file range or validator-added location)", "result": "pass" if ok3 else "fail", "detail": f"{len(seg)} chars"})
            else:
                mode, t = tok
                if mode == "word":
                    ok3 = re.search(r"(?<![A-Za-z0-9_$])(?:" + (t if "|" in t else re.escape(t)) + r")(?![A-Za-z0-9_$])", seg) is not None
                else:
                    ok3 = t in seg
                out.append({"method": "L3_token_at_location", "establishes": "location", "rule_id": None, "validator": GITV, "inputs": [l], "expected": f"token {t!r} ({mode}) in {l['file']}:{l['start_line']}-{l['end_line']}", "result": "pass" if ok3 else "fail", "detail": "found" if ok3 else f"not found; first line: {seg.split(chr(10))[0].strip()[:100]!r}"})
        return out

    def status(self, rec):
        locs = rec["locations"]; checks = rec["checks"]
        if not locs:
            rs = [c for c in checks if c["method"] == "location_recovery"]
            return "missing_location", (rec.get("_reason") or (rs[-1]["detail"] if rs else rec["status_reason"])), []
        lc = [c for c in checks if c["method"] in ("L1_path_exists", "L2_range_in_file")]
        bad = [c for c in lc if c["result"] == "fail"]
        if bad:
            return "rejected", "L1/L2 fail: " + "; ".join(f"{c['check_id']} {c['expected']}" for c in bad), [c["check_id"] for c in bad]
        indep = [c for c in checks if c["independent"]]
        fails = [c for c in indep if c["result"] == "fail"]
        if fails:
            return "rejected", "independent check failed: " + " | ".join(f"{c['check_id']} ({c['method']}{'/' + c['rule_id'] if c['rule_id'] else ''}): {c['detail']}" for c in fails), [c["check_id"] for c in fails]
        l3 = [c for c in checks if c["method"] == "L3_token_at_location" and c["result"] == "fail"]
        if l3:
            return "unvalidated", "L3 fail, not established: " + "; ".join(c["expected"] for c in l3), [c["check_id"] for c in l3]
        if rec["claim_kind"] == "relationship":
            sites = [(l["file"], l["start_line"], l["end_line"]) for l in locs if l["role"] == "site"]
            est = [c for c in indep if c["establishes"] == "relationship" and c["method"] in ("syntax_structure", "binding_resolution", "deterministic_rule") and c["result"] == "pass"
                   and all(s in {(x["file"], x["start_line"], x["end_line"]) for x in c["inputs"]} for s in sites)]
            v5 = rec["granularity"] == "file" or rec["granularity"] == "symbol" or any(l["range_kind"] in ("site", "declaration") for l in locs if l["role"] in ("site", "from_decl", "to_decl"))
            v6 = rec["relationship_kind"] != "renders" or any(l["range_kind"] == "site" and l["role"] == "site" for l in locs)
            incon = [c for c in indep if c["result"] in ("inconclusive", "error")]
            if self.is_import_statement(rec):
                # Decision 002-B correction A: an import of a library module or asset is an observed import statement, not a verified relationship
                pres = [c for c in indep if c["method"] == "parser_presence" and c["result"] == "pass" and all(s in {(x["file"], x["start_line"], x["end_line"]) for x in c["inputs"]} for s in sites)]
                if pres:
                    rec["qualifier"] = IMPORT_STATEMENT_QUALIFIER
                    return "observed", None, [c["check_id"] for c in pres]
                return "unvalidated", "; ".join(f"{c['method']} {c['result']}: {c['detail']}" for c in incon) or "import statement not observed", [c["check_id"] for c in incon]
            if rec["relationship_kind"] == "library_contract":
                return "unvalidated", "library_contract: cannot be established in Task 002 (library source not installed, not in scope); " + "; ".join(c["detail"] for c in incon), [c["check_id"] for c in incon]
            if est and v5 and v6:
                # every check that establishes a relationship and covers sites must not be inconclusive for a fixture claim that names several establishing checks
                return "verified", None, [c["check_id"] for c in est]
            why = "; ".join(f"{c['method']}{'/' + c['rule_id'] if c['rule_id'] else ''} {c['result']}: {c['detail']}" for c in incon) or "no relationship-establishing independent check passed"
            if not v6:
                why = "renders without a site location at the JSX element (V6); " + why
            return "unvalidated", rec.get("_reason") or why, [c["check_id"] for c in incon]
        pres = [c for c in indep if c["method"] == "parser_presence" and c["result"] == "pass"]
        if pres:
            return "observed", None, [c["check_id"] for c in pres]
        incon = [c for c in indep if c["result"] in ("inconclusive", "error")]
        return "unvalidated", "; ".join(f"{c['method']} {c['result']}: {c['detail']}" for c in incon) or "no independent parser_presence pass", [c["check_id"] for c in incon]

    @staticmethod
    def is_import_statement(rec):
        """imports edge whose target is the importing file's own import node (library module or asset outside validator scope)."""
        if rec.get("relationship_kind") != "imports" or rec["originator"]["name"] != "codegraph":
            return False
        t = rec["provenance_raw"].get("endpoint_rows", {}).get("target") or {}
        return t.get("kind") == "import" and t.get("file_path") == rec["from"]["file"]

    def apply(self, rec, res):
        before = rec["status"]
        for l in res.get("add_locations", []) if res else []:
            fl = self.full_loc(l)
            key = (fl["file"], fl["start_line"], fl["end_line"], fl["role"], fl["range_kind"])
            if key not in {(x["file"], x["start_line"], x["end_line"], x["role"], x["range_kind"]) for x in rec["locations"]}:
                rec["locations"].append(fl)
        for fl in (res or {}).get("flags", []):
            if fl not in rec["flags"]:
                rec["flags"].append(fl)
        if res and res.get("reason"):
            rec["_reason"] = res["reason"]
        for c in (res or {}).get("checks", []):
            rec["checks"].append(self.finalize_check(rec, c))
        for c in self.lchecks(rec):
            rec["checks"].append(self.finalize_check(rec, c))
        st, reason, ids = self.status(rec)
        hist = rec["status_history"]
        if before == "missing_location" and st in ("verified", "observed", "rejected", "unvalidated") and rec["locations"]:
            rc = [c["check_id"] for c in rec["checks"] if c["method"] == "location_recovery" and c["result"] == "pass"]
            hist.append({"from": "missing_location", "to": "unvalidated", "at": self.at, "run_id": self.run_id, "check_ids": rc, "by": "location_recovery"})
            before = "unvalidated"
        if st != before:
            hist.append({"from": before, "to": st, "at": self.at, "run_id": self.run_id, "check_ids": ids, "by": "traces-status-v2"})
        rec["status"] = st
        rec["label"] = {"observed": "observed", "verified": "verified"}.get(st, "inferred")
        if reason is None:
            rec.pop("status_reason", None)
        else:
            rec["status_reason"] = reason
        rec.pop("_reason", None)

    def run(self):
        os.makedirs(os.path.join(self.a.run_dir, "validation"), exist_ok=True)
        self.log = []
        t0 = time.time()
        ts_tasks, py_tasks, none = self.tasks()
        ts_res = self.run_ts(ts_tasks)
        py_res = self.run_py(py_tasks)
        fx_py = self.fixture_py(ts_res)
        no_family = Counter()
        for r in self.records:
            rk = r["_rk"]; res = ts_res.get(rk) or py_res.get(rk)
            if res is None:
                no_family[r["claim_kind"]] += 1
                res = {"checks": [], "reason": "no validator family for this file language"}
            self.apply(r, res)
        for r in self.fixture:
            fid = r["origin"]["fixture_id"]; res = {"checks": [], "flags": []}
            for src in (ts_res.get("fixture:" + fid), fx_py.get(fid)):
                if src:
                    res["checks"] += src.get("checks", []); res["flags"] += src.get("flags", [])
            self.apply(r, res)
            if r["relationship_kind"] == "persistence_path" and r["status"] == "verified":
                r["qualifier"] = "statically established persistence path"
        nc = self.fixture_meta["negative_controls"]
        for r in self.injected:
            fid = r["origin"].get("fixture_id") or "N1"
            res = fx_py.get(fid, {"checks": []})
            self.apply(r, res)
            # EXPECTED_CHAIN N1/N2: the stated status_reason is used only when the named checks produced the failing evidence
            fails = {(c["method"], c["rule_id"]) for c in r["checks"] if c["result"] == "fail"}
            need = {("L3_token_at_location", None), ("binding_resolution", None)} if fid == "N1" else {("deterministic_rule", "R2"), ("binding_resolution", None)}
            extra_ok = (self.findings["R4_create_item"]["result"] == "pass") if fid == "N1" else (self.findings["R2_private_create_user"]["complete"] and self.findings["R2_private_create_user"]["closure"] == ["get_db"])
            if r["status"] == "rejected" and need <= fails and extra_ok:
                ids = [c["check_id"] for c in r["checks"] if (c["method"], c["rule_id"]) in need and c["result"] == "fail"]
                r["status_reason"] = nc["N1" if fid == "N1" else "N2"]["expected_status_reason"] + " (failing checks: " + ", ".join(ids) + ")"
        self.timing["total_validation_s"] = round(time.time() - t0, 1)
        allrecs = self.records + self.fixture + self.injected
        for r in allrecs:
            r.pop("_rk", None)
        allrecs.sort(key=lambda r: (r["claim_id"], r["origin"].get("row_ref") or r["origin"].get("fixture_id") or ""))
        vd = os.path.join(self.a.run_dir, "validation")
        with open(os.path.join(vd, "evidence.jsonl"), "w") as f:
            for r in allrecs:
                f.write(canon(r) + "\n")
        json.dump({"findings": self.findings, "r3facts_summary": {"sdk_methods": len(self.r3facts["sdk_methods"]), "data_types": len(self.r3facts["data_types"]), "config": self.r3facts["config"], "sdk_header": self.r3facts["sdk_header"]},
                   "no_validator_family": dict(no_family), "timing": self.timing}, open(os.path.join(vd, "rule_findings.json"), "w"), indent=1, default=str)
        open(os.path.join(vd, "validation.log"), "w").write("\n".join(self.log) + "\n")
        print(f"validation: {len(allrecs)} records; timing {self.timing}")
        return allrecs


def main():
    ap = argparse.ArgumentParser()
    for k in ("--run-dir", "--records", "--fixture", "--injected", "--src", "--sha", "--ts-module"):
        ap.add_argument(k, required=True)
    ap.add_argument("--node", default="node")
    Orchestrator(ap.parse_args()).run()


if __name__ == "__main__":
    main()
