"""F-10 (D-030): the JavaScript import check. Specifier resolution, the CommonJS L3 token and the edge check."""
from __future__ import annotations

import json

from traces.validators import js_imports as J

TREE = {"src/app.js", "src/routes/auth.route.js", "src/services/index.js", "src/services/user.service.js",
        "src/utils/catchAsync.js", "src/config/config.json", "lib/pkg/package.json", "lib/pkg/dist/main.js", "index.js"}
READ = {"lib/pkg/package.json": json.dumps({"main": "dist/main.js"})}.get


def test_resolution_follows_node_commonjs_order():
    r = lambda imp, spec: J.resolve(imp, spec, TREE, READ)[0]  # noqa: E731
    assert r("src/app.js", "./routes/auth.route") == "src/routes/auth.route.js"
    assert r("src/app.js", "./routes/auth.route.js") == "src/routes/auth.route.js"
    assert r("src/routes/auth.route.js", "../services") == "src/services/index.js"
    assert r("src/app.js", "./config/config") == "src/config/config.json"
    assert r("src/app.js", "../lib/pkg") == "lib/pkg/dist/main.js"
    assert r("src/app.js", "..") == "index.js"
    assert r("src/app.js", "express") is None  # packages are never resolved
    assert r("src/app.js", "/etc/passwd") is None
    assert r("src/app.js", "../../outside") is None
    assert r("src/app.js", "./missing") is None


def test_l3_accepts_require_only_with_an_exact_module_path():
    tgt = {"kind": "file", "file": "src/services/index.js", "name": "index.js"}
    for line in ("const { userService } = require('../services');", 'const s = require("../services")',
                 "const s = require( '../services/index.js' )"):
        assert J.l3_pass(line, "src/controllers/a.js", tgt, TREE, READ)[0], line
    for line in ("const s = require('../services/user.service');", "const s = load('../services');",
                 "const s = x.require('../services');", "const s = require(`../services`);", "// nothing here"):
        assert not J.l3_pass(line, "src/controllers/a.js", tgt, TREE, READ)[0], line
    assert J.l3_pass("import x from './y'", "src/a.js", tgt, TREE, READ)[0]  # ES keywords: unchanged rule
    pkg = {"kind": "import", "file": "src/app.js", "name": "express"}
    assert J.l3_pass("const express = require('express');", "src/app.js", pkg, TREE, READ)[0]
    assert not J.l3_pass("const express = require('express-x');", "src/app.js", pkg, TREE, READ)[0]


def _task(src, line, tgt_kind, tgt_file, tgt_name="x"):
    return {"type": "edge", "rk": "r", "rel_kind": "imports", "line": line, "missing": False,
            "src": {"file": src, "name": src, "kind": "file", "start_line": 1, "end_line": 9},
            "tgt": {"file": tgt_file, "name": tgt_name, "kind": tgt_kind, "start_line": 1, "end_line": 3}}


def _parsed(file, refs, shadowed=(), errors=0):
    return {file: {"blob_sha": "0" * 40, "refs": refs, "require_shadowed_at": list(shadowed), "parse_errors": errors}}


REQ = {"how": "require", "spec": "../services", "start_line": 2, "end_line": 2, "spec_line": 2}


def test_edge_check_pass_fail_and_inconclusive():
    f = "src/controllers/auth.controller.js"
    ok = J.edge_check(_task(f, 2, "file", "src/services/index.js"), _parsed(f, [REQ]), TREE, READ, "typescript 6.0.3")
    c = ok["checks"][0]
    assert (c["method"], c["result"], c["establishes"]) == ("binding_resolution", "pass", "relationship")
    assert c["validator"]["family"] == "typescript-compiler" and c["validator"]["name"] != "codegraph"
    assert {(x["file"], x["start_line"], x["role"]) for x in c["inputs"]} >= {(f, 2, "site"), ("src/services/index.js", 1, "to_decl")}
    wrong = J.edge_check(_task(f, 2, "file", "src/services/user.service.js"), _parsed(f, [REQ]), TREE, READ, "t")
    assert wrong["checks"][0]["result"] == "fail"  # resolves, but to another file: rejected, never verified
    pkg = dict(REQ, spec="some-package")
    assert J.edge_check(_task(f, 2, "file", "src/services/index.js"), _parsed(f, [pkg]), TREE, READ, "t")["checks"][0]["result"] == "inconclusive"
    assert J.edge_check(_task(f, 5, "file", "src/services/index.js"), _parsed(f, [REQ]), TREE, READ, "t")["checks"][0]["result"] == "inconclusive"
    shadow = J.edge_check(_task(f, 2, "file", "src/services/index.js"), _parsed(f, [REQ], shadowed=[1]), TREE, READ, "t")
    assert shadow["checks"][0]["result"] == "inconclusive" and "local binding" in shadow["checks"][0]["detail"]


def test_package_import_is_presence_only_and_symbols_are_deferred():
    f = "src/app.js"
    r = J.edge_check(_task(f, 1, "import", f, "express"), _parsed(f, [dict(REQ, spec="express", start_line=1, end_line=1)]), TREE, READ, "t")
    assert (r["checks"][0]["method"], r["checks"][0]["result"]) == ("parser_presence", "pass")
    sym = J.edge_check(_task(f, 1, "function", "src/utils/catchAsync.js"), _parsed(f, [REQ | {"start_line": 1, "end_line": 1}]), TREE, READ, "t")
    assert sym["checks"][0]["result"] == "inconclusive" and "v1.1" in sym["checks"][0]["detail"]
    assert J.edge_check(dict(_task(f, 1, "file", "x"), rel_kind="calls"), {}, TREE, READ, "t") is None
