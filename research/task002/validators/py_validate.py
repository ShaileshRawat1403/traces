"""Task 002 Python validator (family cpython-ast, CPython 3.14.8 stdlib ast only) and FastAPI rules R1 to R4. Step 7.
Reads source blobs at the pinned SHA via git (task002/src/fsft). Never reads CodeGraph output to decide:
tasks carry only the claim under test (names, lines). Rules implement task002/spec/FASTAPI_RULES.md v2."""
import ast, json, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "adapter"))
from common import Blobs

VALIDATOR = {"name": "traces-py-validator 1.0.0", "version": f"cpython {sys.version.split()[0]} ast", "family": "cpython-ast"}
HTTP = ("get", "post", "put", "patch", "delete", "head", "options")
PKG_ROOTS = ("backend",)


def loc(file, s, e, role, range_kind, **kw):
    d = {"file": file, "start_line": s, "end_line": e, "role": role, "range_kind": range_kind}
    d.update(kw)
    return d


def chk(method, establishes, rule_id, inputs, expected, result, detail):
    return {"method": method, "establishes": establishes, "rule_id": rule_id, "validator": VALIDATOR, "inputs": inputs, "expected": expected, "result": result, "detail": detail}


class Decl:
    def __init__(self, name, kind, node, start, def_line, end, parent, file):
        self.name, self.kind, self.node, self.start, self.def_line, self.end, self.parent, self.file = name, kind, node, start, def_line, end, parent, file

    def __repr__(self):
        return f"{self.file}:{self.def_line} {self.kind} {self.name}"


class Module:
    def __init__(self, path, text):
        self.path, self.text = path, text
        self.tree = ast.parse(text, filename=path)
        self.lines = text.split("\n")
        self.decls = []
        self.top = {}        # module-level name -> Decl or ("import", ...) binding
        self.imports = {}    # name -> ("module", modname) | ("from", modname, attr, node)
        self.parent_of = {}
        for p in ast.walk(self.tree):
            for c in ast.iter_child_nodes(p):
                self.parent_of[c] = p
        self._index(self.tree, None, top=True)

    def _index(self, node, parent, top):
        for ch in ast.iter_child_nodes(node):
            here = parent
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = min([d.lineno for d in ch.decorator_list], default=ch.lineno)
                d = Decl(ch.name, type(ch).__name__, ch, start, ch.lineno, ch.end_lineno, parent, self.path)
                self.decls.append(d)
                if top and parent is None:
                    self.top[ch.name] = d
                self._index(ch, d, top=False)
                continue
            if isinstance(ch, (ast.Assign, ast.AnnAssign)) and parent is None:  # module scope, including module-level for/with/try/if blocks
                tg = ch.targets if isinstance(ch, ast.Assign) else [ch.target]
                for t in tg:
                    if isinstance(t, ast.Name):
                        d = Decl(t.id, "ModuleAssign", ch, ch.lineno, ch.lineno, ch.end_lineno, None, self.path)
                        self.decls.append(d)
                        self.top[t.id] = d
            if isinstance(ch, (ast.Import, ast.ImportFrom)) and parent is None:
                modname = ch.module if isinstance(ch, ast.ImportFrom) else ch.names[0].name
                self.decls.append(Decl(modname, type(ch).__name__, ch, ch.lineno, ch.lineno, ch.end_lineno, None, self.path))
                for a in ch.names:
                    if isinstance(ch, ast.Import):
                        if a.asname:
                            self.imports[a.asname] = ("module", a.name, ch)
                        else:
                            self.imports[a.name.split(".")[0]] = ("module", a.name.split(".")[0], ch)
                    else:
                        mod = self._abs_from(ch)
                        self.imports[a.asname or a.name] = ("from", mod, a.name, ch)
            if isinstance(ch, ast.If) and node is self.tree:
                # module-level if: index nested module-level statements too (conditional imports or assignments)
                self._index(ch, parent, top)
                continue
            self._index(ch, here, top=False) if not isinstance(ch, (ast.Assign, ast.AnnAssign, ast.Import, ast.ImportFrom)) else None

    def _abs_from(self, node):
        if not node.level:
            return node.module
        pkg = self.path.split("/")[:-1]
        root = pkg[1:] if pkg and pkg[0] in PKG_ROOTS else pkg
        base = root[: len(root) - (node.level - 1)] if node.level > 1 else root
        return ".".join(base + ([node.module] if node.module else []))

    def seg(self, node):
        return ast.get_source_segment(self.text, node) or ast.unparse(node)


