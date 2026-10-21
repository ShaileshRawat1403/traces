"""Step 1 line-accuracy and containment checks for CodeGraph 1.6.2 on fsft @ b1125d88.
Reads the CodeGraph SQLite index read-only, reads source with `git show <SHA>:<path>`,
and compares against (a) Lab's check_lines.py rule (defline, copied verbatim below) and
(b) independent parsers: CPython 3.14 ast (py_decls.py) and TypeScript 5.9.3 (ts_decls.js).
Writes step1/logs/analysis.json and prints a summary."""
import json, os, re, sqlite3, subprocess, sys
from collections import Counter, defaultdict
SHA = "b1125d8839482cb7bbae603ddc6d0081bf87532e"
T = "/workspace/traces-research/task002"
REPO = f"{T}/src/fsft"
assert subprocess.check_output(["git", "-C", REPO, "rev-parse", "HEAD"], text=True).strip() == SHA
assert subprocess.check_output(["git", "-C", REPO, "status", "--porcelain", "--untracked-files=no"], text=True) == ""
db = sqlite3.connect(f"file:{REPO}/.codegraph/codegraph.db?mode=ro", uri=True); db.row_factory = sqlite3.Row
nodes = {r["id"]: dict(r) for r in db.execute("select * from nodes")}
edges = [dict(r) for r in db.execute("select * from edges")]
_src = {}
def lines(path):
    if path not in _src:
        try: _src[path] = subprocess.check_output(["git", "-C", REPO, "show", f"{SHA}:{path}"], text=True).splitlines()
        except subprocess.CalledProcessError: _src[path] = None
    return _src[path]

# ---- verbatim from lab/B/scripts/check_lines.py lines 7-15, with file read switched to git show at SHA
def defline(path, name, line):
    ls = lines(path)
    if ls is None: return "missing_file"
    pat = re.compile(r"(def|function|class|const|let)\s+%s\b|\b%s\s*[:=(]" % (re.escape(name.split(".")[-1]), re.escape(name.split(".")[-1])))
    def hit(n): return 1 <= n <= len(ls) and pat.search(ls[n-1])
    if hit(line): return "exact_1based"
    if hit(line+1): return "off_by_minus1"
    if 1 <= line <= len(ls) and ls[line-1].lstrip().startswith("@"): return "decorator_line"
    return "other"
# ----

def in_scope(p): return p.startswith("backend/app/") or p.startswith("frontend/src/")
scope = [n for n in nodes.values() if n["kind"] in ("function", "method", "route") and in_scope(n["file_path"])]
res = {"scope_counts": Counter(n["kind"] for n in scope)}

# A1: Lab rule
a1 = Counter(); a1_bad = []
for n in scope:
    if n["kind"] == "route":
        m = re.match(r"route:(.+):(\d+):([A-Z]+):(.*)$", n["id"])
        if m:  # backend route: decorator line must contain .<method>("<path>"
            meth, rpath = m.group(3).lower(), m.group(4)
            ls = lines(n["file_path"]) or []; i = n["start_line"]-1
            # decorator call may span lines: join from the reported line through the closing paren (max 6 lines)
            span = ""; 
            for j in range(i, min(i+6, len(ls))):
                span += ls[j].strip() + " "
                if ")" in ls[j]: break
            ok = ls[i].lstrip().startswith("@") and re.search(r"\.%s\(\s*[\"']%s[\"']" % (meth, re.escape(rpath)), span) is not None
        else:  # frontend file route: line must contain createFileRoute("<path>")
            rpath = n["name"]; ls = lines(n["file_path"]); l = ls[n["start_line"]-1] if ls else ""
            ok = "createFileRoute" in l and (rpath.rstrip("/") in l)
        c = "exact_1based" if ok else "other"
    else:
        c = defline(n["file_path"], n["name"], n["start_line"])
    a1[(n["kind"], c)] += 1
    if c != "exact_1based": a1_bad.append((n["kind"], n["file_path"], n["name"], n["start_line"], c, (lines(n["file_path"]) or [""])[n["start_line"]-1].strip()[:90]))
