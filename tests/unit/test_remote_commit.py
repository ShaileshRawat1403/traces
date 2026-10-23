"""Registration-time commit check (remote_commit_exists): an anonymous shallow fetch of one commit object. Local
upstream over file:// (configured like GitHub, which serves any reachable commit and supports filters); the live
GitHub check runs only with TRACES_NETWORK_TESTS=1."""
from __future__ import annotations

import os

import pytest

from tests.unit.test_ingest import LocalRef, g
from traces.ingest.errors import IngestError
from traces.ingest.remote import HeadProbe, remote_commit_exists
from traces.ingest.urls import parse_repo_url


@pytest.fixture()
def up(tmp_path):
    r = tmp_path / "up"
    r.mkdir()
    g(r, "init", "-q", "-b", "main")
    g(r, "config", "uploadpack.allowAnySHA1InWant", "true")
    g(r, "config", "uploadpack.allowFilter", "true")
    (r / "a.py").write_text("x = 1\n")
    g(r, "add", "-A")
    g(r, "commit", "-q", "-m", "one")
    first = g(r, "rev-parse", "HEAD").strip()
    (r / "a.py").write_text("x = 2\n")
    g(r, "commit", "-qam", "two")
    return r, first


def test_existing_non_head_commit(up):
    r, first = up
    assert remote_commit_exists(LocalRef("github.com", "octo", "up", str(r)), first) is True


def test_unknown_commit_is_false(up):
    r, _ = up
    assert remote_commit_exists(LocalRef("github.com", "octo", "up", str(r)), "1" * 40) is False


def test_unreachable_remote_raises(tmp_path):
    with pytest.raises(IngestError):
        remote_commit_exists(LocalRef("github.com", "octo", "gone", str(tmp_path / "missing")), "1" * 40)


def test_probe_caches_positive_answers(up, monkeypatch):
    r, first = up
    p, ref = HeadProbe(), LocalRef("github.com", "octo", "up", str(r))
    assert p.commit_exists(ref, first)
    import traces.ingest.remote as remote

    monkeypatch.setattr(remote, "remote_commit_exists", lambda *a, **k: pytest.fail("cached answer expected"))
    assert p.commit_exists(ref, first)


@pytest.mark.skipif(os.environ.get("TRACES_NETWORK_TESTS") != "1", reason="live GitHub checks need TRACES_NETWORK_TESTS=1")
def test_live_github_commit_check():
    ref = parse_repo_url("https://github.com/pallets/itsdangerous")
    assert remote_commit_exists(ref, "672971d66a2ef9f85151e53283113f33d642dabd") is True
    assert remote_commit_exists(ref, "1234567890123456789012345678901234567890") is False