class Py:
    def __init__(self, root, sha):
        self.blobs = Blobs(root, sha)
        self.mods = {}

    def mod(self, path):
        if path not in self.mods:
            self.mods[path] = Module(path, self.blobs.text(path)) if self.blobs.exists(path) else None
        return self.mods[path]

    def module_file(self, modname):
        if not modname:
            return None
        for r in PKG_ROOTS:
            for cand in (f"{r}/{modname.replace('.', '/')}.py", f"{r}/{modname.replace('.', '/')}/__init__.py"):
                if self.blobs.exists(cand):
                    return cand
        return None

    # ----- binding resolution -----
    def resolve_top(self, m, name, hops=0, trail=None):
        """Resolve a module-level name in module m. Returns ('decl', Decl, trail) | ('module', path, trail) | ('external', desc, trail) | ('unresolved', reason, trail)."""
        trail = list(trail or [])
        if name in m.top and not (name in m.imports and m.imports[name][-1].lineno > m.top[name].def_line):
            return ("decl", m.top[name], trail)
        if name in m.imports:
            b = m.imports[name]
            trail.append(loc(m.path, b[-1].lineno, b[-1].end_lineno, "input", "site"))
            if b[0] == "module":
                f = self.module_file(b[1])
                return ("module", f, trail) if f else ("external", b[1], trail)
            _, modname, attr, node = b
            f = self.module_file(modname)
            sub = self.module_file(f"{modname}.{attr}")
            if f:
                tm = self.mod(f)
                if attr in tm.top:
                    return ("decl", tm.top[attr], trail)
                if attr in tm.imports and hops < 1:
                    return self.resolve_top(tm, attr, hops + 1, trail)
            if sub:
                return ("module", sub, trail)
            if f:
                return ("unresolved", f"{attr} not found in {f}", trail)
            return ("external", f"{modname}.{attr}", trail)
        if name in dir(__builtins__) if not isinstance(__builtins__, dict) else name in __builtins__:
            return ("external", f"builtins.{name}", trail)
        return ("unresolved", f"name {name} not bound at module level of {m.path}", trail)

    def local_names(self, m, fn):
        names = set()
        a = fn.args
        for x in a.posonlyargs + a.args + a.kwonlyargs + ([a.vararg] if a.vararg else []) + ([a.kwarg] if a.kwarg else []):
            names.add(x.arg)
        for n in ast.walk(fn):
            if n is fn:
                continue
            if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
                names.add(n.id)
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(n.name)
            elif isinstance(n, ast.alias):
                names.add((n.asname or n.name).split(".")[0])
            elif isinstance(n, ast.ExceptHandler) and n.name:
                names.add(n.name)
        return names

    def enclosing_funcs(self, m, node):
        out = []
        p = m.parent_of.get(node)
        while p is not None:
            if isinstance(p, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                out.append(p)
            p = m.parent_of.get(p)
        return out

    def enclosing_class(self, m, node):
        p = m.parent_of.get(node)
        while p is not None:
            if isinstance(p, ast.ClassDef):
                return p
            p = m.parent_of.get(p)
        return None

    def resolve_expr(self, m, expr):
        """Resolve Name / Attribute chains. Returns same tuple shapes as resolve_top plus ('local', reason)."""
        if isinstance(expr, ast.Name):
            for fn in self.enclosing_funcs(m, expr):
                if isinstance(fn, ast.Lambda):
                    if expr.id in {a.arg for a in fn.args.args}:
                        return ("local", f"lambda parameter {expr.id}", [])
                    continue
                if expr.id in self.local_names(m, fn):
                    for d in m.decls:
                        if d.name == expr.id and d.node in ast.walk(fn) and d.node is not fn and isinstance(d.node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                            return ("decl", d, [])
                    return ("local", f"{expr.id} is a local or parameter of {fn.name}", [])
            return self.resolve_top(m, expr.id)
        if isinstance(expr, ast.Attribute):
            if isinstance(expr.value, ast.Name) and expr.value.id in ("self", "cls"):
                cls = self.enclosing_class(m, expr)
                if cls is None:
                    return ("unresolved", "self outside class", [])
                for d in m.decls:
                    if d.node in cls.body and d.name == expr.attr:
                        return ("decl", d, [])
                return ("unresolved", f"{expr.attr} not defined in class {cls.name} body", [])
            base = self.resolve_expr(m, expr.value)
            if base[0] == "module":
                tm = self.mod(base[1])
                r = self.resolve_top(tm, expr.attr, 0, base[2])
                if r[0] == "unresolved":
                    sub = None
                return r
            if base[0] == "decl" and base[1].kind == "ClassDef":
                for d in self.mod(base[1].file).decls:
                    if d.node in base[1].node.body and d.name == expr.attr:
                        return ("decl", d, base[2])
                return ("unresolved", f"{expr.attr} not in class {base[1].name} body (inherited or instance attribute)", base[2])
            if base[0] == "external":
                return ("external", f"{base[1]}.{expr.attr}", base[2])
            return ("unresolved", f"receiver {m.seg(expr.value)} is {base[0]}: {base[1] if base[0] != 'decl' else base[1]}", base[2])
        return ("unresolved", f"expression type {type(expr).__name__}", [])

    @staticmethod
    def last(expr):
        if isinstance(expr, ast.Name):
            return expr.id
        if isinstance(expr, ast.Attribute):
            return expr.attr
        return None


def decl_matches(d, tgt):
    return d.file == tgt["file"] and tgt["start_line"] in (d.def_line, d.start) and d.name == tgt["name"].split("::")[-1].split(".")[-1]


KIND_OK = {"function": ("FunctionDef", "AsyncFunctionDef"), "method": ("FunctionDef", "AsyncFunctionDef"), "class": ("ClassDef",), "variable": ("ModuleAssign",), "import": ("Import", "ImportFrom")}


class PyValidator:
    def __init__(self, root, sha):
        self.P = Py(root, sha)

    # ----- presence -----
    def node(self, t):
        m = self.P.mod(t["file"]); inp = [loc(t["file"], t["start_line"], t["end_line"], "from_decl", "declaration")]
        if t["kind"] == "file":
            return {"checks": [chk("parser_presence", "presence", None, [loc(t["file"], 1, t["end_line"], "from_decl", "file")], "module parses with CPython ast", "pass", f"ast.parse ok, {len(m.tree.body)} top-level statements")]}
        if t["kind"] == "route":
            meth = t["name"].split()[0].lower()
            hits = [dc for d in m.decls if d.kind in ("FunctionDef", "AsyncFunctionDef") for dc in d.node.decorator_list
                    if dc.lineno == t["start_line"] and isinstance(dc, ast.Call) and isinstance(dc.func, ast.Attribute) and dc.func.attr == meth]
            if hits:
                dc = hits[0]; lit = dc.args[0].value if dc.args and isinstance(dc.args[0], ast.Constant) else None
                return {"checks": [chk("parser_presence", "presence", None, inp, f"route decorator .{meth}(...) at line {t['start_line']}", "pass", f"decorator {m.seg(dc.func)}({lit!r}, ...) at {t['file']}:{dc.lineno} on def at {m.parent_of[dc].lineno}")]}
            return {"checks": [chk("parser_presence", "presence", None, inp, f"route decorator .{meth}(...) at line {t['start_line']}", "fail", "no such decorator call at this line")]}
        nm = t["name"] if t["kind"] == "import" else t["name"].split("::")[-1].split(".")[-1]
        ds = [d for d in m.decls if d.name == nm]
        at = [d for d in ds if t["start_line"] in (d.def_line, d.start)]
        ok = [d for d in at if d.kind in KIND_OK.get(t["kind"], (d.kind,))]
        exp = f"{t['kind']} '{nm}' declared at line {t['start_line']}"
        if ok:
            d = ok[0]
            return {"checks": [chk("parser_presence", "presence", None, inp, exp, "pass", f"{d.kind} '{d.name}' {'decorator ' + str(d.start) + ', ' if d.start != d.def_line else ''}def/statement line {d.def_line}, end {d.end}")]}
        if at:
            return {"checks": [chk("parser_presence", "presence", None, inp, exp, "inconclusive", f"declaration '{nm}' at this line is {at[0].kind}, not mapped to CodeGraph kind {t['kind']}")]}
        if ds:
            return {"checks": [chk("parser_presence", "presence", None, inp, exp, "fail", f"'{nm}' declared at {', '.join(str(d.def_line) for d in ds)}, not {t['start_line']}")]}
        return {"checks": [chk("parser_presence", "presence", None, inp, exp, "fail", f"no declaration '{nm}' in {t['file']}")]}

    def unresolved(self, t):
        m = self.P.mod(t["file"]); inp = [loc(t["file"], t["line"], t["line"], "site", "site")]
        last = t["ref_name"].split(".")[-1]
        hits = []
        for n in ast.walk(m.tree):
            if getattr(n, "lineno", None) != t["line"] and not (isinstance(n, ast.alias)):
                continue
            if isinstance(n, ast.Name) and n.id == last: hits.append("Name")
            elif isinstance(n, ast.Attribute) and n.attr == last and n.lineno <= t["line"] <= n.end_lineno and n.end_lineno == t["line"] or (isinstance(n, ast.Attribute) and n.attr == last and n.lineno == t["line"]): hits.append("Attribute")
            elif isinstance(n, (ast.Import, ast.ImportFrom)) and (getattr(n, "module", None) == t["ref_name"] or any(a.name == t["ref_name"] or a.name == last or (a.asname == last) for a in n.names)): hits.append(type(n).__name__)
            elif isinstance(n, ast.keyword) and n.arg == last: hits.append("keyword")
            elif isinstance(n, ast.alias) and getattr(n, "lineno", None) == t["line"] and (n.name == t["ref_name"] or n.name == last or n.asname == last or n.name.split(".")[0] == t["ref_name"]): hits.append("import alias")
        exp = f"'{t['ref_name']}' ({t['ref_kind']}) at line {t['line']}"
        if hits:
            return {"checks": [chk("parser_presence", "presence", None, inp, exp, "pass", f"{len(hits)} syntax node(s) named '{last}' at line {t['line']}: {sorted(set(hits))}")]}
        return {"checks": [chk("parser_presence", "presence", None, inp, exp, "fail", f"no Name, Attribute, import alias or keyword '{last}' at line {t['line']}")]}

    # ----- relationships -----
    def edge(self, t, rules):
        k = t["rel_kind"]; s, g = t["src"], t["tgt"]
        if k == "contains":
            return self.contains(t)
        if t.get("missing"):
            if not t.get("value_ref"):
                return {"checks": [chk("location_recovery", "location", None, [], "a line", "inconclusive", "edge without line and without valueRef")], "reason": "no recovery rule"}
            return self.value_ref(t)
        m = self.P.mod(s["file"]); L = t["line"]; site = [loc(s["file"], L, L, "site", "site")]
        if s["kind"] != "file" and not (s["start_line"] <= L <= s["end_line"]):
            return {"checks": [chk("binding_resolution", "relationship", None, site, "site inside source", "inconclusive", f"site line {L} outside source declaration {s['start_line']}-{s['end_line']}")]}
        if k == "imports":
            self.added = []
            c = self.import_check(m, t)
            return {"checks": [c], "add_locations": list(self.added)}
        if s["kind"] == "route" and k == "references":
            return {"checks": [rules.route_handler_check(t)]}
        return {"checks": [self.site_binding(m, t, k, [L], site)]}

    def candidates(self, m, kind, line, name):
        out = []
        for n in ast.walk(m.tree):
            if kind in ("calls", "instantiates"):
                if isinstance(n, ast.Call) and n.lineno <= line <= n.end_lineno and Py.last(n.func) == name and getattr(n.func, "end_lineno", n.lineno) == line or (isinstance(n, ast.Call) and Py.last(n.func) == name and n.func.lineno == line):
                    out.append(n.func)
            elif kind == "extends":
                if isinstance(n, ast.ClassDef) and n.lineno == line:
                    out += [b for b in n.bases if Py.last(b) == name]
            else:
                if isinstance(n, (ast.Name,)) and n.id == name and n.lineno == line and isinstance(n.ctx, ast.Load):
                    out.append(n)
                elif isinstance(n, ast.Attribute) and n.attr == name and n.lineno <= line <= n.end_lineno and isinstance(n.ctx, ast.Load):
                    out.append(n)
        uniq = []
        for x in out:
            if x not in uniq:
                uniq.append(x)
        return uniq

    def site_binding(self, m, t, kind, lines, inputs):
        g = t["tgt"]; nm = g["name"].split("::")[-1].split(".")[-1]
        exp = f"'{nm}' at {t['src']['file']}:{','.join(map(str, lines))} in a {kind} position resolves to {g['file']}:{g['start_line']}"
        cands = [c for L in lines for c in self.candidates(m, kind, L, nm)]
        if not cands:
            return chk("binding_resolution", "relationship", None, inputs, exp, "inconclusive", f"no {kind} syntax for '{nm}' at line(s) {lines}")
        rs = [(c, self.P.resolve_expr(m, c)) for c in cands]
        hits = [(c, r) for c, r in rs if r[0] == "decl" and decl_matches(r[1], g)]
        if kind == "instantiates":
            hits = [(c, r) for c, r in hits if r[1].kind == "ClassDef"]
        if hits:
            c, r = hits[0]
            return chk("binding_resolution", "relationship", None, inputs + r[2] + [loc(g["file"], r[1].start, r[1].end, "to_decl", "declaration")], exp, "pass", f"'{m.seg(c)}' at line {c.lineno} resolves to {r[1]!r}" + (f" via {[(x['file'], x['start_line']) for x in r[2]]}" if r[2] else ""))
        decl_other = [(c, r) for c, r in rs if r[0] == "decl"]
        if decl_other and len(decl_other) == len(rs):
            return chk("binding_resolution", "relationship", None, inputs, exp, "fail", "; ".join(f"'{m.seg(c)}' at line {c.lineno} resolves to {r[1]!r}" for c, r in decl_other))
        return chk("binding_resolution", "relationship", None, inputs, exp, "inconclusive", "; ".join(f"'{m.seg(c)}' at line {c.lineno}: {r[0]} {r[1] if r[0] != 'decl' else repr(r[1])}" for c, r in rs))

    def import_check(self, m, t):
        g = t["tgt"]; L = t["line"]; site = [loc(t["src"]["file"], L, L, "site", "site")]
        st = [n for n in m.tree.body if isinstance(n, (ast.Import, ast.ImportFrom)) and n.lineno <= L <= n.end_lineno]
        st += [n for n in ast.walk(m.tree) if isinstance(n, (ast.Import, ast.ImportFrom)) and n.lineno <= L <= n.end_lineno and n not in st]
        exp = f"import statement at line {L} binds {g['kind']} {g['name']}"
        if not st:
            return chk("syntax_structure", "relationship", None, site, exp, "inconclusive", f"no import statement starts at or spans line {L}")
        n = st[0]
        if n.lineno != L:  # multi-line import: CodeGraph gives the imported name's line; the statement's first line is added as a validator site
            first = loc(t["src"]["file"], n.lineno, n.lineno, "site", "site", range_rule="expression"); site = site + [first]; self.added.append(first)
        if g["kind"] == "import":
            modname = n.module if isinstance(n, ast.ImportFrom) else n.names[0].name
            ok = modname == g["name"] and g["file"] == t["src"]["file"]
            # Decision 002-B correction A: the target is this file's own import node (library module or asset); this observes the statement, it resolves nothing
            return chk("parser_presence", "presence", None, site + [loc(g["file"], g["start_line"], g["end_line"], "to_decl", "declaration")], exp, "pass" if ok else "fail", f"module {m.path} has {type(n).__name__} of {modname!r} at line {L} (import statement observed; target outside validator scope, not resolved)")
        if g["kind"] == "file":
            if isinstance(n, ast.Import):
                files = [self.P.module_file(a.name) for a in n.names]
            else:
                mod = m._abs_from(n); files = [self.P.module_file(mod)] + [self.P.module_file(f"{mod}.{a.name}") for a in n.names]
            ok = g["file"] in files
            if not any(files):
                return chk("binding_resolution", "relationship", None, site, exp, "inconclusive", f"import at line {L} resolves to no repo module")
            return chk("binding_resolution", "relationship", None, site + [loc(g["file"], 1, g["end_line"], "to_decl", "file")], exp, "pass" if ok else "fail", f"import at line {L} resolves to repo modules {sorted(set(f for f in files if f))}")
        nm = g["name"].split("::")[-1].split(".")[-1]
        if isinstance(n, ast.ImportFrom):
            names = [a for a in n.names if a.name == nm or a.asname == nm]
            if not names:
                mf = self.P.module_file(m._abs_from(n))
                if mf and mf != g["file"] and all(a.name != "*" for a in n.names) and not any(self.P.module_file(f"{m._abs_from(n)}.{a.name}") == g["file"] for a in n.names):
                    return chk("binding_resolution", "relationship", None, site, exp, "fail", f"import at line {L} is 'from {m._abs_from(n)} import {', '.join(a.name for a in n.names)}' ({mf}); it binds no name '{nm}' and no module {g['file']}")
                return chk("binding_resolution", "relationship", None, site, exp, "inconclusive", f"import at line {L} binds {[a.name for a in n.names]}; no '{nm}'")
            r = self.P.resolve_top(m, names[0].asname or names[0].name)
            if r[0] == "decl" and decl_matches(r[1], g):
                return chk("binding_resolution", "relationship", None, site + [loc(g["file"], r[1].start, r[1].end, "to_decl", "declaration")], exp, "pass", f"'{nm}' from {m._abs_from(n)} resolves to {r[1]!r}")
            if r[0] == "decl":
                return chk("binding_resolution", "relationship", None, site, exp, "fail", f"'{nm}' resolves to {r[1]!r}, not {g['file']}:{g['start_line']}")
            return chk("binding_resolution", "relationship", None, site, exp, "inconclusive", f"'{nm}': {r[0]} {r[1]}")
        return chk("binding_resolution", "relationship", None, site, exp, "inconclusive", "plain import of a symbol target")

    def contains(self, t):
        p, c = t["src"], t["tgt"]; m = self.P.mod(c["file"])
        nm = c["name"] if c["kind"] == "import" else c["name"].split("::")[-1].split(".")[-1]
        exp = f"{c['kind']} '{nm}' (start {c['start_line']}) is a direct syntax child of {'the module' if p['kind'] == 'file' else repr(p['name'])}"
        inputs0 = [loc(c["file"], c["start_line"], c["end_line"], "to_decl", "declaration"), loc(p["file"], p["start_line"], p["end_line"], "from_decl", "file" if p["kind"] == "file" else "declaration")]
        if c["kind"] == "route":
            ds = [d for d in m.decls if d.kind in ("FunctionDef", "AsyncFunctionDef") and any(dc.lineno == c["start_line"] for dc in d.node.decorator_list)]
        else:
            ds = [d for d in m.decls if d.name == nm and c["start_line"] in (d.def_line, d.start)]
        if not ds:
            return {"checks": [chk("location_recovery", "location", "R-contains", inputs0, exp, "inconclusive", f"child '{nm}' not found at line {c['start_line']} by the parser")], "reason": "child declaration not found at the extractor line"}
        d = ds[0]
        pname = p["name"].split("::")[-1].split(".")[-1]
        parent_ok = (d.parent is None) if p["kind"] == "file" else (d.parent is not None and d.parent.name == pname and p["start_line"] in (d.parent.def_line, d.parent.start))
        child_loc = loc(c["file"], d.start, d.end, "to_decl", "declaration", range_rule="decorator_to_body_end" if d.start != d.def_line else ("binding_statement" if d.kind in ("ModuleAssign", "Import", "ImportFrom") else "header_to_body_end"))
        if p["kind"] == "file":
            par_loc = loc(p["file"], 1, p["end_line"], "from_decl", "file", range_rule="file")
        else:
            pd = [x for x in m.decls if x.name == pname and p["start_line"] in (x.def_line, x.start)]
            par_loc = loc(p["file"], pd[0].start, pd[0].end, "from_decl", "declaration", range_rule="header_to_body_end") if pd else None
        out = {"checks": [], "add_locations": []}
        if par_loc:
            out["checks"].append(chk("location_recovery", "location", "R-contains", [child_loc, par_loc], exp, "pass", f"child {d.kind} '{d.name}' at {d.start}-{d.end}; parent at {par_loc['start_line']}-{par_loc['end_line']}"))
            out["add_locations"] = [child_loc, par_loc]
        if parent_ok:
            out["checks"].append(chk("syntax_structure", "relationship", "R-contains", [child_loc, par_loc], exp, "pass", f"nearest enclosing declaration of '{d.name}' is {d.parent!r}" if d.parent else f"'{d.name}' is a module-level statement"))
            return out
        a = d.parent; trans = False
        while a is not None:
            if p["kind"] != "file" and a.name == pname and p["start_line"] in (a.def_line, a.start):
                trans = True; break
            a = a.parent
        if p["kind"] == "file" and d.parent is not None:
            trans = True
        if trans:
            out["checks"].append(chk("syntax_structure", "relationship", "R-contains", inputs0, exp, "inconclusive", f"immediate enclosing declaration is {d.parent!r}"))
            out["reason"] = "transitive containment, immediate parent not a node"
            return out
        out["checks"].append(chk("syntax_structure", "relationship", "R-contains", inputs0, exp, "fail", f"immediate enclosing declaration of '{d.name}' is {d.parent!r}, not {pname}"))
        return out

    def value_ref(self, t):
        s, g = t["src"], t["tgt"]; m = self.P.mod(s["file"]); nm = g["name"].split("::")[-1].split(".")[-1]
        s0, s1 = (1, s["end_line"]) if s["kind"] == "file" else (s["start_line"], s["end_line"])
        scope = loc(s["file"], s0, s1, "input", "file" if s["kind"] == "file" else "declaration")
        exp = f"inside {s['file']}:{s0}-{s1}, a Load of '{nm}' that resolves to {g['file']}:{g['start_line']}"
        cands = [n for n in ast.walk(m.tree) if isinstance(n, ast.Name) and n.id == nm and isinstance(n.ctx, ast.Load) and s0 <= n.lineno <= s1]
        hits = [(n, r) for n in cands for r in [self.P.resolve_expr(m, n)] if r[0] == "decl" and decl_matches(r[1], g)]
        if not hits:
            return {"checks": [chk("location_recovery", "location", "R-valueRef", [scope], exp, "inconclusive", f"{len(cands)} candidate(s), 0 resolve to the target")], "reason": "no resolving reference inside the source range"}
        lines = sorted({n.lineno for n, _ in hits})
        sites = [loc(s["file"], L, L, "site", "site", range_rule="expression", recovered_by="R-valueRef") for L in lines]
        out = {"checks": [chk("location_recovery", "location", "R-valueRef", [scope] + sites, exp, "pass", f"{len(hits)} hit(s) at line(s) {lines} resolve to {hits[0][1][1]!r}")], "add_locations": sites}
        r = hits[0][1]
        out["checks"].append(chk("binding_resolution", "relationship", None, [dict(x) for x in sites] + r[2] + [loc(g["file"], r[1].start, r[1].end, "to_decl", "declaration")], exp, "pass", f"'{nm}' at line(s) {lines} resolves to {r[1]!r}"))
        return out


class Rules:
    """FASTAPI_RULES R1 to R4 (+ L9, N1, N2 checks)."""
    VERSIONS = {"fastapi": "0.141.1", "@hey-api/openapi-ts": "0.97.3"}

    def __init__(self, pv):
        self.pv, self.P = pv, pv.P
        self.version_gate = self._versions()
        self.routes, self.r1_notes = self._r1()

    def _versions(self):
        out = {}
        lock = self.P.blobs.text("uv.lock").split("\n")
        for i, l in enumerate(lock):
            if l == 'name = "fastapi"' and i + 1 < len(lock):
                out["fastapi"] = (re.match(r'version = "(.*)"', lock[i + 1]).group(1), "uv.lock", i + 1)
        pj = self.P.blobs.text("frontend/package.json").split("\n")
        for i, l in enumerate(pj):
            mm = re.match(r'\s*"@hey-api/openapi-ts": "(.*)"', l)
            if mm:
                out["@hey-api/openapi-ts"] = (mm.group(1), "frontend/package.json", i + 1)
        ok = all(out.get(k, (None,))[0] == v for k, v in self.VERSIONS.items())
        return {"ok": ok, "found": out}

    def gate(self):
        if not self.version_gate["ok"]:
            return f"framework version differs from the rule's pinned versions: {self.version_gate['found']}"
        return None

    # ---------- R1 ----------
    def _literal(self, m, expr, flags, inputs):
        """Resolve a prefix expression to a string literal. Supports str constants and settings.X class defaults."""
        if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
            return expr.value
        if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name):
            r = self.P.resolve_expr(m, expr.value)
            if r[0] == "decl" and r[1].kind == "ModuleAssign":
                inputs.extend(r[2]); d = r[1]; val = d.node.value
                if isinstance(val, ast.Call) and isinstance(val.func, ast.Name):
                    cm = self.P.mod(d.file); cr = self.P.resolve_expr(cm, val.func)
                    if cr[0] == "decl" and cr[1].kind == "ClassDef":
                        for st in cr[1].node.body:
                            if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name) and st.target.id == expr.attr and isinstance(st.value, ast.Constant) and isinstance(st.value.value, str):
                                inputs.append(loc(d.file, d.def_line, d.end, "input", "declaration", range_rule="binding_statement"))
                                inputs.append(loc(cr[1].file, st.lineno, st.end_lineno, "input", "declaration", range_rule="binding_statement"))
                                flags.add("runtime_config_dependent")
                                return st.value.value
        return None

    def _router_assign(self, m, name):
        d = m.top.get(name)
        if d and d.kind == "ModuleAssign" and isinstance(d.node.value, ast.Call):
            f = self.P.resolve_expr(m, d.node.value.func)
            if f[0] == "external" and f[1] in ("fastapi.APIRouter", "fastapi.FastAPI"):
                return d, f[1].split(".")[-1]
        return None, None

    def _kw(self, call, k):
        for kw in call.keywords:
            if kw.arg == k:
                return kw.value
        return None

    def _r1(self):
        notes = []
        if self.gate():
            return [], [self.gate()]
        m = self.P.mod("backend/app/main.py")
        app, kind = self._router_assign(m, "app")
        if not app or kind != "FastAPI":
            return [], ["app = FastAPI(...) not found in backend/app/main.py"]
        routes = []
        app_loc = loc(m.path, app.def_line, app.end, "input", "declaration", range_rule="binding_statement")

        def includes(mod, router_name):
            out = []
            def walk(stmts, cond):
                for st in stmts:
                    if isinstance(st, ast.If):
                        walk(st.body, (cond + " and " if cond else "") + mod.seg(st.test)); walk(st.orelse, (cond + " and " if cond else "") + "not (" + mod.seg(st.test) + ")")
                    elif isinstance(st, ast.Expr) and isinstance(st.value, ast.Call) and isinstance(st.value.func, ast.Attribute) and st.value.func.attr == "include_router" and isinstance(st.value.func.value, ast.Name) and st.value.func.value.id == router_name:
                        out.append((st.value, cond, st))
            walk(mod.tree.body, None)
            return out

        def router_of(mod, expr, inputs):
            if isinstance(expr, ast.Name):
                r = self.P.resolve_top(mod, expr.id)
            else:
                r = self.P.resolve_expr(mod, expr)
            if r[0] != "decl":
                return None, None
            inputs.extend(r[2])
            tm = self.P.mod(r[1].file)
            d, k = self._router_assign(tm, r[1].name)
            return (tm, d) if d else (None, None)

        def visit(mod, rdecl, path_pieces, tags, deps, cond, inputs, flags, depth):
            if depth > 4:
                notes.append("include depth > 4"); return
            call = rdecl.node.value
            pre = self._kw(call, "prefix"); my_flags = set(flags); my_inputs = list(inputs) + [loc(mod.path, rdecl.def_line, rdecl.end, "input", "declaration", range_rule="binding_statement")]
            if pre is not None:
                v = self._literal(mod, pre, my_flags, my_inputs)
                if v is None:
                    notes.append(f"non-literal router prefix at {mod.path}:{rdecl.def_line}"); return
            else:
                v = ""
            my_pieces = path_pieces + [(v, mod.path, rdecl.def_line, "router prefix")]
            t = self._kw(call, "tags"); my_tags = tags + ([e.value for e in t.elts] if isinstance(t, ast.List) else [])
            dp = self._kw(call, "dependencies"); my_deps = deps + ([(mod.path, rdecl.def_line, mod.seg(dp))] if dp is not None else [])
            # decorators on functions in this module bound to this router
            for d in mod.decls:
                if d.kind not in ("FunctionDef", "AsyncFunctionDef") or d.parent is not None:
                    continue
                for dc in d.node.decorator_list:
                    if isinstance(dc, ast.Call) and isinstance(dc.func, ast.Attribute) and dc.func.attr in HTTP and isinstance(dc.func.value, ast.Name) and dc.func.value.id == rdecl.name:
                        pth = dc.args[0].value if dc.args and isinstance(dc.args[0], ast.Constant) else None
                        if pth is None:
                            notes.append(f"non-literal route path at {mod.path}:{dc.lineno}"); continue
                        dt = self._kw(dc, "tags"); rt = my_tags + ([e.value for e in dt.elts] if isinstance(dt, ast.List) else [])
                        nmk = self._kw(dc, "name"); rname = nmk.value if isinstance(nmk, ast.Constant) else d.name
                        ddeps = my_deps + ([(mod.path, dc.lineno, mod.seg(self._kw(dc, "dependencies")))] if self._kw(dc, "dependencies") is not None else [])
                        pieces = my_pieces + [(pth, mod.path, dc.lineno, "decorator path")]
                        fl = set(my_flags) | ({"conditional_route"} if cond else set())
                        routes.append({"method": dc.func.attr.upper(), "file": mod.path, "decorator_line": dc.lineno, "def_line": d.def_line, "end_line": d.end, "handler": d.name,
                                       "full_path": "".join(p[0] for p in pieces), "pieces": pieces, "tags": rt, "route_name": rname, "condition": cond, "dependencies": ddeps,
                                       "response_model": mod.seg(self._kw(dc, "response_model")) if self._kw(dc, "response_model") is not None else None,
                                       "flags": sorted(fl), "inputs": my_inputs + [loc(mod.path, dc.lineno, d.end, "input", "declaration", range_rule="decorator_to_body_end")], "decl": d})
            for c, ccond, st in includes(mod, rdecl.name):
                child_inputs = list(my_inputs) + [loc(mod.path, st.lineno, st.end_lineno, "input", "site", range_rule="expression")]
                tmod, td = router_of(mod, c.args[0], child_inputs)
                if not td:
                    notes.append(f"include target not resolved at {mod.path}:{st.lineno}"); continue
                ipre = self._kw(c, "prefix"); ifl = set(my_flags)
                iv = "" if ipre is None else self._literal(mod, ipre, ifl, child_inputs)
                if iv is None:
                    notes.append(f"non-literal include prefix at {mod.path}:{st.lineno}"); continue
                it = self._kw(c, "tags"); idp = self._kw(c, "dependencies")
                visit(tmod, td, my_pieces + [(iv, mod.path, st.lineno, "include prefix")], my_tags + ([e.value for e in it.elts] if isinstance(it, ast.List) else []),
                      my_deps + ([(mod.path, st.lineno, mod.seg(idp))] if idp is not None else []), " and ".join(x for x in (cond, ccond) if x) or None, child_inputs, ifl, depth + 1)

        appdeps = self._kw(app.node.value, "dependencies")
        for c, cond, st in includes(m, "app"):
            ins = [app_loc, loc(m.path, st.lineno, st.end_lineno, "input", "site", range_rule="expression")]
            tmod, td = router_of(m, c.args[0], ins)
            if not td:
                notes.append(f"app include target not resolved at line {st.lineno}"); continue
            fl = set(); pre = self._kw(c, "prefix")
            v = "" if pre is None else self._literal(m, pre, fl, ins)
            if v is None:
                notes.append(f"non-literal app include prefix at line {st.lineno}"); continue
            visit(tmod, td, [(v, m.path, st.lineno, "app include prefix")], [], ([(m.path, app.def_line, m.seg(appdeps))] if appdeps is not None else []), cond, ins, fl, 0)
        return routes, notes

    def route(self, file, decorator_line):
        return [r for r in self.routes if r["file"] == file and r["decorator_line"] == decorator_line]

    def route_handler_check(self, t):
        s, g = t["src"], t["tgt"]; L = t["line"]
        meth = s["name"].split()[0]
        site = [loc(s["file"], L, L, "site", "site")]
        exp = f"R1: {meth} route decorator at {s['file']}:{L} decorates handler '{g['name']}' (def {g['start_line']})"
        if self.gate():
            return chk("deterministic_rule", "relationship", "R1", site, exp, "inconclusive", self.gate())
        rs = self.route(s["file"], L)
        if not rs:
            return chk("deterministic_rule", "relationship", "R1", site, exp, "inconclusive", f"R1 produced no route at {s['file']}:{L}; notes {self.r1_notes}")
        r = rs[0]
        ok = r["method"] == meth and r["def_line"] == g["start_line"] and r["handler"] == g["name"].split("::")[-1]
        return chk("deterministic_rule", "relationship", "R1", site + r["inputs"], exp, "pass" if ok else "fail",
                   f"R1 finding: {r['method']} {r['full_path']} handler {r['handler']} (decorator {r['decorator_line']}, def {r['def_line']}-{r['end_line']}), tags {r['tags']}, name {r['route_name']}, condition {r['condition']}; extractor route-local path kept in provenance_raw")

    # ---------- R3 (python side + join) ----------
    def opid_function(self):
        m = self.P.mod("backend/app/main.py"); app, _ = self._router_assign(m, "app")
        kw = self._kw(app.node.value, "generate_unique_id_function")
        if kw is None:
            return None, "FastAPI(...) has no generate_unique_id_function (default IDs are out of scope)", []
        r = self.P.resolve_expr(m, kw)
        if r[0] != "decl" or r[1].kind != "FunctionDef":
            return None, f"generate_unique_id_function does not resolve to a repo function: {r[0]} {r[1]}", []
        fn = r[1].node
        rets = [s for s in fn.body if isinstance(s, ast.Return)]
        if len(fn.body) != 1 or not rets or not isinstance(rets[0].value, ast.JoinedStr):
            return None, "unique id function body is not a single f-string return", []
        inputs = [loc(m.path, kw.lineno, kw.end_lineno, "input", "site", range_rule="expression"), loc(m.path, fn.lineno, fn.end_lineno, "input", "declaration", range_rule="header_to_body_end")]
        return (fn, rets[0].value, fn.args.args[0].arg), None, inputs

    def eval_opid(self, route):
        f, err, inputs = self.opid_function()
        if err:
            return None, err, inputs
        fn, js, param = f
        out = []
        for v in js.values:
            if isinstance(v, ast.Constant):
                out.append(v.value)
            elif isinstance(v, ast.FormattedValue) and v.conversion == -1 and v.format_spec is None:
                e = v.value
                if isinstance(e, ast.Attribute) and isinstance(e.value, ast.Name) and e.value.id == param and e.attr in ("name", "path"):
                    out.append(route["route_name"] if e.attr == "name" else route["full_path"])
                elif isinstance(e, ast.Subscript) and isinstance(e.value, ast.Attribute) and isinstance(e.value.value, ast.Name) and e.value.value.id == param and e.value.attr == "tags" and isinstance(e.slice, ast.Constant) and isinstance(e.slice.value, int):
                    if e.slice.value >= len(route["tags"]):
                        return None, "route.tags index out of range", inputs
                    out.append(route["tags"][e.slice.value])
                else:
                    return None, f"unsupported f-string piece {ast.unparse(e)}", inputs
            else:
                return None, "unsupported f-string construct", inputs
        return "".join(out), None, inputs

    @staticmethod
    def camel(s, upper_first=False):
        parts = [p for p in re.split(r"[^A-Za-z0-9]+", s) if p]
        if not parts:
            return s
        r = parts[0][0].upper() + parts[0][1:] if upper_first else parts[0][0].lower() + parts[0][1:]
        return r + "".join(p[0].upper() + p[1:] for p in parts[1:])

    def r3(self, route, facts):
        """Returns (result, detail, inputs, finding)."""
        g = self.gate()
        if g:
            return "inconclusive", g, [], None
        opid, err, inputs = self.eval_opid(route)
        if err:
            return "inconclusive", err, inputs, None
        inputs = list(inputs)
        cand = [s for s in facts["sdk_methods"] if s["http"] == route["method"].lower() and s["url"] == route["full_path"]]
        if not cand:
            return "fail", f"K1: no SDK static method with ({route['method']}, {route['full_path']})", inputs, None
        if len(cand) > 1:
            return "inconclusive", f"K1: {len(cand)} SDK methods match ({route['method']}, {route['full_path']})", inputs, None
        s = cand[0]
        sdk = "frontend/src/client/sdk.gen.ts"; typ = "frontend/src/client/types.gen.ts"; cfg = "frontend/openapi-ts.config.ts"
        inputs += [loc(sdk, s["class_line"], s["class_line"], "input", "declaration"), loc(sdk, s["method_line"], s["method_line"], "input", "declaration"),
                   loc(sdk, s["http_line"], s["http_line"], "input", "site"), loc(sdk, s["url_line"], s["url_line"], "input", "site")]
        # K2 naming (A3 documented claim: hey-api casing)
        mn = facts["config"].get("methodName", [{}])[0]; cn = facts["config"].get("containerName", [{}])[0]; stg = facts["config"].get("strategy", [{}])[0]
        rx, rep = mn.get("regex"), mn.get("replace_with")
        k2 = []
        if not rx or rep is None or not cn.get("text"):
            return "inconclusive", "K2: openapi-ts config methodName/containerName not statically readable", inputs, None
        pyrx = rx.strip("/")
        method_raw = re.sub(pyrx, rep, opid, count=1)
        want_method = self.camel(method_raw); want_data = self.camel(opid) + "Data"
        tmpl = json.loads(cn["text"]) if cn["text"].startswith('"') else cn["text"].strip("'\"")
        want_container = tmpl.replace("{{name}}", self.camel(route["tags"][0], upper_first=True))
        inputs += [loc(cfg, stg.get("line", 1), stg.get("line", 1), "input", "site"), loc(cfg, cn["line"], cn["line"], "input", "site"), loc(cfg, mn["line"], mn["line"], "input", "site")]
        k2 = [("method", s["method"], want_method), ("data type", s["data_type"], want_data), ("container", s["class"], want_container)]
        k2ok = all(a == b for _, a, b in k2)
        # cross-check: Data type url literal
        dts = [d for d in facts["data_types"] if d["name"] == s["data_type"]]
        xok = bool(dts) and dts[0]["url"] == route["full_path"]
        resolves = isinstance(s["data_type_resolves_to"], list) and any(r["file"] == typ and dts and r["start_line"] == dts[0]["line"] for r in s["data_type_resolves_to"])
        if dts:
            inputs += [loc(typ, dts[0]["line"], dts[0]["line"], "input", "declaration"), loc(typ, dts[0]["url_line"], dts[0]["url_line"], "input", "site")]
        detail = (f"operation id {opid!r} from f-string at main.py (route.tags[0]={route['tags'][0]!r}, route.name={route['route_name']!r}); "
                  f"K1 unique: {s['class']}.{s['method']} (.{s['http']} at sdk.gen.ts:{s['http_line']}, url {s['url']!r} at :{s['url_line']}); "
                  f"K2 (A3, documented claim): " + ", ".join(f"{k} {a!r} vs expected {b!r}" for k, a, b in k2) + f" from methodName {rx} -> {rep!r}, containerName {cn['text']}, strategy {stg.get('text')}; "
                  f"cross-check: {s['data_type']} url {dts[0]['url'] if dts else None!r} at types.gen.ts:{dts[0]['url_line'] if dts else None} vs R1 {route['full_path']!r}; "
                  f"TS binding of the Options<> type argument to types.gen.ts: {resolves}")
        finding = {"operation_id": opid, "method": route["method"], "full_path": route["full_path"], "sdk_class": s["class"], "sdk_method": s["method"], "sdk_method_lines": [s["method_line"], s["method_end"]], "data_type": s["data_type"]}
        if not k2ok or not resolves:
            return "inconclusive", "generated client may be out of date (K1 with K2 mismatch); " + detail, inputs, finding
        if not xok:
            return "fail", "cross-check failed; " + detail, inputs, finding
        return "pass", detail, inputs, finding

    # ---------- R2 ----------
    def _dep_from_annotation(self, m, ann):
        """Returns ('dep', callable_decl_or_desc, alias_info, value_type, inputs) | ('none', why) | ('inconclusive', why)."""
        if ann is None:
            return ("none", "no annotation")
        if isinstance(ann, ast.Subscript) and self.P.resolve_expr(m, ann.value)[:2] == ("external", "typing.Annotated"):
            return self._annotated(m, ann, None, [])
        r = self.P.resolve_expr(m, ann)
        if r[0] == "decl" and r[1].kind == "ModuleAssign":
            d = r[1]; am = self.P.mod(d.file); v = d.node.value
            if isinstance(v, ast.Subscript) and self.P.resolve_expr(am, v.value)[:2] == ("external", "typing.Annotated"):
                return self._annotated(am, v, d, r[2] + [loc(d.file, d.def_line, d.end, "input", "declaration", range_rule="binding_statement")])
            return ("inconclusive", f"annotation resolves to a non-Annotated assignment {d!r}")
        if r[0] == "decl" and r[1].kind == "ClassDef":
            return ("none", f"annotation is repo class {r[1]!r}")
        if r[0] == "external":
            if r[1] in ("builtins.str", "builtins.int", "builtins.bool", "uuid.UUID", "builtins.float"):
                return ("none", f"annotation is {r[1]}")
            return ("inconclusive", f"annotation resolves to external {r[1]}")
        return ("inconclusive", f"annotation {m.seg(ann)}: {r[0]} {r[1]}")

    def _annotated(self, m, sub, alias, inputs):
        elts = sub.slice.elts if isinstance(sub.slice, ast.Tuple) else [sub.slice]
        vt = elts[0]; vtr = self.P.resolve_expr(m, vt)
        deps = [e for e in elts[1:] if isinstance(e, ast.Call) and Py.last(e.func) in ("Depends", "Security")]
        if not deps:
            return ("none", "Annotated without Depends")
        e = deps[0]
        fr = self.P.resolve_expr(m, e.func)
        if Py.last(e.func) == "Security" or not (fr[0] == "external" and fr[1] == "fastapi.Depends"):
            return ("inconclusive", f"{m.seg(e)} is Security or not fastapi.Depends")
        if not e.args:
            return ("inconclusive", "Depends() without argument")
        cr = self.P.resolve_expr(m, e.args[0])
        if cr[0] != "decl":
            return ("inconclusive", f"dependency callable {m.seg(e.args[0])}: {cr[0]} {cr[1]}")
        return ("dep", cr[1], alias, (vtr, m.seg(vt), m.path), inputs + cr[2] + [loc(cr[1].file, cr[1].start, cr[1].end, "input", "declaration")])

    def deps_of(self, m, fn_decl):
        """Direct parameter-level dependencies of a FunctionDef. Returns (deps, complete, notes)."""
        fn = fn_decl.node; a = fn.args; out = []; complete = True; notes = []
        params = a.posonlyargs + a.args + a.kwonlyargs
        defaults = dict(zip([p.arg for p in (a.posonlyargs + a.args)][::-1], a.defaults[::-1]))
        defaults.update({p.arg: d for p, d in zip(a.kwonlyargs, a.kw_defaults) if d is not None})
        for p in params:
            if p.arg in ("self", "cls"):
                continue
            dfl = defaults.get(p.arg)
            if isinstance(dfl, ast.Call) and Py.last(dfl.func) in ("Depends", "Security"):
                fr = self.P.resolve_expr(m, dfl.func)
                if Py.last(dfl.func) == "Security" or not dfl.args or not (fr[0] == "external" and fr[1] == "fastapi.Depends"):
                    complete = False; notes.append(f"{p.arg}: {m.seg(dfl)} inconclusive"); continue
                cr = self.P.resolve_expr(m, dfl.args[0])
                if cr[0] != "decl":
                    complete = False; notes.append(f"{p.arg}: callable {cr[0]}"); continue
                out.append({"param": p.arg, "param_line": p.lineno, "callable": cr[1], "alias": None, "value_type": None, "inputs": cr[2]}); continue
            r = self._dep_from_annotation(m, p.annotation)
            if r[0] == "dep":
                out.append({"param": p.arg, "param_line": p.lineno, "param_end": p.end_lineno, "callable": r[1], "alias": r[2], "value_type": r[3], "inputs": r[4]})
            elif r[0] == "inconclusive":
                complete = False; notes.append(f"{p.arg}: {r[1]}")
            else:
                notes.append(f"{p.arg}: no dependency ({r[1]})")
        return out, complete, notes

    def closure(self, m, fn_decl, depth=0, path=()):
        deps, complete, notes = self.deps_of(m, fn_decl)
        res = []
        for d in deps:
            c = d["callable"]
            res.append({"depth": depth + 1, "path": list(path) + [fn_decl.name], **d})
            if c.kind in ("FunctionDef", "AsyncFunctionDef") and depth < 4:
                sub, sc, sn = self.closure(self.P.mod(c.file), c, depth + 1, tuple(list(path) + [fn_decl.name]))
                res += sub; complete = complete and sc; notes += sn
            elif c.kind == "ModuleAssign":
                notes.append(f"{c.name}: instance (leaf)")
        return res, complete, notes

    def r2(self, route):
        """Direct and transitive dependencies of the route handler plus dependencies= entries on its R1 path."""
        if self.gate():
            return None
        m = self.P.mod(route["file"]); d = route["decl"]
        cl, complete, notes = self.closure(m, d)
        if route["dependencies"]:
            complete = False; notes.append(f"dependencies= on R1 path: {route['dependencies']} (resolution of list entries not needed for Task 002 handlers)")
        return {"closure": cl, "complete": complete, "notes": notes}

    # ---------- R4 ----------
    STEP = {"add": "session_stage", "add_all": "session_stage", "delete": "session_stage", "commit": "session_commit", "refresh": "session_reload"}

    def r4(self, route):
        if self.gate():
            return {"result": "inconclusive", "detail": self.gate()}
        m = self.P.mod(route["file"]); fn = route["decl"].node
        deps, complete, notes = self.deps_of(m, route["decl"])
        bound = {}
        for d in deps:
            c = d["callable"]; vt = d["value_type"]
            if c.name == "get_db" and c.file == "backend/app/api/deps.py" and vt and vt[0][0] == "external" and vt[0][1] == "sqlmodel.Session":
                # get_db yields Session(engine): generator with `with Session(...) as x: yield x`
                gm = self.P.mod(c.file); gen_ok = any(isinstance(n, ast.Yield) for n in ast.walk(c.node))
                withs = [w for w in ast.walk(c.node) if isinstance(w, ast.With) for it in w.items if isinstance(it.context_expr, ast.Call) and self.P.resolve_expr(gm, it.context_expr.func)[:2] == ("external", "sqlmodel.Session")]
                if gen_ok and withs:
                    bound[d["param"]] = d
        steps, observed_only, problems = [], [], []
        top = list(fn.body)
        def stmt_index(node):
            p = node
            while m.parent_of.get(p) is not fn and m.parent_of.get(p) is not None:
                p = m.parent_of[p]
            return top.index(p) if p in top else None
        for n in sorted([n for n in ast.walk(fn) if isinstance(n, ast.Call)], key=lambda n: (n.lineno, n.col_offset)):
            f = n.func
            if not isinstance(f, ast.Attribute) or not isinstance(f.value, ast.Name):
                continue
            r = f.value.id
            if f.attr == "model_validate":
                cr = self.P.resolve_expr(m, f.value)
                if cr[0] == "decl" and cr[1].kind == "ClassDef" and cr[1].file == "backend/app/models.py":
                    table = any(k.arg == "table" and isinstance(k.value, ast.Constant) and k.value.value is True for k in cr[1].node.keywords)
                    steps.append({"type": "model_validation", "line": n.lineno, "end": n.end_lineno, "call": m.seg(n), "model": cr[1], "table_model": table, "inputs": cr[2], "stmt": stmt_index(n)})
                continue
            if r in bound:
                reassigned = [x for x in ast.walk(fn) if isinstance(x, ast.Name) and x.id == r and isinstance(x.ctx, (ast.Store, ast.Del)) and x.lineno < n.lineno]
                if reassigned:
                    problems.append(f"{r} reassigned at line {reassigned[0].lineno} before {n.lineno}"); continue
                if f.attr in self.STEP:
                    steps.append({"type": self.STEP[f.attr], "line": n.lineno, "end": n.end_lineno, "call": m.seg(n), "receiver": r, "stmt": stmt_index(n)})
                elif f.attr in ("get", "exec", "execute", "flush", "merge"):
                    observed_only.append((n.lineno, m.seg(n)))
        # path condition (R4 step 4): a stage followed by a commit on the same receiver; both calls are direct parts of top-level
        # straight-line statements of the handler body, and every statement from the stage through the commit is straight-line
        STRAIGHT = (ast.Expr, ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Return)
        def direct(s):
            st = top[s["stmt"]] if s["stmt"] is not None else None
            if not isinstance(st, STRAIGHT):
                return False
            p = m.parent_of.get(next(x for x in ast.walk(st) if isinstance(x, ast.Call) and x.lineno == s["line"] and m.seg(x) == s["call"]))
            while p is not None and p is not st:
                if isinstance(p, (ast.Lambda, ast.IfExp, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.BoolOp)):
                    return False
                p = m.parent_of.get(p)
            return True
        stage = [s for s in steps if s["type"] == "session_stage"]; commit = [s for s in steps if s["type"] == "session_commit"]
        ok_pair = None
        for a in stage:
            for b in commit:
                if a["receiver"] == b["receiver"] and a["line"] < b["line"] and direct(a) and direct(b) and all(isinstance(x, STRAIGHT) for x in top[a["stmt"]: b["stmt"] + 1]):
                    ok_pair = (a, b); break
            if ok_pair:
                break
        res = {"steps": steps, "observed_only": observed_only, "problems": problems, "bound": bound, "deps_complete": complete, "notes": notes}
        if problems:
            res.update(result="inconclusive", detail="; ".join(problems))
        elif not ok_pair:
            res.update(result="inconclusive" if stage or commit else "fail", detail="no session_stage followed by session_commit on the same bound receiver in straight-line code")
        else:
            res.update(result="pass", detail=f"stage at {ok_pair[0]['line']}, commit at {ok_pair[1]['line']} on receiver {ok_pair[0]['receiver']} bound by R2 to {bound[ok_pair[0]['receiver']]['alias'].name} -> sqlmodel.Session, callable get_db")
        return res
