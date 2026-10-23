"""O-9: the startup cleanup removes only failed sha_not_found snapshots without claims, and only empty cache dirs."""
from __future__ import annotations

import logging
import time
from pathlib import Path

from tests.api.test_views import rec
from traces.evidence.maintenance import purge_missing_commit_snapshots
from traces.evidence.store import Store, create_job, update_job

MISSING = "0" * 39 + "1"


def _snap(st: Store, rid: str, sha: str, state: str, code: str | None, jid: str) -> str:
    st.upsert_repo(rid, "github.com", "o", rid, f"https://github.com/o/{rid}")
    sid = st.upsert_snapshot(rid, sha, state)
    create_job(st, jid, rid, "index", sid)
    if code:
        update_job(st, jid, state="failed", phase="failed", error_code=code, message=code)
    time.sleep(0.002)
    return sid


def test_removes_only_missing_commit_rows_and_empty_dirs(tmp_path: Path, caplog):
    st = Store(":memory:")
    targets = tmp_path / "targets"
    gone = _snap(st, "github.com__pallets__markupsafe", MISSING, "failed", "sha_not_found", "j1")
    (targets / "github.com__pallets__markupsafe" / MISSING / "source.partial").mkdir(parents=True)  # empty leftovers
    timeout = _snap(st, "github.com__o__slow", "a" * 40, "failed", "fetch_timeout", "j2")
    with_claims = _snap(st, "github.com__o__claims", "b" * 40, "failed", "sha_not_found", "j3")
    st.put_claims(with_claims, [rec()])
    ready = _snap(st, "github.com__o__ready", "c" * 40, "ready", None, "j4")
    full = _snap(st, "github.com__o__full", "d" * 40, "failed", "sha_not_found", "j5")
    keep_file = targets / "github.com__o__full" / ("d" * 40) / "note.txt"
    keep_file.parent.mkdir(parents=True)
    keep_file.write_text("not empty")
    # a later, different failure on the same snapshot: the latest job decides, so this one stays
    later = _snap(st, "github.com__o__later", "e" * 40, "failed", "sha_not_found", "j6")
    create_job(st, "j7", "github.com__o__later", "index", later)
    update_job(st, "j7", state="failed", phase="failed", error_code="fetch_failed", message="x")

    with caplog.at_level(logging.WARNING, logger="traces.maintenance"):
        out = purge_missing_commit_snapshots(st, targets)
    assert {o["snapshot_id"] for o in out} == {gone, full}
    left = {r[0] for r in st.db.execute("SELECT id FROM snapshots")}
    assert left == {timeout, with_claims, ready, later}
    assert not (targets / "github.com__pallets__markupsafe").exists()  # empty dirs, repo dir included
    assert keep_file.exists()  # a directory holding a file is never removed
    jobs = dict(st.db.execute("SELECT id, snapshot_id FROM jobs").fetchall())
    assert jobs["j1"] is None and jobs["j5"] is None and jobs["j2"] == timeout  # job history stays
    assert any(gone in r.getMessage() and "O-9" in r.getMessage() for r in caplog.records)
    # idempotent: a second run changes nothing
    assert purge_missing_commit_snapshots(st, targets) == []
    assert {r[0] for r in st.db.execute("SELECT id FROM snapshots")} == left
