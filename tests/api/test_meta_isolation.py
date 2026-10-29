"""/meta reports the probed isolation (Traces seat on b37eef2): auto without a working unshare is 'unavailable'."""
from __future__ import annotations

import subprocess

import pytest
from fastapi.testclient import TestClient

from traces.api import app as appmod


@pytest.fixture(autouse=True)
def _fresh_cache():
    appmod._ISO_CACHE.clear()
    yield
    appmod._ISO_CACHE.clear()


def _no_unshare(tmp_path, monkeypatch):
    b = tmp_path / "bin"
    b.mkdir()
    (b / "unshare").write_text("#!/bin/sh\necho 'unshare: unshare failed: Operation not permitted' >&2\nexit 1\n")
    (b / "unshare").chmod(0o755)
    monkeypatch.setenv("PATH", f"{b}:{__import__('os').environ['PATH']}")


@pytest.mark.parametrize("mode", ["auto", "unshare"])
def test_meta_says_unavailable_when_the_probe_fails(tmp_path, monkeypatch, mode):
    _no_unshare(tmp_path, monkeypatch)
    monkeypatch.setenv("TRACES_ISOLATION", mode)
    assert TestClient(appmod.app).get("/api/v1/meta").json()["isolation"] == "unavailable"


def test_meta_says_off_only_for_the_explicit_override(monkeypatch):
    monkeypatch.setenv("TRACES_ISOLATION", "off")
    assert TestClient(appmod.app).get("/api/v1/meta").json()["isolation"] == "off"


def test_meta_says_unshare_when_the_probe_passes(monkeypatch):
    if subprocess.run(["unshare", "-rn", "true"], capture_output=True).returncode != 0:
        pytest.skip("unshare -rn is not available on this machine")
    monkeypatch.setenv("TRACES_ISOLATION", "auto")
    assert TestClient(appmod.app).get("/api/v1/meta").json()["isolation"] == "unshare"
