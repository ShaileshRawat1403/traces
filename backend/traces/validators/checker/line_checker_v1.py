"""line_checker_v1: start-line accuracy of CodeGraph function, method and route nodes.

Frozen for Task 002 (Decision 002-A). Runs on CPython 3.14 (stdlib only) plus a TypeScript helper (ts_decls_v1.js).
Read-only: opens the CodeGraph SQLite index with mode=ro&immutable=1 and reads source with `git show <sha>:<path>`.

Modes
  parser     (default, the accepted S2 measure, 378/379 on fsft @ b1125d88):
             function/method -> declaration line from an independent parser (Python 3.14 ast, TypeScript compiler API);
             route           -> route rule.
  lab_route  (audit variant, 351/379): function/method -> Lab Task 001 regex rule `defline` (copied unchanged from
             lab/B/scripts/check_lines.py lines 7-15); route -> route rule.
The unmodified Lab script (no route rule, 320/379) is NOT reimplemented here; run it from lab/ for that number.

Usage:
  python line_checker_v1.py --db <codegraph.db> --src <repo root> --sha <commit> --ts-module <typescript pkg dir>
                            [--mode parser|lab_route] [--out result.json]
"""
import argparse, ast, json, os, re, sqlite3, subprocess, sys
from collections import Counter, defaultdict

VERSION = "line_checker_v1.0.0"
HERE = os.path.dirname(os.path.abspath(__file__))
SCOPE_KINDS = ("function", "method", "route")
SCOPE_PREFIXES = ("backend/app/", "frontend/src/")


def git_lines(src, sha, path, _c={}):
    if path not in _c:
        try: _c[path] = subprocess.check_output(["git", "-C", src, "show", f"{sha}:{path}"], text=True).splitlines()
        except subprocess.CalledProcessError: _c[path] = None
    return _c[path]


def py_decls(src, sha, files):
    """Python 3.14 ast: every FunctionDef/AsyncFunctionDef/ClassDef with def line, first decorator line, end line."""
    out = defaultdict(list)
    for rel in files:
        tree = ast.parse("\n".join(git_lines(src, sha, rel)) + "\n")
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                dec = min([d.lineno for d in n.decorator_list], default=n.lineno)
                out[(rel, n.name)].append({"kind": type(n).__name__, "def": n.lineno, "decorator": dec, "end": n.end_lineno})
    return out


def ts_decls(src, ts_module, files):
    env = dict(os.environ, TS_MODULE=ts_module)
    raw = subprocess.check_output(["node", os.path.join(HERE, "ts_decls_v1.js"), src] + files, text=True, env=env)
    out = defaultdict(list); diags = 0
    for line in raw.splitlines():
        d = json.loads(line)
        if "parse_diagnostics" in d: diags += 1; continue
        out[(d["file"], d["name"])].append(d)
    return out, diags


def lab_defline(lines, name, line):
    """Unchanged logic of lab/B/scripts/check_lines.py defline() (lines 7-15), given the file's lines."""
    if lines is None: return "missing_file"
    pat = re.compile(r"(def|function|class|const|let)\s+%s\b|\b%s\s*[:=(]" % (re.escape(name.split(".")[-1]), re.escape(name.split(".")[-1])))
    def hit(n): return 1 <= n <= len(lines) and pat.search(lines[n-1])
    if hit(line): return "exact_1based"
    if hit(line+1): return "off_by_minus1"
    if 1 <= line <= len(lines) and lines[line-1].lstrip().startswith("@"): return "decorator_line"
    return "other"


