"""F-10, F-9 and O-7 end to end on a tiny CommonJS + ES module Express app, indexed by the real worker (no network).
JavaScript imports that resolve to the right file reach verified (D-030). JavaScript calls never do. A trace whose step
has unresolved outgoing calls is not complete."""
from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.security.conftest import LocalRef, git, toolchain_ready

FILES = {
    "package.json": '{"name": "mini", "version": "1.0.0", "dependencies": {"express": "^4.18.0"}}\n',
    "src/services/user.service.js": "const createUser = async (body) => ({ id: 1, ...body });\n\nmodule.exports = { createUser };\n",
    "src/services/index.js": "module.exports.userService = require('./user.service');\n",
    "src/utils/catchAsync.js": "const catchAsync = (fn) => (req, res, next) => {\n  Promise.resolve(fn(req, res, next)).catch(next);\n};\n\nmodule.exports = catchAsync;\n",
    "src/controllers/auth.controller.js": (
        "const catchAsync = require('../utils/catchAsync');\nconst { userService } = require('../services');\n\n"
        "const register = catchAsync(async (req, res) => {\n  const user = await userService.createUser(req.body);\n"
        "  res.status(201).send(user);\n});\n\nmodule.exports = { register };\n"),
    "src/routes/auth.route.js": (
        "const express = require('express');\nconst authController = require('../controllers/auth.controller');\n\n"
        "const router = express.Router();\n\nrouter.post('/register', authController.register);\n\nmodule.exports = router;\n"),
    "src/app.js": (
        "const express = require('express');\nconst routes = require('./routes/auth.route');\nconst limiter = require('./utils/catchAsync');\n\n"
        "const app = express();\napp.use('/v1/auth', limiter);\napp.use('/v1/auth', routes);\n\nmodule.exports = app;\n"),
    "src/esm/math.mjs": "export function add(a, b) {\n  return a + b;\n}\n",
    "src/esm/main.mjs": "import { add } from './math.mjs';\n\nexport const three = () => add(1, 2);\n",
}


@pytest.fixture(scope="module")
def snap(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    ok, why = toolchain_ready()
    if not ok:
        pytest.skip(why)
    root = tmp_path_factory.mktemp("jsmini")
    src = root / "src" / "mini"
    for name, text in FILES.items():
        p = src / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    git(src, "init", "-q", "-b", "main")
    git(src, "add", "-A")
    git(src, "commit", "-q", "-m", "mini")
    sha = git(src, "rev-parse", "HEAD").strip()
    keys = ("TRACES_DATA_DIR", "TRACES_CACHE_DIR", "TRACES_ISOLATION")
    old = {k: os.environ.get(k) for k in keys}
    os.environ.update(TRACES_DATA_DIR=str(root / "data"), TRACES_CACHE_DIR=str(root / "cache"), TRACES_ISOLATION="unshare")
    try:
        from traces.core.config import get_settings
        from traces.evidence.index import IndexRun
        from traces.evidence.store import Store, create_job

        ref = LocalRef("github.com", "unitfixture", "jsmini", path=str(src))
        st = Store(get_settings().db_path)
        st.upsert_repo(ref.cache_key, ref.host, ref.owner, ref.name, f"https://github.com/{ref.slug}")
        st.ensure_snapshot(ref.cache_key, sha)
        create_job(st, "js", ref.cache_key, "index", f"{ref.cache_key}@{sha}")
        res = IndexRun(st, "js", ref, sha, get_settings()).execute()
        st.close()
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    assert "error" not in res, res.get("error")
    return {"root": Path(root), "base": f"/api/v1/repos/{ref.cache_key}/snapshots/{sha}"}


@pytest.fixture()
def client(snap: dict[str, Any]) -> Iterator[Any]:
    from fastapi.testclient import TestClient

    from traces.api.app import app, get_store
    from traces.evidence.store import Store

    st = Store(snap["root"] / "data" / "traces.sqlite3")
    app.dependency_overrides[get_store] = lambda: st
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        st.close()


def _claims(client: Any, snap: dict[str, Any], **params: Any) -> list[dict[str, Any]]:
    r = client.get(f"{snap['base']}/claims", params={"limit": 500, **params})
    assert r.status_code == 200, r.text
    return r.json()["items"]


def test_true_requires_and_es_imports_are_verified(client, snap):
    rels = _claims(client, snap, claim_kind="relationship")
    imports = {(c["from_symbol"].split("::")[0], c["to_symbol"].split("::")[0]): c["status"] for c in rels if c["kind"] == "imports"}
    for pair in [("src/controllers/auth.controller.js", "src/services/index.js"),  # directory index
                 ("src/controllers/auth.controller.js", "src/utils/catchAsync.js"),
                 ("src/services/index.js", "src/services/user.service.js"), ("src/app.js", "src/routes/auth.route.js"),
                 ("src/routes/auth.route.js", "src/controllers/auth.controller.js")]:
        assert imports.get(pair) == "verified", (pair, imports)
    es = {c["to_symbol"]: c["status"] for c in rels if c["kind"] == "imports" and c["from_symbol"].startswith("src/esm/main.mjs")}
    file_level = {k: v for k, v in es.items() if "::" not in k or k.endswith("::src/esm/math.mjs")}
    assert file_level and set(file_level.values()) == {"verified"}, es  # the ES import of the file
    assert all(v == "unvalidated" for k, v in es.items() if k.endswith("::add")), es  # a named binding: v1.1


def test_javascript_calls_and_references_are_never_verified(client, snap):
    rels = _claims(client, snap, claim_kind="relationship", status="verified")
    assert rels and all(c["kind"] == "imports" for c in rels), [(c["kind"], c["from_symbol"]) for c in rels]
    detail = client.get(f"{snap['base']}/claims/{rels[0]['claim_id']}").json()
    fams = {c["validator"]["family"] for c in detail["checks"] if c["independent"]}
    assert fams == {"typescript-compiler"}
    assert client.get("/api/v1/meta").json()["validators"]["javascript"].endswith("imports only (D-030)")


def test_trace_with_unresolved_calls_is_not_complete(client, snap):
    t = client.get(f"{snap['base']}/trace", params={"from": "src/controllers/auth.controller.js::register"}).json()
    assert t["complete"] is False, t
    gaps = [h for h in t["hops"] if h["type"] == "gap"]
    assert gaps and "userService.createUser" in gaps[0]["unresolved_calls"], gaps
    assert "unresolved" in gaps[0]["reason"] and gaps[0]["label"] == "inferred"
    assert "require" not in gaps[0]["unresolved_calls"]
    assert t["incomplete_reasons"]
    assert [h["index"] for h in t["hops"]] == list(range(len(t["hops"])))


def test_middleware_mount_is_a_mount_not_an_unknown_route(client, snap):
    routes = client.get(f"{snap['base']}/routes").json()
    mounts = [r for r in routes if r["method"] == "USE"]
    assert mounts and all("mount" in r["flags"] and "method_not_recorded" not in r["flags"] for r in mounts), routes
    assert ("POST", "/v1/auth/register") in {(r["method"], r["path"]) for r in routes}
