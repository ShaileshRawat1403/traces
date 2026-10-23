"""CommonJS Express patterns that the FastAPI fixture never exercised (found on hagopj13/node-express-boilerplate@179ae84).

A tiny local Express-style package is indexed by the real worker (no network) and read through the real API.
Open findings are xfail(strict=True)."""

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
    "src/utils/catchAsync.js": (
        "const catchAsync = (fn) => (req, res, next) => {\n"
        "  Promise.resolve(fn(req, res, next)).catch((err) => next(err));\n"
        "};\n\nmodule.exports = catchAsync;\n"
    ),
    "src/controllers/auth.controller.js": (
        "const catchAsync = require('../utils/catchAsync');\n"
        "const { userService } = require('../services');\n\n"
        "const register = catchAsync(async (req, res) => {\n"
        "  const user = await userService.createUser(req.body);\n"
        "  res.status(201).send(user);\n"
        "});\n\nmodule.exports = { register };\n"
    ),
    "src/routes/auth.route.js": (
        "const express = require('express');\n"
        "const authController = require('../controllers/auth.controller');\n\n"
        "const router = express.Router();\n\n"
        "router.post('/register', authController.register);\n\n"
        "module.exports = router;\n"
    ),
    "src/app.js": (
        "const express = require('express');\nconst routes = require('./routes/auth.route');\n\n"
        "const app = express();\napp.use('/v1/auth', routes);\n\nmodule.exports = app;\n"
    ),
}


@pytest.fixture(scope="module")
def snap(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    ok, why = toolchain_ready()
    if not ok:
        pytest.skip(why)
    root = tmp_path_factory.mktemp("expressmini")
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
    os.environ.update(
        TRACES_DATA_DIR=str(root / "data"), TRACES_CACHE_DIR=str(root / "cache"), TRACES_ISOLATION="unshare"
    )
    try:
        from traces.core.config import get_settings
        from traces.evidence.index import IndexRun
        from traces.evidence.store import Store, create_job

        ref = LocalRef("github.com", "e2efixture", "expressmini", path=str(src))
        st = Store(get_settings().db_path)
        st.upsert_repo(ref.cache_key, ref.host, ref.owner, ref.name, f"https://github.com/{ref.slug}")
        st.ensure_snapshot(ref.cache_key, sha)
        create_job(st, "ex", ref.cache_key, "index", f"{ref.cache_key}@{sha}")
        res = IndexRun(st, "ex", ref, sha, get_settings()).execute()
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
def client(snap: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    from fastapi.testclient import TestClient

    from traces.api.app import app, get_store
    from traces.evidence.store import Store

    monkeypatch.setenv("TRACES_DATA_DIR", str(snap["root"] / "data"))
    monkeypatch.setenv("TRACES_CACHE_DIR", str(snap["root"] / "cache"))
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


def test_commonjs_requires_and_express_routes_are_recorded(client, snap):
    rels = _claims(client, snap, claim_kind="relationship")
    imports = {(c["from_symbol"], c["to_symbol"]) for c in rels if c["kind"] == "imports"}
    assert any(
        f.startswith("src/controllers/auth.controller.js") and t.startswith("src/services/index.js") for f, t in imports
    ), imports
    routes = client.get(f"{snap['base']}/routes").json()
    assert {(r["method"], r["path"], r["file"], r["line"]) for r in routes} >= {
        ("POST", "/v1/auth/register", "src/routes/auth.route.js", 6)
    }


def test_unvalidated_javascript_claims_are_never_shown_as_verified(client, snap):
    """Without a JavaScript validator nothing may be verified; the overview says so instead of inventing certainty."""
    ov = client.get(f"{snap['base']}/overview").json()
    assert ov["counts"]["verified"] == 0
    assert any(f["kind"] == "unknown" and "verified" in f["text"] for f in ov["start_here"]), ov["start_here"]


@pytest.mark.xfail(
    strict=True,
    reason="FINDING F-10 (Traces seat, validators): JavaScript files have no validator family ('no validator family for "
    "this file language'), so a true CommonJS require or call is never verified. node-express-boilerplate@179ae84: 0 of 712 "
    "static relationships verified, 107 of 107 relative requires correct on manual check; the default graph is empty.",
)
def test_true_commonjs_require_is_verified(client, snap):
    rels = _claims(client, snap, claim_kind="relationship", status="verified")
    assert any(
        c["kind"] == "imports" and c["from_symbol"].startswith("src/controllers/auth.controller.js") for c in rels
    )


@pytest.mark.xfail(
    strict=True,
    reason="FINDING F-9 (Traces seat, views trace_view): a trace reports complete with 0 gaps although the traced symbol has "
    "stored unresolved call references (here userService.createUser through a services/index.js barrel). "
    "node-express-boilerplate@179ae84: trace from register shows 3 steps, 'Complete', and omits 3 unresolved service calls.",
)
def test_trace_with_unresolved_calls_is_not_complete(client, snap):
    unresolved = _claims(client, snap, claim_kind="unresolved_reference")
    assert any("userService.createUser" in c["statement"] for c in unresolved), (
        "precondition: the unresolved call is stored"
    )
    t = client.get(f"{snap['base']}/trace", params={"from": "src/controllers/auth.controller.js::register"}).json()
    assert t["complete"] is False or any(h.get("type") == "gap" for h in t["hops"]), t
