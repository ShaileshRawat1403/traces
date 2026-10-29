"""JavaScript import check (D-030): does a CodeGraph `imports` edge from a JavaScript file name the file its
`import ... from 'x'`, `export ... from 'x'`, `require('x')` or `import('x')` resolves to?

The parse comes from the pinned TypeScript 6.0.3 parser (Apache-2.0, `js/js_imports.js`; parser only, no type checker).
Specifier resolution is done here, deterministically, against the Git tree at the pinned SHA: Node's CommonJS order for
relative specifiers (exact path, then .js .cjs .mjs .jsx .json, then the directory's package.json `main`, then
index.*). Package specifiers, absolute paths, aliases and computed specifiers are never resolved: they are inconclusive.
No target code runs. Calls and references in JavaScript are not checked here (deferred to v1.1, D-030), so they stay
unvalidated."""
from __future__ import annotations

import json
import posixpath
import re
from collections.abc import Callable, Container, Iterable
from typing import Any

JS_EXT = (".js", ".cjs", ".mjs", ".jsx")
TRY_EXT = (".js", ".cjs", ".mjs", ".jsx", ".json")
FAMILY = "typescript-compiler"
REQUIRE_RE = re.compile(r"""(?<![A-Za-z0-9_$.])require\s*\(\s*(['"])((?:(?!\1)[^\\\n])+)\1\s*\)""")
IMPORT_WORD_RE = re.compile(r"(?<![A-Za-z0-9_$])(?:import|from|export)(?![A-Za-z0-9_$])")


def is_js(path: str) -> bool:
    return path.endswith(JS_EXT)


def validator(parser_version: str) -> dict[str, str]:
    return {"name": "traces-js-imports 1.0.0", "version": f"{parser_version} parser (no type checker)", "family": FAMILY}


def _rel(spec: str) -> bool:
    return spec in (".", "..") or spec.startswith(("./", "../"))


def resolve(importer: str, spec: str, tree: Container[str], read: Callable[[str], str | None], _depth: int = 0) -> tuple[str | None, str]:
    """Repo file a specifier resolves to from `importer`, or (None, why). Relative specifiers only."""
    if not _rel(spec):
        return None, "package or absolute specifier: not resolved (outside the repository's own files)"
    base = posixpath.normpath(posixpath.join(posixpath.dirname(importer), spec))
    if base == ".":
        base = ""
    if base == ".." or base.startswith("../"):
        return None, "specifier leaves the repository"
    for c in ([base] if base else []) + [base + e for e in TRY_EXT if base]:
        if c in tree:
            return c, f"file {c}"
    pj = f"{base}/package.json" if base else "package.json"
    if pj in tree and _depth < 2:
        try:
            main = json.loads(read(pj) or "{}").get("main")
        except (ValueError, AttributeError):
            main = None
        if isinstance(main, str) and main:
            hit, _why = _main(base, main, tree, read, _depth)
            if hit:
                return hit, f"{pj} main -> {hit}"
    for e in TRY_EXT:
        c = f"{base}/index{e}" if base else f"index{e}"
        if c in tree:
            return c, f"directory index {c}"
    return None, "resolves to no tracked file"


def _main(base: str, main: str, tree: Container[str], read: Callable[[str], str | None], depth: int) -> tuple[str | None, str]:
    spec = "./" + main.removeprefix("./")
    return resolve(f"{base}/package.json" if base else "package.json", spec, tree, read, depth + 1)


def require_specs(text: str) -> list[str]:
    return [m.group(2) for m in REQUIRE_RE.finditer(text)]


def l3_pass(seg: str, importer: str, tgt: dict[str, Any], tree: Container[str], read: Callable[[str], str | None]) -> tuple[bool, str]:
    """L3 for a JavaScript import site: the ES keywords as before, or a CommonJS require('x') / require("x") whose
    specifier matches exactly (a file target: resolves to that file; an import node: the same module string)."""
    if IMPORT_WORD_RE.search(seg):
        return True, "found import|from|export"
    for spec in require_specs(seg):
        if tgt.get("kind") == "import" and spec == tgt.get("name"):
            return True, f"found require({spec!r})"
        if tgt.get("kind") == "file" and resolve(importer, spec, tree, read)[0] == tgt.get("file"):
            return True, f"found require({spec!r}) resolving to {tgt.get('file')}"
    specs = require_specs(seg)
    return False, (f"require specifier(s) {specs} do not match {tgt.get('kind')} {tgt.get('name')!r}" if specs
                   else "no import|from|export and no require('...') with a literal specifier")


