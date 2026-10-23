"""Isolation fails closed (D-026). TRACES_ISOLATION=auto never falls back to an unisolated run: when `unshare -rn` does
not work the index job fails with isolation_failed (E_ISOLATION), nothing is fetched and no ready snapshot is stored.
Only the explicit TRACES_ISOLATION=off dev override runs unisolated, and the snapshot then records isolation=off and is
shown as unisolated by the API. No network: the synthetic repository is cloned over file://."""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.unit.test_index_worker import _job, settings_env, synth  # noqa: F401  (pytest fixtures)
from tests.unit.test_ingest import LocalRef
from traces.adapter.codegraph import AdapterError
from traces.api.app import app, get_store
from traces.core.config import get_settings
from traces.evidence.index import IndexRun
from traces.evidence.pipeline import IsolationUnavailable, resolve_isolation
from traces.evidence.store import Store, get_job

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def no_userns(tmp_path, monkeypatch):
    """Simulate a host without user/network namespaces: an `unshare` on PATH that always fails."""
    b = tmp_path / "fakebin"
    b.mkdir()
    (b / "unshare").write_text("#!/bin/sh\necho 'unshare: unshare failed: Operation not permitted' >&2\nexit 1\n")
    (b / "unshare").chmod(0o755)
    monkeypatch.setenv("PATH", f"{b}:{os.environ['PATH']}")


def test_resolve_isolation_modes(no_userns):
    s = get_settings()
    for mode in ("auto", "unshare", "AUTO"):
        with pytest.raises(IsolationUnavailable) as e:
            resolve_isolation(replace(s, isolation=mode))
        assert e.value.code == "E_ISOLATION" and "TRACES_ISOLATION=off" in str(e.value)
    for mode in ("none", "bogus"):
        with pytest.raises(IsolationUnavailable):
            resolve_isolation(replace(s, isolation=mode))
    assert resolve_isolation(replace(s, isolation="off")) == "off"


def test_resolve_isolation_unshare_when_available():
    if subprocess.run(["unshare", "-rn", "true"], capture_output=True).returncode != 0:
        pytest.fail("unshare -rn is required for the test suite (CI enables user namespaces)")
    s = get_settings()
    assert resolve_isolation(replace(s, isolation="auto")) == "unshare"
    assert resolve_isolation(replace(s, isolation="unshare")) == "unshare"


@pytest.mark.parametrize("mode", ["auto", "none"])
def test_index_fails_closed_without_isolation(synth, settings_env, no_userns, monkeypatch, mode):  # noqa: F811
    up, sha = synth
    monkeypatch.setenv("TRACES_ISOLATION", mode)
    s = get_settings()
    st = Store(s.db_path)
    ref = LocalRef("github.com", "octo", f"iso{mode}", str(up))
    _job(st, ref, sha, f"iso-{mode}")
    res = IndexRun(st, f"iso-{mode}", ref, sha, s, history_run=None).execute()
    j = get_job(st, f"iso-{mode}")
    assert j["state"] == "failed" and j["error_code"] == "isolation_failed", (j["error_code"], j["error_detail"])
    assert "E_ISOLATION" in j["error_detail"] and res["error"]["detail"] == {"adapter_code": "E_ISOLATION"}
    snap = st.get_snapshot(f"{ref.cache_key}@{sha}")
    assert snap["state"] == "failed" and snap["isolation"] is None
    assert st.db.execute("SELECT count(*) FROM claims WHERE snapshot_id=?", (snap["id"],)).fetchone()[0] == 0
    assert not (s.targets_dir / ref.cache_key).exists(), "nothing may be fetched before isolation is shown"
    st.close()


def test_off_override_marks_snapshot_unisolated(synth, settings_env, monkeypatch):  # noqa: F811
    up, sha = synth
    monkeypatch.setenv("TRACES_ISOLATION", "off")
    s = get_settings()
    st = Store(s.db_path)
    ref = LocalRef("github.com", "octo", "isooff", str(up))
    _job(st, ref, sha, "iso-off")
    res = IndexRun(st, "iso-off", ref, sha, s, history_run=None).execute()
    j = get_job(st, "iso-off")
    assert j["state"] == "succeeded", (j["error_code"], j["error_detail"])
    assert res["isolation"] == "off"
    assert any(e["level"] == "warning" and "TRACES_ISOLATION=off" in e["message"] for e in j["events"])
    snap = st.get_snapshot(f"{ref.cache_key}@{sha}")
    assert snap["state"] == "ready" and snap["isolation"] == "off"
    ex = json.loads(snap["extractor_json"])
    assert ex["isolation"] == "off" and any("not acceptance evidence" in w for w in ex["adapter_warnings"])
    assert any(c.startswith("4.7 SKIPPED: isolation=off") for c in ex["adapter_checks_passed"])
    app.dependency_overrides[get_store] = lambda: st
    try:
        c = TestClient(app)
        body = c.get(f"/api/v1/repos/{ref.cache_key}/snapshots/{sha}").json()
        assert body["isolation"] == "off" and body["unisolated"] is True
        assert c.get("/api/v1/meta").json()["isolation"] == "off"
    finally:
        app.dependency_overrides.clear()
        st.close()


def test_isolated_snapshot_is_not_unisolated(synth, settings_env, monkeypatch):  # noqa: F811
    up, sha = synth
    monkeypatch.setenv("TRACES_ISOLATION", "auto")
    s = get_settings()
    st = Store(s.db_path)
    ref = LocalRef("github.com", "octo", "isoauto", str(up))
    _job(st, ref, sha, "iso-auto")
    res = IndexRun(st, "iso-auto", ref, sha, s, history_run=None).execute()
    assert res["isolation"] == "unshare" and "error" not in res, res.get("error")
    app.dependency_overrides[get_store] = lambda: st
    try:
        body = TestClient(app).get(f"/api/v1/repos/{ref.cache_key}/snapshots/{sha}").json()
        assert body["isolation"] == "unshare" and body["unisolated"] is False
    finally:
        app.dependency_overrides.clear()
        st.close()


@pytest.mark.parametrize("mode,rc", [("none", 64), ("bogus", 64), ("", 0), ("unshare", 0), ("off", 0)])
def test_sandbox_refuses_unknown_isolation(tmp_path, mode, rc):
    env = {"PATH": os.environ["PATH"], "TRACES_SANDBOX_HOME": str(tmp_path / "h"), "TRACES_TOOLCHAIN_DIR": str(tmp_path),
           "TRACES_ISOLATION": mode}
    p = subprocess.run(["bash", str(ROOT / "workers" / "sandbox.sh"), "true"], env=env, capture_output=True, text=True)
    assert p.returncode == rc, p.stderr
    if rc:
        assert "E_ISOLATION" in p.stderr


def test_adapter_refuses_unknown_isolation(tmp_path):
    from traces.adapter.codegraph import Adapter

    ad = Adapter.__new__(Adapter)
    ad.m = {"env": {"isolation": "none", "netprobe_log": str(tmp_path / "nope.log")}}
    ad.warnings, ad.checks_done = [], []
    with pytest.raises(AdapterError) as e:
        ad.c47()
    assert e.value.code == "E_ISOLATION"
