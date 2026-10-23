"""A hostile target repository (symlinks out of the tree, odd names, a file:// submodule) is fetched and indexed by the
real index worker, and the source endpoint refuses traversal. Every failure is a visible 4xx with the error envelope."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from .conftest import ODD_FILES, SYMLINKS, UNICODE_FILES, Indexed, index_local, toolchain_ready


def _base(ix: Indexed) -> str:
    return f"/api/v1/repos/{ix.repo_id}/snapshots/{ix.sha}"


def test_index_job_succeeds_on_hostile_repo(indexed_hostile: Indexed):
    assert "error" not in indexed_hostile.result, indexed_hostile.result.get("error")
    assert indexed_hostile.result.get("isolation") == "unshare"


def test_cached_checkout_has_no_symlinks_and_no_submodule(indexed_hostile: Indexed):
    src = indexed_hostile.cache_dir / "targets" / indexed_hostile.repo_id / indexed_hostile.sha / "source"
    assert src.is_dir()
    for dp, dns, fns in os.walk(src):
        for n in dns + fns:
            assert not os.path.islink(os.path.join(dp, n)), f"symlink materialised: {os.path.join(dp, n)}"
    for name, target in SYMLINKS.items():
        p = src / name
        assert p.is_file() and p.read_text() == target, "a symlink must be checked out as a plain file holding its target text"
    assert not any((src / "evil").iterdir()) if (src / "evil").exists() else True, "submodule must not be fetched"


def test_claims_stay_inside_the_tree(indexed_hostile: Indexed, hostile_client):
    page = hostile_client.get(f"{_base(indexed_hostile)}/claims", params={"limit": 500, "include_rejected": True}).json()
    assert page["items"], "the worker should have stored claims for app/ and web/"
    tracked = set(ODD_FILES) | set(SYMLINKS)
    for c in page["items"]:
        rec = c.get("record") or c
        for end in ("from", "to"):
            f = (rec.get(end) or {}).get("file")
            if f:
                assert not f.startswith("/") and ".." not in Path(f).parts, f
                assert f in tracked or any(f.startswith(t) for t in ("app/", "web/")), f


@pytest.mark.parametrize("name", ["has space.py", "-rf.py", "a:b.py", "..hidden.py", "app/main.py"])
def test_odd_but_legal_paths_are_readable(indexed_hostile: Indexed, hostile_client, name):
    r = hostile_client.get(f"{_base(indexed_hostile)}/source", params={"path": name})
    assert r.status_code == 200, r.text
    assert r.json()["lines"] == ODD_FILES[name].splitlines()


@pytest.mark.parametrize("name", list(SYMLINKS))
def test_symlink_source_shows_link_text_not_target(indexed_hostile: Indexed, hostile_client, name):
    r = hostile_client.get(f"{_base(indexed_hostile)}/source", params={"path": name})
    assert r.status_code == 200, r.text
    assert r.json()["lines"] == [SYMLINKS[name]]
    assert "root:" not in r.text


TRAVERSAL = {
    "dotdot": "../../../../etc/passwd",
    "dotdot_inside": "app/../../etc/passwd",
    "absolute": "/etc/passwd",
    "home": "~/.ssh/id_rsa",
    "backslash": "..\\..\\etc\\passwd",
    "nul": "app/main.py\x00.png",
    "newline": "app/main.py\nother",
    "empty": "",
}


@pytest.mark.parametrize("path", TRAVERSAL.values(), ids=TRAVERSAL.keys())
def test_traversal_refused(indexed_hostile: Indexed, hostile_client, path):
    r = hostile_client.get(f"{_base(indexed_hostile)}/source", params={"path": path})
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] in ("invalid_request",)
    assert "root:" not in r.text


RAW = {
    "encoded_dotdot": "%2e%2e%2f%2e%2e%2fetc%2fpasswd",
    "encoded_dotdot_upper": "%2E%2E/%2E%2E/etc/passwd",
    "encoded_nul": "app%2fmain.py%00",
    "encoded_absolute": "%2fetc%2fpasswd",
}


@pytest.mark.parametrize("raw", RAW.values(), ids=RAW.keys())
def test_encoded_traversal_refused(indexed_hostile: Indexed, hostile_client, raw):
    r = hostile_client.get(f"{_base(indexed_hostile)}/source?path={raw}")
    assert r.status_code == 422, r.text
    assert "root:" not in r.text


@pytest.mark.parametrize("path", ["%252e%252e/%252e%252e/etc/passwd", "dirlink/passwd", "app", "evil/passwd", "nope.py"])
def test_not_in_tree_is_404(indexed_hostile: Indexed, hostile_client, path):
    r = hostile_client.get(f"{_base(indexed_hostile)}/source", params={"path": path})
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found", r.text
    assert "root:" not in r.text


def test_line_range_limits(indexed_hostile: Indexed, hostile_client):
    b = f"{_base(indexed_hostile)}/source"
    assert hostile_client.get(b, params={"path": "app/main.py", "start": 0}).status_code == 422
    assert hostile_client.get(b, params={"path": "app/main.py", "start": 99}).status_code == 422
    assert hostile_client.get(b, params={"path": "app/main.py", "start": 3, "end": 2}).status_code == 422
    assert hostile_client.get(b, params={"path": "app/main.py", "start": 1, "end": 10**9}).status_code == 422


@pytest.mark.parametrize("repo_id", ["..%2f..%2fetc", "../../etc", "github.com__secfixture__hostile%00"])
def test_repo_id_traversal_is_404(indexed_hostile: Indexed, hostile_client, repo_id):
    r = hostile_client.get(f"/api/v1/repos/{repo_id}/snapshots/{indexed_hostile.sha}/source", params={"path": "app/main.py"})
    assert r.status_code in (404, 422), r.text
    assert "root:" not in r.text


def test_bad_snapshot_sha_is_422(indexed_hostile: Indexed, hostile_client):
    r = hostile_client.get(f"/api/v1/repos/{indexed_hostile.repo_id}/snapshots/HEAD/source", params={"path": "app/main.py"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_sha"


def test_non_ascii_path_indexes(tmp_path, monkeypatch):
    ok, why = toolchain_ready()
    if not ok:
        pytest.skip(why)
    monkeypatch.setenv("TRACES_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TRACES_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("TRACES_ISOLATION", "unshare")
    ix = index_local(tmp_path, tmp_path / "data", tmp_path / "cache", extra=UNICODE_FILES, name="unicode", job="uni")
    assert "error" not in ix.result, ix.result.get("error")


def test_non_ascii_path_failure_is_safe_and_visible(tmp_path, monkeypatch):
    """Until F-1 is fixed the job must fail closed with a stable code and a failed snapshot, never a partial index."""
    ok, why = toolchain_ready()
    if not ok:
        pytest.skip(why)
    from traces.evidence.store import Store, get_job

    monkeypatch.setenv("TRACES_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TRACES_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("TRACES_ISOLATION", "unshare")
    ix = index_local(tmp_path, tmp_path / "data", tmp_path / "cache", extra=UNICODE_FILES, name="unicode2", job="uni2")
    if "error" not in ix.result:
        return  # F-1 fixed: nothing to check here
    st = Store(tmp_path / "data" / "traces.sqlite3")
    j = get_job(st, "uni2") or {}
    snap = st.get_snapshot(f"{ix.repo_id}@{ix.sha}") or {}
    n = st.db.execute("SELECT count(*) FROM claims WHERE snapshot_id=?", (snap.get("id"),)).fetchone()[0]
    st.close()
    assert j["state"] == "failed" and j["error_code"] == "adapter_failed"
    assert snap["state"] == "failed" and n == 0


def test_option_like_path_is_not_an_option(indexed_hostile: Indexed, hostile_client, tmp_path):
    out = tmp_path / "x"
    r = hostile_client.get(f"{_base(indexed_hostile)}/source", params={"path": f"--output={out}"})
    assert r.status_code in (404, 422) and r.json()["error"]["code"] in ("not_found", "invalid_request")
    assert not out.exists()


def test_oversized_repo_job_fails_visibly(tmp_path, monkeypatch):
    """Through the index worker and the jobs API: a file-count cap breach is a failed job with code too_many_files."""
    ok, why = toolchain_ready()
    if not ok:
        pytest.skip(why)
    from fastapi.testclient import TestClient

    from traces.api.app import app, get_store
    from traces.evidence.store import Store

    monkeypatch.setenv("TRACES_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TRACES_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("TRACES_ISOLATION", "unshare")
    monkeypatch.setenv("TRACES_MAX_FILES", "3")
    ix = index_local(tmp_path, tmp_path / "data", tmp_path / "cache", name="toomany", job="big")
    assert ix.result["error"]["code"] == "too_many_files"
    st = Store(tmp_path / "data" / "traces.sqlite3")
    app.dependency_overrides[get_store] = lambda: st
    try:
        c = TestClient(app)
        j = c.get("/api/v1/jobs/big").json()
        assert j["state"] == "failed" and j["error"]["code"] == "too_many_files" and "cap" in j["error"]["message"]
        snap = c.get(f"/api/v1/repos/{ix.repo_id}/snapshots/{ix.sha}").json()
        assert snap["state"] == "failed"
        r = c.get(f"/api/v1/repos/{ix.repo_id}/snapshots/{ix.sha}/overview")
        assert r.status_code < 500
    finally:
        app.dependency_overrides.clear()
        st.close()
    assert not (tmp_path / "cache" / "targets" / ix.repo_id / ix.sha / "source").exists()
