"""Missing API keys: no-key mode stays useful and keys cannot be submitted. Worker resource caps fail visibly."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from traces.evidence.index import IndexFailure, clean_env, run_watched

from .conftest import Indexed

PROVIDER_VARS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "XAI_API_KEY", "GEMINI_API_KEY", "GH_TOKEN", "GITHUB_TOKEN")


def test_no_key_explain_answers_with_citations(indexed_hostile: Indexed, hostile_client, monkeypatch):
    for k in PROVIDER_VARS:
        monkeypatch.delenv(k, raising=False)
    b = f"/api/v1/repos/{indexed_hostile.repo_id}/snapshots/{indexed_hostile.sha}"
    r = hostile_client.post(f"{b}/explain", json={"question": "What does app/main.py call?"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("citations"), "no-key explain must cite stored claims"
    for c in body["citations"]:
        assert c["claim_id"].startswith("c_") and c["status"] in ("verified", "observed", "unvalidated", "missing_location")
    g = hostile_client.get(f"{b}/graph").json()
    assert g.get("nodes") and g.get("edges") is not None


def test_chat_bundle_without_key_is_a_bundle_not_a_call(indexed_hostile: Indexed, hostile_client):
    b = f"/api/v1/repos/{indexed_hostile.repo_id}/snapshots/{indexed_hostile.sha}"
    r = hostile_client.post(f"{b}/chat/bundle", json={"question": "Explain app/main.py"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("outbound_manifest"), "the bundle must list what would be sent"
    assert "sk-" not in r.text and "api_key" not in r.text.lower()


@pytest.mark.parametrize("field", ["api_key", "provider_key", "openai_api_key", "authorization"])
def test_keys_cannot_be_submitted(indexed_hostile: Indexed, hostile_client, field):
    b = f"/api/v1/repos/{indexed_hostile.repo_id}/snapshots/{indexed_hostile.sha}"
    for ep in ("explain", "chat/bundle"):
        r = hostile_client.post(f"{b}/{ep}", json={"question": "x", field: "sk-test-not-a-real-key"})
        assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request", r.text


def test_submitted_key_not_echoed(indexed_hostile: Indexed, hostile_client):
    b = f"/api/v1/repos/{indexed_hostile.repo_id}/snapshots/{indexed_hostile.sha}"
    r = hostile_client.post(f"{b}/explain", json={"question": "x", "api_key": "sk-test-not-a-real-key"})
    assert r.status_code == 422
    assert "sk-test-not-a-real-key" not in r.text


def test_oversized_question_refused(indexed_hostile: Indexed, hostile_client):
    b = f"/api/v1/repos/{indexed_hostile.repo_id}/snapshots/{indexed_hostile.sha}"
    r = hostile_client.post(f"{b}/explain", json={"question": "x" * 5000})
    assert r.status_code == 422


def test_worker_env_strips_credentials():
    env = clean_env({"PATH": "/usr/bin", "GH_TOKEN": "x", "GH_TOKEN_TRACES": "x", "OPENAI_API_KEY": "x", "AWS_ACCESS_KEY_ID": "x",
                     "MY_SECRET": "x", "DB_PASSWORD": "x", "XAI_API_KEY": "x", "HOME": "/h"})
    assert set(env) == {"PATH", "HOME"}


def test_step_timeout_kills_process_tree(tmp_path: Path):
    t0 = time.monotonic()
    with pytest.raises(IndexFailure) as e:
        run_watched(["bash", "-c", "sleep 60 & sleep 60"], {"PATH": "/usr/bin:/bin"}, tmp_path / "log", timeout_s=1, max_rss_mb=6144,
                    step="indexing")
    assert e.value.code == "index_timeout" and e.value.detail == {"step": "indexing"}
    assert time.monotonic() - t0 < 10
    assert "exit=-9" in (tmp_path / "log").read_text()


def test_step_memory_cap_kills(tmp_path: Path):
    code = "import time; b = bytearray(400 * 1024 * 1024); b[::4096] = b'x' * len(b[::4096]); time.sleep(30)"
    with pytest.raises(IndexFailure) as e:
        run_watched([sys.executable, "-c", code], {"PATH": "/usr/bin:/bin"}, tmp_path / "log", timeout_s=60, max_rss_mb=100, step="indexing")
    assert e.value.code == "memory_limit" and e.value.detail["peak_rss_mb"] > 100
