"""Acceptance row 5: a real co-change record, produced by the real worker's history phase, must reach no-key explain
as a history pattern with the caveat, never as a fact and never under code_structure (PR #24).

A local repository whose two files always change together is indexed by IndexRun (no network), then explain is
asked through the real API about those files."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.security.conftest import LocalRef, git, toolchain_ready

CAVEAT = "not evidence of a code dependency"
QUESTIONS = [
    "Which files changed together with alpha.py?",
    "co-change history for beta.py",
    "What changes with alpha.py and beta.py?",
]


@pytest.fixture(scope="module")
def cochange_snapshot(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    ok, why = toolchain_ready()
    if not ok:
        pytest.skip(why)
    root = tmp_path_factory.mktemp("cochange")
    src = root / "src" / "pair"
    (src / "pair").mkdir(parents=True)
    (src / "pair" / "__init__.py").write_text("")
    (src / "pair" / "other.py").write_text("def other():\n    return 0\n")
    git(src, "init", "-q", "-b", "main")
    git(src, "add", "-A")
    git(src, "commit", "-q", "-m", "init")
    # alpha.py and beta.py change together in 7 commits; neither imports or calls the other.
    for i in range(7):
        (src / "pair" / "alpha.py").write_text(f"def alpha():\n    return {i}\n")
        (src / "pair" / "beta.py").write_text(f"def beta():\n    return {i}\n")
        git(src, "add", "-A")
        git(src, "commit", "-q", "-m", f"tune alpha and beta {i}")
    (src / "pair" / "other.py").write_text("def other():\n    return 1\n")
    git(src, "commit", "-qam", "other")
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

        ref = LocalRef("github.com", "e2efixture", "pair", path=str(src))
        st = Store(get_settings().db_path)
        st.upsert_repo(ref.cache_key, ref.host, ref.owner, ref.name, f"https://github.com/{ref.slug}")
        st.ensure_snapshot(ref.cache_key, sha)
        create_job(st, "cc", ref.cache_key, "index", f"{ref.cache_key}@{sha}")
        res = IndexRun(st, "cc", ref, sha, get_settings()).execute()
        st.close()
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    assert "error" not in res, res.get("error")
    return {"root": Path(root), "repo_id": ref.cache_key, "sha": sha}


@pytest.fixture()
def client(cochange_snapshot: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    from fastapi.testclient import TestClient

    from traces.api.app import app, get_store
    from traces.evidence.store import Store

    root = cochange_snapshot["root"]
    monkeypatch.setenv("TRACES_DATA_DIR", str(root / "data"))
    monkeypatch.setenv("TRACES_CACHE_DIR", str(root / "cache"))
    st = Store(root / "data" / "traces.sqlite3")
    app.dependency_overrides[get_store] = lambda: st
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        st.close()


def _snap(s: dict[str, Any]) -> str:
    return f"/api/v1/repos/{s['repo_id']}/snapshots/{s['sha']}"


def _cochange_ids(client: Any, s: dict[str, Any]) -> set[str]:
    r = client.get(f"{_snap(s)}/history/cochange", params={"target": "pair/alpha.py"})
    assert r.status_code == 200, r.text
    items = [i for i in r.json()["items"] if i.get("kind") == "co_changed_with"]
    pairs = {frozenset((i["from_symbol"], i["to_symbol"])) for i in items}
    assert frozenset(("file::pair/alpha.py", "file::pair/beta.py")) in pairs, pairs
    return {i["claim_id"] for i in items}


def test_worker_stores_the_cochange_as_a_history_pattern(client, cochange_snapshot):
    """Precondition: the history phase produced the co-change record for the pair, and it is not verified."""
    r = client.get(f"{_snap(cochange_snapshot)}/history/cochange", params={"target": "pair/alpha.py"})
    items = [i for i in r.json()["items"] if i.get("kind") == "co_changed_with"]
    assert items
    assert all(i["class"] == "history_pattern" and i["status"] != "verified" for i in items), items


@pytest.mark.parametrize("question", QUESTIONS)
def test_cochange_explain_is_a_pattern_with_caveat_never_fact_or_code_structure(client, cochange_snapshot, question):
    ids = _cochange_ids(client, cochange_snapshot)
    r = client.post(f"{_snap(cochange_snapshot)}/explain", json={"question": question})
    assert r.status_code == 200, r.text
    out = r.json()
    cats = out["categories"]
    assert ids & set(cats["history_patterns"]), f"co-change not in history_patterns: {cats}"
    assert not ids & set(cats["code_structure"]), "co-change counted as code structure"
    assert not ids & set(cats.get("inference", [])), "co-change counted as inference"
    citing = [a for a in out["answer"] if ids & set(a["claim_ids"])]
    assert all(a["kind"] != "fact" for a in citing), citing
    # The sentence that states the co-change itself cites only co-change records and carries the caveat.
    own = [a for a in citing if set(a["claim_ids"]) <= ids]
    assert own, citing
    for a in own:
        assert a["kind"] == "interpretation", a
        assert CAVEAT in a["text"], a["text"]
