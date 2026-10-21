"""Apply lab/B/scripts/check_lines.py defline() unchanged (imported by exec of its function source) to all
function/method/route nodes in backend/app and frontend/src. REPO points at the task002 checkout (same SHA, clean)."""
import ast, sqlite3, json
from collections import Counter
from pathlib import Path
src = Path("/workspace/traces-research/lab/B/scripts/check_lines.py").read_text()
mod = ast.parse(src); fn = next(n for n in mod.body if isinstance(n, ast.FunctionDef) and n.name == "defline")
ns = {"re": __import__("re"), "REPO": Path("/workspace/traces-research/task002/src/fsft")}
exec(compile(ast.Module(body=[fn], type_ignores=[]), "check_lines.py:defline", "exec"), ns)
db = sqlite3.connect("file:/workspace/traces-research/task002/src/fsft/.codegraph/codegraph.db?mode=ro&immutable=1", uri=True)
rows = db.execute("select kind,file_path,name,start_line from nodes where kind in ('function','method','route') and (file_path like 'backend/app/%' or file_path like 'frontend/src/%')").fetchall()
c = Counter((k, ns["defline"](p, n, s)) for k, p, n, s in rows)
print(len(rows), json.dumps({f"{k}|{v}": n for (k, v), n in sorted(c.items())}, indent=1))
print("exact_1based total:", sum(n for (k, v), n in c.items() if v == "exact_1based"))