def route_ok(node, lines):
    """Backend (id route:<file>:<line>:<METHOD>:<path>): reported line starts with '@' and the decorator call,
    joined from that line through the first line containing ')' (max 6 lines), contains .<method>("<path>" or '<path>'.
    Frontend TanStack (no METHOD in id): reported line contains createFileRoute and the route path without trailing '/'."""
    i = node["start_line"] - 1
    if not lines or not (0 <= i < len(lines)): return False
    m = re.match(r"route:(.+):(\d+):([A-Z]+):(.*)$", node["id"])
    if m:
        span = ""
        for j in range(i, min(i + 6, len(lines))):
            span += lines[j].strip() + " "
            if ")" in lines[j]: break
        return lines[i].lstrip().startswith("@") and re.search(r"\.%s\(\s*[\"']%s[\"']" % (m.group(3).lower(), re.escape(m.group(4))), span) is not None
    return "createFileRoute" in lines[i] and node["name"].rstrip("/") in lines[i]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True); ap.add_argument("--src", required=True); ap.add_argument("--sha", required=True)
    ap.add_argument("--ts-module", required=True); ap.add_argument("--mode", default="parser", choices=["parser", "lab_route"])
    ap.add_argument("--out")
    a = ap.parse_args()
    head = subprocess.check_output(["git", "-C", a.src, "rev-parse", "HEAD"], text=True).strip()
    if head != a.sha: sys.exit(f"HEAD {head} != --sha {a.sha}")
    db = sqlite3.connect(f"file:{a.db}?mode=ro&immutable=1", uri=True); db.row_factory = sqlite3.Row
    nodes = [dict(r) for r in db.execute("select id, kind, name, file_path, language, start_line, end_line from nodes")]
    scope = [n for n in nodes if n["kind"] in SCOPE_KINDS and n["file_path"].startswith(SCOPE_PREFIXES)]
    pyfiles = sorted({n["file_path"] for n in scope if n["language"] == "python"})
    tsfiles = sorted({n["file_path"] for n in scope if n["language"] in ("typescript", "tsx")})
    pyd = py_decls(a.src, a.sha, pyfiles)
    tsd, ts_diag = ts_decls(a.src, a.ts_module, tsfiles)
    ts_version = json.load(open(os.path.join(a.ts_module, "package.json")))["version"]
    per = []
    for n in sorted(scope, key=lambda n: (n["file_path"], n["start_line"], n["name"])):
        lines = git_lines(a.src, a.sha, n["file_path"])
        short = n["name"].split("::")[-1].split(".")[-1]
        if n["kind"] == "route":
            ok, why = route_ok(n, lines), "route_rule"
        elif a.mode == "lab_route":
            r = lab_defline(lines, n["name"], n["start_line"]); ok, why = r == "exact_1based", "lab_defline:" + r
        elif n["language"] == "python":
            c = [d for d in pyd[(n["file_path"], short)] if d["kind"] != "ClassDef"]
            ok = any(d["def"] == n["start_line"] for d in c)
            why = "py_def_line" if ok else ("py_decorator_line" if any(d["decorator"] == n["start_line"] for d in c) else ("py_no_decl" if not c else "py_mismatch"))
        else:
            c = tsd[(n["file_path"], short)]
            ok = any(n["start_line"] in (d["start"], d["nameLine"]) for d in c)
            why = "ts_decl_line" if ok else ("ts_no_decl" if not c else "ts_mismatch:" + ",".join(f'{d["kind"]}@{d["start"]}' for d in c))
        per.append({"kind": n["kind"], "file": n["file_path"], "name": n["name"], "start_line": n["start_line"], "exact": ok, "basis": why})
    exact = sum(p["exact"] for p in per)
    res = {"version": VERSION, "mode": a.mode, "sha": a.sha, "db": a.db,
           "parsers": {"python": sys.version.split()[0], "typescript": ts_version, "ts_files_with_parse_diagnostics": ts_diag},
           "scope": dict(Counter(p["kind"] for p in per)), "total": len(per), "exact": exact,
           "share": round(exact / len(per), 4) if per else None,
           "by_kind_basis": {f'{k}|{b}': v for (k, b), v in sorted(Counter((p["kind"], p["basis"]) for p in per).items())},
           "not_exact": [p for p in per if not p["exact"]]}
    if a.out: json.dump({**res, "nodes": per}, open(a.out, "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
