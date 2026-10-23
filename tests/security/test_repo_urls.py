"""Bad repository URLs are refused before any network call, with a visible 422 invalid_repo_url (charter s5, s7)."""
from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from traces.api.app import app, get_head_probe, get_store
from traces.evidence.store import Store
from traces.ingest.remote import RemoteHead
from traces.ingest.urls import InvalidRepoUrl, parse_repo_url

BAD_URLS = {
    "non_github_host": "https://gitlab.com/a/b",
    "lookalike_host": "https://github.com.evil.example/a/b",
    "userinfo_host_confusion": "https://github.com@evil.example/a/b",
    "http_plain": "http://github.com/a/b",
    "ssh_scheme": "ssh://git@github.com/a/b.git",
    "scp_like_ssh": "git@github.com:a/b.git",
    "git_protocol": "git://github.com/a/b.git",
    "file_scheme": "file:///etc/passwd",
    "file_scheme_github_path": "file://github.com/a/b",
    "credentials_user_pass": "https://user:hunter2@github.com/a/b",
    "credentials_token": "https://ghp_abcdefabcdefabcdefabcdefabcdefabcdef@github.com/a/b",
    "ip_literal_v4": "https://140.82.112.3/a/b",
    "ip_literal_v6": "https://[::1]/a/b",
    "localhost": "https://localhost/a/b",
    "loopback_ip": "https://127.0.0.1/a/b",
    "explicit_port": "https://github.com:8443/a/b",
    "query_string": "https://github.com/a/b?ref=main",
    "fragment": "https://github.com/a/b#main",
    "extra_path": "https://github.com/a/b/tree/main",
    "dot_dot_name": "https://github.com/a/..",
    "encoded_dot_dot": "https://github.com/a/%2e%2e",
    "dot_name": "https://github.com/a/.git",
    "newline_injection": "https://github.com/a/b\n--upload-pack=touch /tmp/x",
    "option_injection_owner": "https://github.com/-u/b",
    "nul_byte": "https://github.com/a/b\x00",
    "overlong": "https://github.com/a/" + "b" * 400,
    "empty": "",
    "javascript": "javascript:alert(1)",
}


class CountingProbe:
    def __init__(self) -> None:
        self.calls = 0

    def head(self, ref: Any, *, max_age_s: float | None = None) -> RemoteHead:
        self.calls += 1
        return RemoteHead("main", "a" * 40, "2026-10-23T12:00:00+05:30")


@pytest.fixture()
def api():
    st, probe = Store(":memory:"), CountingProbe()
    app.dependency_overrides[get_store] = lambda: st
    app.dependency_overrides[get_head_probe] = lambda: probe
    try:
        yield TestClient(app), probe, st
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("url", BAD_URLS.values(), ids=BAD_URLS.keys())
def test_bad_url_refused_before_network(api, url):
    client, probe, st = api
    r = client.post("/api/v1/repos", json={"url": url})
    assert r.status_code == 422, r.text
    err = r.json()["error"]
    assert err["code"] == "invalid_repo_url" and err["message"]
    assert probe.calls == 0, "a rejected URL must never reach ls-remote"
    assert st.list_repos() == []
    # Credentials in a refused URL are never echoed back.
    assert "hunter2" not in r.text and "ghp_abc" not in r.text


@pytest.mark.parametrize("url", BAD_URLS.values(), ids=BAD_URLS.keys())
def test_parser_refuses(url):
    with pytest.raises(InvalidRepoUrl):
        parse_repo_url(url)


def test_non_string_url_is_invalid_request(api):
    client, probe, _ = api
    for body in ({"url": 123}, {"url": None}, {}, {"url": "https://github.com/a/b", "token": "x"}):
        r = client.post("/api/v1/repos", json=body)
        assert r.status_code == 422 and r.json()["error"]["code"] in ("invalid_request", "invalid_repo_url"), (body, r.text)
    assert probe.calls == 0


def test_bad_sha_refused(api):
    client, probe, _ = api
    for sha in ("HEAD", "main", "abc123", "A" * 40, "../" + "a" * 37, "-" + "a" * 39):
        r = client.post("/api/v1/repos", json={"url": "https://github.com/a/b", "sha": sha})
        assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_sha", (sha, r.text)
    assert probe.calls == 0


def test_valid_url_normalizes_to_https_clone(api):
    client, probe, _ = api
    r = client.post("/api/v1/repos", json={"url": "https://github.com/Octo/Demo.git"})
    assert r.status_code == 201 and r.json()["id"] == "github.com__octo__demo" and probe.calls == 1
    assert parse_repo_url("https://github.com/Octo/Demo").clone_url == "https://github.com/Octo/Demo.git"
