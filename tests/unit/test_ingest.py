"""INGEST: safe pinned clone, caps, failure classification and anonymous HEAD discovery. Uses local synthetic
repositories only (file:// clones); the live GitHub checks run only with TRACES_NETWORK_TESTS=1."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from traces.ingest import remote
from traces.ingest.errors import IngestError
from traces.ingest.fetch import FetchLimits, classify_git_failure, ensure_pinned_checkout
from traces.ingest.remote import HeadProbe, RemoteHead, ls_remote_head
from traces.ingest.urls import RepoRef, parse_repo_url

ENV = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid", "PATH": os.environ["PATH"]}


def g(repo: Path, *a: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *a], env=ENV, check=True, capture_output=True, text=True).stdout


@dataclass(frozen=True)
class LocalRef(RepoRef):
    path: str = ""

    @property
    def clone_url(self) -> str:
        return self.path


@pytest.fixture()
def upstream(tmp_path: Path) -> tuple[Path, str]:
    """A small repo with a symlink pointing outside, a hook-like script and an LFS-style attribute."""
    r = tmp_path / "up"
    r.mkdir()
    g(r, "init", "-q", "-b", "main")
    (r / "a.py").write_text("print('never run')\n")
    (r / "big.bin").write_bytes(os.urandom(300_000))
    (r / ".gitattributes").write_text("*.bin filter=lfs diff=lfs merge=lfs -text\n")
    os.symlink("/etc/passwd", r / "link")
    g(r, "add", "-A")
    g(r, "commit", "-q", "-m", "one")
    (r / "b.py").write_text("x = 1\n")
    g(r, "add", "-A")
    g(r, "commit", "-q", "-m", "two")
    return r, g(r, "rev-parse", "HEAD").strip()


def ref_for(up: Path) -> LocalRef:
    return LocalRef("github.com", "octo", "up", str(up))


def test_pinned_clone_is_safe(upstream, tmp_path):
    up, sha = upstream
    dest = ensure_pinned_checkout(ref_for(up), sha, tmp_path / "c" / "source")
    assert g(dest, "rev-parse", "HEAD").strip() == sha
    link = dest / "link"
    assert link.exists() and not link.is_symlink() and link.read_text() == "/etc/passwd"  # symlink checked out as a plain file
    assert g(dest, "rev-list", "--count", "HEAD").strip() == "2"  # full history for history/SHA~1
    assert not (dest.parent / "source.partial").exists()
    # idempotent: clean checkout at sha is reused (same inode)
    ino = os.stat(dest / "a.py").st_ino
    ensure_pinned_checkout(ref_for(up), sha, dest)
    assert os.stat(dest / "a.py").st_ino == ino


def test_older_sha_and_missing_sha(upstream, tmp_path):
    up, sha = upstream
    first = g(up, "rev-parse", "HEAD~1").strip()
    d = ensure_pinned_checkout(ref_for(up), first, tmp_path / "old")
    assert not (d / "b.py").exists()
    with pytest.raises(IngestError) as e:
        ensure_pinned_checkout(ref_for(up), "0" * 40, tmp_path / "missing")
    assert e.value.code == "sha_not_found"
    assert not (tmp_path / "missing").exists() and not (tmp_path / "missing.partial").exists()


@pytest.mark.parametrize("limits,code", [
    (FetchLimits(max_clone_bytes=50_000), "too_large"),
    (FetchLimits(max_files=2), "too_many_files"),
    (FetchLimits(max_tree_bytes=100_000), "too_large"),
])
def test_caps_fail_cleanly(upstream, tmp_path, limits, code):
    up, sha = upstream
    with pytest.raises(IngestError) as e:
        ensure_pinned_checkout(ref_for(up), sha, tmp_path / "x", limits)
    assert e.value.code == code and e.value.http_status == 413
    assert list(tmp_path.glob("x*")) == []


def test_unreachable_repo_is_classified(tmp_path):
    with pytest.raises(IngestError) as e:
        ensure_pinned_checkout(LocalRef("github.com", "octo", "none", str(tmp_path / "nope")), "1" * 40, tmp_path / "y")
    assert e.value.code in ("fetch_failed", "repo_not_public")
    assert list(tmp_path.glob("y*")) == []


@pytest.mark.parametrize("stderr,code", [
    ("fatal: could not read Username for 'https://github.com': terminal prompts disabled", "repo_not_public"),
    ("remote: Repository not found.\nfatal: Authentication failed for 'https://github.com/a/b.git/'", "repo_not_public"),
    ("fatal: unable to access 'https://github.com/a/b.git/': Could not resolve host: github.com", "upstream_unavailable"),
    ("fatal: unable to access '...': The requested URL returned error: 502", "upstream_unavailable"),
    ("fatal: something odd", "fetch_failed"),
])
def test_classify(stderr, code):
    e = classify_git_failure(stderr, "a/b")
    assert e.code == code
    assert "ghp_" not in str(e.detail)


def test_ls_remote_parse(monkeypatch):
    out = "ref: refs/heads/master\tHEAD\n" + "c" * 40 + "\tHEAD\n"
    monkeypatch.setattr(remote.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, out, ""))
    h = ls_remote_head(parse_repo_url("https://github.com/a/b"))
    assert (h.default_branch, h.sha) == ("master", "c" * 40)
    monkeypatch.setattr(remote.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, "", ""))
    with pytest.raises(IngestError) as e:
        ls_remote_head(parse_repo_url("https://github.com/a/b"))
    assert e.value.code == "repo_empty"


def test_ls_remote_offers_no_credentials(monkeypatch):
    seen = {}

    def fake(cmd, **k):
        seen["cmd"], seen["env"] = cmd, k["env"]
        return subprocess.CompletedProcess(cmd, 128, "", "fatal: could not read Username for 'https://github.com': terminal prompts disabled")

    monkeypatch.setenv("GH_TOKEN", "should-not-leak")
    monkeypatch.setattr(remote.subprocess, "run", fake)
    with pytest.raises(IngestError) as e:
        ls_remote_head(parse_repo_url("https://github.com/a/private"))
    assert e.value.code == "repo_not_public"
    assert "credential.helper=" in seen["cmd"] and seen["env"]["GIT_TERMINAL_PROMPT"] == "0" and seen["env"]["GIT_ASKPASS"] == "/bin/false"
    assert not any(k.startswith(("GH_", "GITHUB_")) or "TOKEN" in k for k in seen["env"])


def test_head_probe_cache_and_rate_limit(monkeypatch):
    calls = []
    monkeypatch.setattr(remote, "ls_remote_head", lambda ref, t: calls.append(ref) or RemoteHead("main", "d" * 40, "t"))
    p = HeadProbe(ttl_s=60, min_interval_s=5)
    ref = parse_repo_url("https://github.com/a/b")
    assert p.head(ref).sha == "d" * 40 and p.head(ref).sha == "d" * 40 and len(calls) == 1  # cached
    assert p.head(ref, max_age_s=0).sha == "d" * 40 and len(calls) == 1  # within min interval: cached value, no call
    p2 = HeadProbe(ttl_s=0, min_interval_s=5)
    monkeypatch.setattr(remote, "ls_remote_head", lambda ref, t: (_ for _ in ()).throw(IngestError("upstream_unavailable", "x")))
    with pytest.raises(IngestError):
        p2.head(ref)
    with pytest.raises(IngestError) as e:
        p2.head(ref)  # second call inside the interval with nothing cached
    assert e.value.code == "rate_limited" and e.value.http_status == 429


live = pytest.mark.skipif(os.environ.get("TRACES_NETWORK_TESTS") != "1", reason="live GitHub checks need TRACES_NETWORK_TESTS=1")


@live
def test_live_public_head():
    h = ls_remote_head(parse_repo_url("https://github.com/fastapi/full-stack-fastapi-template"))
    assert h.default_branch == "master" and len(h.sha) == 40


@live
def test_live_missing_or_private_is_refused():
    with pytest.raises(IngestError) as e:
        ls_remote_head(parse_repo_url("https://github.com/ShaileshRawat1403/this-repo-does-not-exist-traces-v1"))
    assert e.value.code == "repo_not_public"
