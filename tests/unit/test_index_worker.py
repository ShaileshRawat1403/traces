"""INDEX worker: resource caps, credential stripping, deterministic snapshot facts, safe failure, and one real end-to-end
index of a small synthetic repository (CodeGraph in the sandbox, adapter, validators, store). No network: the
synthetic repository is cloned over file://."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.unit.test_ingest import ENV, LocalRef, g
from traces.core.config import get_settings
from traces.evidence import components as comp
from traces.evidence.index import IndexFailure, IndexRun, clean_env, run_watched
from traces.evidence.store import Store, create_job, get_job
from traces.history.interface import HistoryResult


def test_watchdog_timeout_and_memory(tmp_path):
    with pytest.raises(IndexFailure) as e:
        run_watched([sys.executable, "-c", "import time; time.sleep(30)"], dict(os.environ), tmp_path / "l", timeout_s=1, max_rss_mb=4096, step="t")
    assert e.value.code == "index_timeout"
    hog = "x = bytearray(400 * 1024 * 1024); import time; [x.__setitem__(i, 1) for i in range(0, len(x), 4096)]; time.sleep(30)"
    with pytest.raises(IndexFailure) as e:
        run_watched([sys.executable, "-c", hog], dict(os.environ), tmp_path / "l", timeout_s=60, max_rss_mb=150, step="m")
    assert e.value.code == "memory_limit" and e.value.detail["peak_rss_mb"] >= 150
    assert run_watched([sys.executable, "-c", "pass"], dict(os.environ), tmp_path / "l", timeout_s=30, max_rss_mb=4096, step="ok") == 0


def test_clean_env_strips_credentials():
    env = clean_env({"PATH": "/bin", "GH_TOKEN_TRACES": "x", "GITHUB_TOKEN": "x", "MY_API_KEY": "x", "AWS_REGION": "x", "OPENAI_X": "x", "HOME": "/h"})
    assert env == {"PATH": "/bin", "HOME": "/h"}


def test_component_rules():
    assert comp.component_key("README.md") == "(root)"
    assert comp.component_key("backend/app/api/routes/items.py") == "backend/app/api"
    assert comp.component_key("frontend/src/client/sdk.gen.ts") == "frontend/src/client"
    assert comp.component_key("src/index.ts") == "src"
    assert comp.layer_of("backend/app/api/routes/items.py") == "api"
    assert comp.layer_of("frontend/src/components/A.tsx") == "frontend"
    assert comp.layer_of("backend/tests/test_x.py") == "tests"
    assert comp.layer_of("backend/app/models.py") == "data"
    assert comp.layer_of(".github/workflows/ci.yml") == "infra"
    assert comp.layer_of("docs/x.md") == "docs"
    cs, _ = comp.build_components(["a/x.py", "a/y.py", "b/t.test.ts"])
    m1, m2 = comp.component_map("0" * 40, cs), comp.component_map("0" * 40, list(reversed(cs)))
    assert m1.digest == m2.digest and m1.component_of("a/y.py") == "component::a"


@pytest.fixture()
def synth(tmp_path) -> tuple[Path, str]:
    r = tmp_path / "synth"
    r.mkdir()
    g(r, "init", "-q", "-b", "main")
    (r / "app").mkdir()
    (r / "app" / "util.py").write_text("def helper(x):\n    return x + 1\n")
    (r / "app" / "main.py").write_text("from app.util import helper\n\n\ndef run():\n    return helper(1)\n")
    (r / "web").mkdir()
    (r / "web" / "lib.ts").write_text("export function add(a: number, b: number): number {\n  return a + b\n}\n")
    (r / "web" / "index.ts").write_text("import { add } from './lib'\n\nexport const three = add(1, 2)\n")
    (r / "openapi-ts.config.ts").write_text("export default { input: 'x.json', output: './web/client' }\n")
    (r / "package.json").write_text('{"name": "s", "devDependencies": {"vite": "1.0.0"}}\n')
    (r / "pyproject.toml").write_text('[project]\nname = "s"\ndependencies = ["fastapi>=0.1"]\n')
    (r / "hook.sh").write_text("#!/bin/sh\ntouch /tmp/traces-should-never-run\n")
    g(r, "add", "-A")
    g(r, "commit", "-q", "-m", "init")
    return r, g(r, "rev-parse", "HEAD").strip()


def _job(st: Store, ref, sha: str, jid: str) -> None:
    st.upsert_repo(ref.cache_key, ref.host, ref.owner, ref.name, f"https://github.com/{ref.slug}")
    st.ensure_snapshot(ref.cache_key, sha)
    create_job(st, jid, ref.cache_key, "index", f"{ref.cache_key}@{sha}")


@pytest.fixture()
def settings_env(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACES_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TRACES_CACHE_DIR", str(tmp_path / "cache"))
    s = get_settings()
    if not s.codegraph_bin.exists():
        pytest.fail(f"toolchain not installed in {s.toolchain_dir} (run: make toolchain)")
    return s


def test_end_to_end_index_of_synthetic_repo(synth, settings_env, tmp_path):
    up, sha = synth
    s = settings_env
    st = Store(s.db_path)
    ref = LocalRef("github.com", "octo", "synth", str(up))
    _job(st, ref, sha, "e2e")
    seen = {}

    def fake_history(repo, config, **kw):
        seen["repo"], seen["components"], seen["ev"], seen["kw"] = repo, kw["components"], kw["evidence_sets"], kw
        return HistoryResult(records=[], report={})

    res = IndexRun(st, "e2e", ref, sha, s, history_run=fake_history).execute()
    j = get_job(st, "e2e")
    assert j["state"] == "succeeded", (j["error_code"], j["error_detail"], res.get("error"))
    snap = st.get_snapshot(f"{ref.cache_key}@{sha}")
    assert snap["state"] == "ready" and snap["indexed_at"]
    stats = res["stats"]
    assert stats["codegraph_edges"]["total"] > 0 and stats["injected"] == {} and res["fixture"] is None
    assert stats["history"] == {"state": "done", "records": 0, "complete": True}
    ev = seen["ev"][sha]
    assert ev.sha == sha and ev.schema_version == "traces-evidence/0.4" and len(ev.records) > 0
    assert all(r["evidence_scope"] == "static" for r in ev.records)
    assert seen["kw"]["max_milestones"] == 8 and seen["kw"]["run_id"] == "idx-e2e"
    assert seen["repo"].sha == sha and seen["components"].component_of("app/main.py") == "component::app"
    import json
    assert json.loads(snap["generated_paths_json"]) == ["web/client"]
    assert {"FastAPI", "Vite"} <= set(json.loads(snap["frameworks_json"]))
    assert {c["component_id"] for c in st.list_components(snap["id"])} >= {"component::app", "component::web"}
    # rejected never verified; missing_location never verified (store-level invariant)
    bad = st.db.execute("SELECT count(*) FROM claims WHERE snapshot_id=? AND status='verified' AND (label!='verified')", (snap["id"],)).fetchone()[0]
    assert bad == 0
    # missing_location is never verified: it carries no verified label, it never jumps straight to verified or observed
    # (only location_recovery, with recovered locations, moves it to unvalidated first), and nothing verified lacks a location
    seen_ml = 0
    for (rj,) in st.db.execute("SELECT record_json FROM claims WHERE snapshot_id=?", (snap["id"],)):
        rec = json.loads(rj)
        if rec["status"] == "missing_location":
            assert rec["label"] != "verified", rec["claim_id"]
        if rec["status"] == "verified":
            assert rec.get("locations"), f"verified without a location: {rec['claim_id']}"
        for h in rec.get("status_history") or []:
            if h.get("from") == "missing_location":
                seen_ml += 1
                assert h["to"] == "unvalidated" and h["by"] == "location_recovery" and h["check_ids"], (rec["claim_id"], h)
            assert not (h.get("to") == "verified" and h.get("from") == "missing_location"), rec["claim_id"]
    assert seen_ml > 0, "the synthetic repo should exercise location recovery at least once"
    assert not Path("/tmp/traces-should-never-run").exists()
    assert not (s.runs_dir / "idx-e2e" / "real").exists()  # throwaway working copy removed
    assert (s.runs_dir / "idx-e2e" / "netprobe.log").read_text().count("PROBE_SUMMARY a=pass b=pass c=pass d=pass") == 1
    st.close()


def test_history_absent_is_skipped_and_failure_is_safe(synth, settings_env):
    up, sha = synth
    s = settings_env
    st = Store(s.db_path)
    ref = LocalRef("github.com", "octo", "synth2", str(up))
    _job(st, ref, sha, "h1")
    res = IndexRun(st, "h1", ref, sha, s, history_run=None).execute()
    assert res["stats"]["history"]["state"] == "skipped" and get_job(st, "h1")["state"] == "succeeded"
    assert any(e["level"] == "warning" and "history skipped" in e["message"] for e in get_job(st, "h1")["events"])
    # history crashing never discards the stored static evidence
    _job(st, ref, "0" * 40, "h2")  # unknown commit -> sha_not_found at fetch
    res = IndexRun(st, "h2", ref, "0" * 40, s).execute()
    j = get_job(st, "h2")
    assert j["state"] == "failed" and j["error_code"] == "sha_not_found"
    # F-6: a commit that does not exist leaves no failed snapshot row and no empty cache directory behind
    assert j["snapshot_id"] is None and st.get_snapshot(f"{ref.cache_key}@{'0' * 40}") is None
    assert not (s.targets_dir / ref.cache_key / ("0" * 40)).exists()
    assert st.get_snapshot(f"{ref.cache_key}@{sha}")["state"] == "ready"  # the real snapshot is untouched
    st.close()


def test_history_crash_keeps_static_evidence(synth, settings_env):
    up, sha = synth
    s = settings_env
    st = Store(s.db_path)
    ref = LocalRef("github.com", "octo", "synth3", str(up))
    _job(st, ref, sha, "h3")

    def boom(*a, **k):
        raise RuntimeError("history exploded")

    res = IndexRun(st, "h3", ref, sha, s, history_run=boom).execute()
    assert get_job(st, "h3")["state"] == "succeeded" and res["stats"]["history"]["state"] == "failed"
    assert res["stats"]["records"] > 0
    st.close()


@pytest.mark.parametrize("kind", ["not_implemented", "partial"])
def test_history_stub_and_partial(synth, settings_env, kind):
    up, sha = synth
    s = settings_env
    st = Store(s.db_path)
    ref = LocalRef("github.com", "octo", f"synth-{kind}", str(up))
    _job(st, ref, sha, kind)

    def hist(repo, config, **kw):
        if kind == "not_implemented":
            raise NotImplementedError("history runner: stub")
        r = HistoryResult(records=[], report={"complete": False, "incomplete_reason": "budget: 600 s"})
        return r

    res = IndexRun(st, kind, ref, sha, s, history_run=hist).execute()
    h = res["stats"]["history"]
    assert get_job(st, kind)["state"] == "succeeded"
    if kind == "not_implemented":
        assert h["state"] == "skipped" and "stub" in h["reason"]
    else:
        assert h["state"] == "completed_with_warnings" and h["complete"] is False and "budget" in h["reason"]
    st.close()


def test_private_or_missing_repo_fails_cleanly(settings_env, tmp_path):
    s = settings_env
    st = Store(s.db_path)
    ref = LocalRef("github.com", "octo", "gone", str(tmp_path / "does-not-exist"))
    _job(st, ref, "1" * 40, "p1")
    IndexRun(st, "p1", ref, "1" * 40, s).execute()
    j = get_job(st, "p1")
    assert j["state"] == "failed" and j["error_code"] in ("fetch_failed", "repo_not_public") and j["phase"] == "failed"
    st.close()


_ = (subprocess, ENV)