res["A1_lab_rule"] = {f"{k}|{c}": v for (k, c), v in sorted(a1.items())}
res["A1_not_exact"] = a1_bad

# Independent parser declarations
pyfiles = sorted({n["file_path"] for n in nodes.values() if n["language"] == "python"})
tsfiles = sorted({n["file_path"] for n in nodes.values() if n["language"] in ("typescript", "tsx")})
pyd = [json.loads(l) for l in subprocess.check_output([f"{T}/tools/py314/bin/python", f"{T}/step1/py_decls.py", REPO] + pyfiles, text=True).splitlines()]
tsd = [json.loads(l) for l in subprocess.check_output(["node", f"{T}/step1/ts_decls.js", REPO] + tsfiles, text=True).splitlines()]
res["parser_versions"] = {"python": subprocess.check_output([f"{T}/tools/py314/bin/python", "-c", "import sys;print(sys.version.split()[0])"], text=True).strip(),
                          "typescript": json.load(open(os.environ.get("TS_MODULE", f"{T}/tools/node_modules/typescript") + "/package.json"))["version"]}
py_by = defaultdict(list); ts_by = defaultdict(list)
for d in pyd: py_by[(d["file"], d["name"])].append(d)
for d in tsd: ts_by[(d["file"], d["name"])].append(d)

# A2: independent start/end check for function/method nodes in scope
a2 = Counter(); a2_bad = []
for n in scope:
    if n["kind"] == "route": continue
    short = n["name"].split(".")[-1]
    if n["language"] == "python":
        cands = [d for d in py_by[(n["file_path"], short)] if d["kind"] in ("FunctionDef", "AsyncFunctionDef")]
        st = [d for d in cands if d["def"] == n["start_line"]]
        start = "def_line" if st else ("decorator_line" if [d for d in cands if d["decorator"] == n["start_line"]] else ("no_decl_found" if not cands else "mismatch"))
        end = "end_match" if any(d["end"] == n["end_line"] for d in (st or cands)) else "end_mismatch"
    else:
        cands = ts_by[(n["file_path"], short)]
        st = [d for d in cands if n["start_line"] in (d["start"], d["nameLine"])]
        start = "start_line" if st else ("no_decl_found" if not cands else "mismatch")
        end = "end_match" if any(d["end"] == n["end_line"] for d in (st or cands)) else "end_mismatch"
    a2[(n["language"], n["kind"], start, end)] += 1
    if start not in ("def_line", "start_line") or end != "end_match":
        a2_bad.append((n["kind"], n["file_path"], n["name"], n["start_line"], n["end_line"], start, end, [(d.get("def", d.get("start")), d["end"], d["kind"]) for d in cands][:3]))
res["A2_independent_parser"] = {"|".join(k): v for k, v in sorted(a2.items())}
res["A2_not_matching"] = a2_bad

# B: edge line refs (non-contains edges with a line): token check on the source file line
b = Counter(); b_bad = []; b_prov = Counter()
for e in edges:
    if e["kind"] == "contains": continue
    s, t = nodes[e["source"]], nodes[e["target"]]
    if e["line"] is None: b[(e["kind"], "no_line")] += 1; continue
    ls = lines(s["file_path"]) or []
    l = ls[e["line"]-1] if 1 <= e["line"] <= len(ls) else None
    md = json.loads(e["metadata"] or "{}")
    toks = {t["name"].split("::")[-1].split(".")[-1].split("/")[-1]}
    if md.get("refName"): toks.add(md["refName"].split(".")[-1].split("/")[-1])
    toks = {x for x in toks if x}
    if l is None: c = "line_out_of_range"
    elif any(x in l for x in toks): c = "token_on_line"
    elif e["line"] == s["start_line"] and s["kind"] != "file":
        body = "\n".join(ls[s["start_line"]-1:s["end_line"]])
        if s["kind"] == "route" and s["language"] == "python" and t["file_path"] == s["file_path"] and 0 < t["start_line"] - e["line"] <= 6:
            c = "route_decorator_line_for_next_def"
        elif s["kind"] == "route" and any(re.search(r"\b%s\b" % re.escape(x), " ".join(ls[e["line"]-1:e["line"]+5])) for x in toks):
            c = "route_decl_line_component_in_route_object"
        else: c = "points_at_source_decl_line|token_in_source_span" if any(re.search(r"\b%s\b" % re.escape(x), body) for x in toks) else "points_at_source_decl_line|token_absent_from_span"
    elif e["kind"] == "imports" and any(x in " ".join(ls[e["line"]-1:e["line"]+40]).split(";")[0] for x in toks): c = "multiline_import_token_in_statement"
    elif e["kind"] == "navigates" and re.search(r"to=[\"']%s[\"']" % re.escape(t["name"]), l or ""): c = "navigates_link_literal_on_line"
    else: c = "token_not_on_line"
    b[(e["kind"], c)] += 1
    b_prov[(e["kind"], c, e["provenance"])] += 1
    if c in ("token_not_on_line", "line_out_of_range", "points_at_source_decl_line|token_absent_from_span"): b_bad.append((e["kind"], s["file_path"], e["line"], s["qualified_name"], t["qualified_name"], sorted(toks), (l or "").strip()[:100], e["provenance"]))
