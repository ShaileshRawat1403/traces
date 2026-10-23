"""Python library patterns the FastAPI fixture never exercised (Lab findings F-4 and F-5 on pallets/itsdangerous):
relative imports and calls into @typing.overload'ed methods must not be rejected. A tiny local package is indexed by
the real worker over file:// (no network). Lab's own repro lives in tests/e2e/test_python_package_patterns.py."""
from __future__ import annotations

from typing import Any

import pytest

from tests.unit.test_index_worker import _job, settings_env  # noqa: F401  (pytest fixture)
from tests.unit.test_ingest import LocalRef, g
from traces.evidence.index import IndexRun
from traces.evidence.store import Store

FILES = {
    "src/pkg/__init__.py": "from .enc import want_bytes as want_bytes\nfrom .signer import Signer as Signer\n",
    "src/pkg/enc.py": "def want_bytes(s):\n    return s if isinstance(s, bytes) else s.encode()\n",
    "src/pkg/sub/__init__.py": "from .. import enc\nfrom ..enc import want_bytes\n",
    "src/pkg/signer.py": (
        "import typing as t\nfrom typing import overload\n\nfrom .enc import want_bytes\n\n\nclass Signer:\n"
        "    @t.overload\n    def unsign(self, v: str) -> bytes: ...\n\n"
        "    @t.overload\n    def unsign(self, v: bytes) -> bytes: ...\n\n"
        "    def unsign(self, v):\n        return want_bytes(v)\n\n"
        "    @overload\n    def sign(self, v: str) -> bytes: ...\n\n"
        "    @overload\n    def sign(self, v: bytes) -> bytes: ...\n\n"
        "    def sign(self, v):\n        return want_bytes(v)\n\n"
        "    def validate(self, v):\n        return bool(self.unsign(v)) and bool(self.sign(v))\n"
    ),
}


@pytest.fixture()
def indexed(tmp_path, settings_env) -> list[dict[str, Any]]:  # noqa: F811
    src = tmp_path / "pypkg"
    for name, text in FILES.items():
        p = src / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    g(src, "init", "-q", "-b", "main")
    g(src, "add", "-A")
    g(src, "commit", "-q", "-m", "pkg")
    sha = g(src, "rev-parse", "HEAD").strip()
    st = Store(settings_env.db_path)
    ref = LocalRef("github.com", "octo", "pypkg", str(src))
    _job(st, ref, sha, "pk")
    res = IndexRun(st, "pk", ref, sha, settings_env, history_run=None).execute()
    assert "error" not in res, res.get("error")
    recs = list(st.iter_claims(f"{ref.cache_key}@{sha}"))
    st.close()
    return recs


def _rels(recs: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [r for r in recs if r.get("claim_kind") == "relationship" and r.get("relationship_kind") == kind
            and r.get("evidence_scope") == "static"]


def test_relative_imports_are_not_rejected(indexed):
    rel = [r for r in _rels(indexed, "imports") if r["to"]["symbol"].split("::")[-1].startswith(".")]
    assert rel, "CodeGraph should report the relative imports"
    assert all(r["status"] != "rejected" for r in rel), [(r["statement"], r["status"]) for r in rel]
    assert any(r["status"] in ("verified", "observed") for r in rel)
    bad = [(r["claim_kind"], r.get("relationship_kind") or r.get("node_kind"), r["statement"], [c.get("detail") for c in r.get("checks", []) if c.get("result") == "fail"]) for r in indexed if r.get("status") == "rejected"]
    assert not bad, bad


@pytest.mark.parametrize("method", ["unsign", "sign"])
def test_call_into_overloaded_method_is_not_rejected(indexed, method):
    calls = [r for r in _rels(indexed, "calls") if r["to"]["symbol"].endswith(f"Signer::{method}")
             and r["from"]["symbol"].endswith("Signer::validate")]
    assert calls, f"CodeGraph should report validate -> {method}"
    assert all(r["status"] != "rejected" for r in calls), [(r["statement"], r["status"], r["to"]) for r in calls]
