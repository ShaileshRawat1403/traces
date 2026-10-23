"""Oversized repositories, slow clones, private repos, upstream failures and HEAD rate limits fail safely and visibly.

A `git` shim on PATH (conftest.fake_git) stands in for the remote: no network is used. The shim logs argv and the NAMES
of the environment variables it received, so the tests can check that no credential reaches git."""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from traces.api.app import app, get_head_probe, get_store
from traces.evidence.store import Store
from traces.ingest.errors import IngestError
from traces.ingest.fetch import FetchLimits, ensure_pinned_checkout
from traces.ingest.remote import HeadProbe
from traces.ingest.urls import RepoRef

from .conftest import LocalRef, build_hostile_repo, git

GH = RepoRef("github.com", "octo", "demo")
SHA = "a" * 40
GROW = ('dest="${@: -1}"; mkdir -p "$dest"; for i in $(seq 1 600); do head -c 1048576 /dev/urandom > "$dest/blob$i"; sleep 0.05; done; '
        'exit 0')


def _no_partial(dest: Path) -> None:
    assert not dest.exists(), "a failed fetch must not leave a checkout"
    assert not dest.with_name(dest.name + ".partial").exists(), "a failed fetch must remove the partial clone"


def test_clone_timeout_kills_and_cleans(tmp_path, fake_git):
    fake_git(clone="exec sleep 60")
    dest = tmp_path / "t" / "source"
    t0 = time.monotonic()
    with pytest.raises(IngestError) as e:
        ensure_pinned_checkout(GH, SHA, dest, FetchLimits(clone_timeout_s=1))
    assert e.value.code == "fetch_timeout" and e.value.http_status == 504
    assert time.monotonic() - t0 < 10
    _no_partial(dest)


def test_clone_size_cap_kills_while_cloning(tmp_path, fake_git):
    fake_git(clone=GROW)
    dest = tmp_path / "t" / "source"
    with pytest.raises(IngestError) as e:
        ensure_pinned_checkout(GH, SHA, dest, FetchLimits(max_clone_bytes=5 * 1024 * 1024))
    assert e.value.code == "too_large" and e.value.http_status == 413
    _no_partial(dest)


def test_tree_caps_before_checkout(tmp_path):
    src, sha = build_hostile_repo(tmp_path / "src")
    ref = LocalRef("github.com", "secfixture", "hostile", path=str(src))
    for limits, code in ((FetchLimits(max_files=3), "too_many_files"), (FetchLimits(max_tree_bytes=10), "too_large")):
        dest = tmp_path / code / "source"
        with pytest.raises(IngestError) as e:
            ensure_pinned_checkout(ref, sha, dest, limits)
        assert e.value.code == code and e.value.http_status == 413 and e.value.detail
        _no_partial(dest)


def test_fast_small_clone_over_cap_is_still_refused(tmp_path):
    """A clone that finishes before the 0.5 s size poll must still be refused if the cloned data is over the cap.
    Here the tree cap is left at its default, so only the clone-size cap can refuse it."""
    src = tmp_path / "big"
    src.mkdir()
    (src / "blob.bin").write_bytes(__import__("os").urandom(3 * 1024 * 1024))
    git(src, "init", "-q", "-b", "main")
    git(src, "add", "-A")
    git(src, "commit", "-q", "-m", "big")
    sha = git(src, "rev-parse", "HEAD").strip()
    ref = LocalRef("github.com", "secfixture", "big", path=str(src))
    dest = tmp_path / "out" / "source"
    with pytest.raises(IngestError) as e:
        ensure_pinned_checkout(ref, sha, dest, FetchLimits(max_clone_bytes=1024 * 1024))
    assert e.value.code == "too_large"
    _no_partial(dest)


def test_missing_commit_is_sha_not_found(tmp_path):
    src, _ = build_hostile_repo(tmp_path / "src")
    ref = LocalRef("github.com", "secfixture", "hostile", path=str(src))
    dest = tmp_path / "x" / "source"
    with pytest.raises(IngestError) as e:
        ensure_pinned_checkout(ref, "b" * 40, dest)
    assert e.value.code == "sha_not_found"
    _no_partial(dest)