res["B_edge_lines"] = {f"{k}|{c}": v for (k, c), v in sorted(b.items())}
res["B_not_matching"] = b_bad
res["B_by_provenance"] = {f"{k}|{c}|{p}": v for (k, c, p), v in sorted(b_prov.items(), key=str)}

# C: containment edges vs independent AST parent-child
c = Counter(); c_bad = []
for e in edges:
    if e["kind"] != "contains": continue
    s, t = nodes[e["source"]], nodes[e["target"]]
    want_parent = None if s["kind"] == "file" else s["name"].split("::")[-1]
    short = t["name"].split("::")[-1].split(".")[-1]
    if t["language"] == "python":
        cands = [d for d in py_by[(t["file_path"], t["name"] if t["kind"] == "import" else short)] if d["def"] == t["start_line"] or d["decorator"] == t["start_line"]]
    elif t["language"] in ("typescript", "tsx"):
        cands = [d for d in ts_by[(t["file_path"], t["name"] if t["kind"] == "import" else short)] if t["start_line"] in (d["start"], d["nameLine"])]
    else: cands = None
    if cands is None: k = "language_not_checked"
    elif not cands: k = "target_not_found_by_parser"
    elif any(d["parent"] == want_parent for d in cands): k = "recovered_from_ast"
    else: k = "ast_parent_differs"
    c[(s["kind"], t["kind"], t["language"], k)] += 1
    if k in ("ast_parent_differs", "target_not_found_by_parser"): c_bad.append((k, s["kind"], s["name"], t["kind"], t["name"], t["file_path"], t["start_line"], [(d.get("parent"), d["kind"]) for d in (cands or [])][:3]))
res["C_contains"] = {"|".join(k): v for k, v in sorted(c.items())}
res["C_not_recovered"] = c_bad
bad1 = {(r[1], r[2], r[3]) for r in a1_bad}
bad2 = {(r[1], r[2], r[3]) for r in a2_bad if r[5] not in ("def_line", "start_line")}
res["START_confirmed_by_either"] = {"total": len(scope), "lab_rule_not_exact": len(bad1), "independent_parser_not_matching": len(bad2), "not_confirmed_by_either": sorted(bad1 & (bad2 | {(n["file_path"], n["name"], n["start_line"]) for n in scope if n["kind"] == "route"}))}
res["scope_counts"] = dict(res["scope_counts"])
json.dump(res, open(os.environ.get("ANALYSIS_OUT", f"{T}/step1/logs/analysis.json"), "w"), indent=1, default=str)
for k in ("scope_counts", "parser_versions", "A1_lab_rule", "A2_independent_parser", "START_confirmed_by_either", "B_edge_lines", "B_by_provenance", "C_contains"):
    print("==", k); print(json.dumps(res[k], indent=1))
for k in ("A1_not_exact", "A2_not_matching", "B_not_matching", "C_not_recovered"):
    print("==", k, len(res[k]))
    for r in res[k][:60]: print("  ", r)
