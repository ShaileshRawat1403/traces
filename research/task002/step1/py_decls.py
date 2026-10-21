"""Independent Python declaration extractor with CPython 3.14 stdlib ast. Usage: py_decls.py <root> <file>..."""
import ast, json, sys
root = sys.argv[1]
for rel in sys.argv[2:]:
    tree = ast.parse(open(f"{root}/{rel}").read())
    def visit(node, parent):
        for ch in ast.iter_child_nodes(node):
            here = parent
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                dec = min([d.lineno for d in ch.decorator_list], default=ch.lineno)
                print(json.dumps({"file": rel, "name": ch.name, "kind": type(ch).__name__, "def": ch.lineno, "decorator": dec, "end": ch.end_lineno, "parent": parent, "depth_direct": True}))
                here = ch.name
            elif isinstance(ch, (ast.Assign, ast.AnnAssign)) and parent is None:
                tg = ch.targets if isinstance(ch, ast.Assign) else [ch.target]
                for t in tg:
                    if isinstance(t, ast.Name):
                        print(json.dumps({"file": rel, "name": t.id, "kind": "ModuleAssign", "def": ch.lineno, "decorator": ch.lineno, "end": ch.end_lineno, "parent": None}))
            elif isinstance(ch, (ast.Import, ast.ImportFrom)) and parent is None:
                print(json.dumps({"file": rel, "name": (ch.module if isinstance(ch, ast.ImportFrom) else ch.names[0].name), "kind": type(ch).__name__, "def": ch.lineno, "decorator": ch.lineno, "end": ch.end_lineno, "parent": None}))
            visit(ch, here)
    visit(tree, None)
