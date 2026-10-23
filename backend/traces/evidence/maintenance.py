"""Idempotent store maintenance run once at API startup (O-9).

Stores created before b37eef2 (F-6) can still hold a failed snapshot row for a commit that does not exist, plus empty
cache directories for it. This removes exactly those: a snapshot in state `failed` whose latest job failed with
`sha_not_found`, that has no claims, and is not `ready`. Its jobs stay, with snapshot_id NULL; only empty cache
directories are removed. Every other row and every non-empty directory is left alone. Each removal is logged."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from traces.evidence.store import Store

log = logging.getLogger("traces.maintenance")


def missing_commit_snapshots(st: Store) -> list[dict[str, Any]]:
    rows = st.db.execute(
        """SELECT s.id, s.repo_id, s.sha FROM snapshots s
           WHERE s.state = 'failed'
             AND NOT EXISTS (SELECT 1 FROM claims c WHERE c.snapshot_id = s.id)
             AND (SELECT j.error_code FROM jobs j WHERE j.snapshot_id = s.id
                  ORDER BY j.created_at DESC, j.id DESC LIMIT 1) = 'sha_not_found'
           ORDER BY s.id""").fetchall()
    return [{"snapshot_id": r[0], "repo_id": r[1], "sha": r[2]} for r in rows]


def _remove_empty_tree(root: Path) -> list[str]:
    """rmdir every empty directory under and including `root`, bottom up; a directory holding a file is kept."""
    removed: list[str] = []
    if not root.is_dir() or root.is_symlink():
        return removed
    for dp, _dns, _fns in os.walk(root, topdown=False, followlinks=False):
        try:
            os.rmdir(dp)
            removed.append(dp)
        except OSError:
            continue
    return removed


def purge_missing_commit_snapshots(st: Store, targets_dir: Path) -> list[dict[str, Any]]:
    out = []
    for s in missing_commit_snapshots(st):
        if not st.drop_unindexed_snapshot(s["snapshot_id"]):
            continue
        repo_dir = Path(targets_dir) / s["repo_id"]
        dirs = _remove_empty_tree(repo_dir / s["sha"])
        try:
            repo_dir.rmdir()  # only when no other snapshot is cached for this repository
            dirs.append(str(repo_dir))
        except OSError:
            pass
        item = {**s, "removed_dirs": dirs}
        log.warning("O-9: removed failed snapshot %s (commit not found, no claims); jobs kept with snapshot_id NULL; "
                    "empty cache dirs removed: %s", s["snapshot_id"], dirs or "none")
        out.append(item)
    return out