@pytest.mark.parametrize(("stderr", "code", "status"), [
    ("fatal: could not read Username for 'https://github.com': terminal prompts disabled", "repo_not_public", 422),
    ("remote: Repository not found.\nfatal: repository 'https://github.com/octo/demo.git/' not found", "repo_not_public", 422),
    ("fatal: unable to access 'https://github.com/octo/demo.git/': Could not resolve host: github.com", "upstream_unavailable", 502),
    ("fatal: something odd", "fetch_failed", 502),
])
def test_clone_failures_are_classified(tmp_path, fake_git, stderr, code, status):
    fake_git(clone=f"printf '%s\\n' {stderr!r} >&2; exit 128")
    dest = tmp_path / "c" / "source"
    with pytest.raises(IngestError) as e:
        ensure_pinned_checkout(GH, SHA, dest)
    assert e.value.code == code and e.value.http_status == status
    _no_partial(dest)


def test_git_never_sees_credentials_or_prompts(tmp_path, fake_git, monkeypatch):
    log = fake_git(ls_remote="printf 'ref: refs/heads/main\\tHEAD\\n%s\\tHEAD\\n' " + "c" * 40 + "; exit 0")
    for k in ("GH_TOKEN", "GITHUB_TOKEN", "GH_TOKEN_TRACES", "OPENAI_API_KEY", "GIT_ASKPASS", "SSH_AUTH_SOCK"):
        monkeypatch.setenv(k, "dummy-value-not-a-secret")
    h = HeadProbe(min_interval_s=0).head(GH)
    assert h.sha == "c" * 40 and h.default_branch == "main"
    text = log.read_text()
    env_line = next(line for line in text.splitlines() if line.startswith("ENV "))
    names = set(env_line.split()[1:])
    assert not names & {"GH_TOKEN", "GITHUB_TOKEN", "GH_TOKEN_TRACES", "OPENAI_API_KEY", "SSH_AUTH_SOCK"}
    assert {"GIT_TERMINAL_PROMPT", "GIT_CONFIG_NOSYSTEM"} <= names
    assert "credential.helper=" in text and "protocol.allow=never" in text and "dummy-value" not in text


# ------------------------------------------------------------------------------------------------ through the API
@pytest.fixture()
def api_real_probe():
    st = Store(":memory:")
    probe = HeadProbe(ttl_s=60, min_interval_s=30, timeout_s=1)
    app.dependency_overrides[get_store] = lambda: st
    app.dependency_overrides[get_head_probe] = lambda: probe
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_api_ls_remote_timeout_is_504(api_real_probe, fake_git):
    fake_git(ls_remote="exec sleep 30")
    r = api_real_probe.post("/api/v1/repos", json={"url": "https://github.com/octo/slow"})
    assert r.status_code == 504 and r.json()["error"]["code"] == "fetch_timeout"


def test_api_private_repo_is_422_without_prompt(api_real_probe, fake_git):
    fake_git(ls_remote="echo 'remote: Repository not found.' >&2; exit 128")
    r = api_real_probe.post("/api/v1/repos", json={"url": "https://github.com/octo/private"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "repo_not_public"
    assert "credentials" in r.json()["error"]["message"]


def test_api_rate_limit_is_429_with_retry_after(api_real_probe, fake_git):
    fake_git(ls_remote="echo 'fatal: Could not resolve host: github.com' >&2; exit 128")
    r1 = api_real_probe.post("/api/v1/repos", json={"url": "https://github.com/octo/flaky"})
    assert r1.status_code == 502 and r1.json()["error"]["code"] == "upstream_unavailable"
    r2 = api_real_probe.post("/api/v1/repos", json={"url": "https://github.com/octo/flaky"})
    assert r2.status_code == 429 and r2.json()["error"]["code"] == "rate_limited"
    assert int(r2.headers["Retry-After"]) >= 1