def _loc(file: str, s: int, e: int, role: str, range_kind: str, **kw: Any) -> dict[str, Any]:
    return {"file": file, "start_line": s, "end_line": e, "role": role, "range_kind": range_kind, **kw}


def edge_check(t: dict[str, Any], parsed: dict[str, Any], tree: Container[str], read: Callable[[str], str | None],
               parser_version: str) -> dict[str, Any] | None:
    """Checks for one `imports` edge task (orchestrator task shape), or None when there is nothing to check."""
    if t.get("rel_kind") != "imports" or t.get("missing") or t.get("line") is None:
        return None
    V = validator(parser_version)
    s, g, L = t["src"], t["tgt"], int(t["line"])
    f = s["file"]
    site = [_loc(f, L, L, "site", "site")]
    exp = f"module reference at {f}:{L} names {g['kind']} {g['name']}"

    def chk(method: str, establishes: str, inputs: list[dict[str, Any]], result: str, detail: str) -> dict[str, Any]:
        return {"method": method, "establishes": establishes, "rule_id": None, "validator": V, "inputs": inputs, "expected": exp,
                "result": result, "detail": detail}

    info = parsed.get(f) or {"error": "file was not parsed"}
    if "error" in info:
        return {"checks": [chk("syntax_structure", "relationship", site, "inconclusive", info["error"])]}
    refs = [r for r in info["refs"] if r["start_line"] <= L <= r["end_line"]]
    note = ""
    if info["require_shadowed_at"]:
        dropped = [r for r in refs if r["how"] == "require"]
        refs = [r for r in refs if r["how"] != "require"]
        if dropped:
            note = f"; require is a local binding at line(s) {info['require_shadowed_at']}, so require(...) is not trusted"
    if not refs:
        return {"checks": [chk("syntax_structure", "relationship", site, "inconclusive",
                               f"no import, export, require() or import() with a literal specifier spans line {L}"
                               f" ({info['parse_errors']} parse error(s)){note}")]}
    added: list[dict[str, Any]] = []
    if g["kind"] == "import":
        ok = g["file"] == f and any(r["spec"] == g["name"] for r in refs)
        return {"checks": [chk("parser_presence", "presence", site + [_loc(g["file"], g["start_line"], g["end_line"], "to_decl", "declaration")],
                               "pass" if ok else "fail",
                               f"{f} has {', '.join(_spell(r) for r in refs)} at line {L} (module reference "
                               "observed; package outside validator scope, not resolved)" + note)]}
    if g["kind"] != "file":
        return {"checks": [chk("binding_resolution", "relationship", site, "inconclusive",
                               "a JavaScript import of a symbol is not resolved in v1 (D-030: names, calls and references are v1.1)")]}
    res = [(r, *resolve(f, r["spec"], tree, read)) for r in refs]
    hits = [x for x in res if x[1] == g["file"]]
    desc = "; ".join(f"{_spell(r)} at line {r['start_line']}: {why}" for r, _hit, why in res)
    if hits:
        r = hits[0][0]
        if r["start_line"] != L:
            first = _loc(f, r["start_line"], r["start_line"], "site", "site", range_rule="expression")
            site, added = site + [first], [first]
        return {"checks": [chk("binding_resolution", "relationship", site + [_loc(g["file"], 1, g["end_line"], "to_decl", "file")], "pass",
                               desc + note)], "add_locations": added}
    if all(hit is not None for _r, hit, _why in res):
        return {"checks": [chk("binding_resolution", "relationship", site, "fail", desc + note)]}
    return {"checks": [chk("binding_resolution", "relationship", site, "inconclusive", desc + note)]}


def _spell(r: dict[str, Any]) -> str:
    return {"require": f"require({r['spec']!r})", "dynamic_import": f"import({r['spec']!r})"}.get(r["how"], f"{r['how']} ... from {r['spec']!r}")


def files_to_parse(tasks: Iterable[dict[str, Any]]) -> list[str]:
    return sorted({t["src"]["file"] for t in tasks if t.get("rel_kind") == "imports"})
