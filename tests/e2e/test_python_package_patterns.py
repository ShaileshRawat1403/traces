"""Python library patterns that the FastAPI fixture never exercised (found on pallets/itsdangerous and pallets/markupsafe).

A tiny local package is indexed by the real worker (no network). Open findings are xfail(strict=True)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from tests.security.conftest import GIT_ENV, LocalRef, git, toolchain_ready

FILES = {
    "src/pkg/__init__.py": "from .enc import want_bytes as want_bytes\nfrom .signer import Signer as Signer\n",
    "src/pkg/enc.py": "def want_bytes(s):\n    return s if isinstance(s, bytes) else s.encode()\n",
    "src/pkg/signer.py": (
        "import typing as t\n\nfrom .enc import want_bytes\n\n\nclass Signer:\n"
        "    @t.overload\n    def unsign(self, v: str) -> bytes: ...\n\n"
        "    @t.overload\n    def unsign(self, v: bytes) -> bytes: ...\n\n"
        "    def unsign(self, v):\n        return want_bytes(v)\n\n"
        "    def validate(self, v):\n        return bool(self.unsign(v))\n"
    ),
}


@pytest.fixture(scope="module")
def indexed(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    ok, why = toolchain_ready()
    if not ok:
        pytest.skip(why)
    root = tmp_path_factory.mktemp("pypkg")
    src = root / "src" / "pypkg"
    for name, text in FILES.items():
        p = src / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    git(src, "init", "-q", "-b", "main")
    git(src, "add", "-A")
    git(src, "commit", "-q", "-m", "pkg")
    sha = git(src, "rev-parse", "HEAD").strip()
    old = {k: os.environ.get(k) for k in ("TRACES_DATA_DIR", "TRACES_CACHE_DIR", "TRACES_ISOLATION")}
    os.environ.update(TRACES_DATA_DIR=str(root / "data"), TRACES_CACHE_DIR=str(root / "cache"), TRACES_ISOLATION="unshare")
    try:
        from traces.core.config import get_settings
        from traces.evidence.index import IndexRun
        from traces.evidence.store import Store, create_job

        ref = LocalRef("github.com", "e2efixture", "pypkg", path=str(src))
        st = Store(get_settings().db_path)
        st.upsert_repo(ref.cache_key, ref.host, ref.owner, ref.name, f"https://github.com/{ref.slug}")
        st.ensure_snapshot(ref.cache_key, sha)
        create_job(st, "pk", ref.cache_key, "index", f"{ref.cache_key}@{sha}")
        res = IndexRun(st, "pk", ref, sha, get_settings()).execute()
        recs = list(st.iter_claims(f"{ref.cache_key}@{sha}"))
        st.close()
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    assert "error" not in res, res.get("error")
    return {"recs": recs, "env": GIT_ENV, "root": Path(root)}


def _rels(recs: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [r for r in recs if r.get("claim_kind") == "relationship" and r.get("relationship_kind") == kind
            and r.get("evidence_scope") == "static"]


def test_relative_imports_are_extracted(indexed):
    imps = _rels(indexed["recs"], "imports")
    rel = [r for r in imps if r["to"]["symbol"].split("::")[-1].startswith(".")]
    assert rel, "CodeGraph should report the relative imports"


# Regression guard for F-4, fixed in PR #27.
def test_relative_imports_not_rejected(indexed):
    rel = [r for r in _rels(indexed["recs"], "imports") if r["to"]["symbol"].split("::")[-1].startswith(".")]
    assert rel and all(r["status"] != "rejected" for r in rel), [(r["statement"], r["status"]) for r in rel]


# Regression guard for F-5, fixed in PR #27.
def test_overload_call_to_implementation_not_rejected(indexed):
    calls = [r for r in _rels(indexed["recs"], "calls") if r["to"]["symbol"].endswith("Signer::unsign")
             and r["from"]["symbol"].endswith("Signer::validate")]
    assert calls, "CodeGraph should report validate -> unsign"
    assert all(r["status"] != "rejected" for r in calls), [(r["statement"], r["status"], r["to"]) for r in calls]
