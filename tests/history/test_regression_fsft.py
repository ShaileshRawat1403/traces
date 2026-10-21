"""Regressions on fastapi/full-stack-fastapi-template@b1125d8 (contract section 18, HT1 to HT5).

Needs a local full-history clone (TRACES_HISTORY_FSFT_REPO). Skips with the reason when it is absent. The module only
reads Git objects from that clone; nothing in it is executed."""

from __future__ import annotations

import pytest

from traces.history import (
    HistoryConfig,
    HistoryLog,
    RepoRef,
    RunContext,
    canonical_hash,
    commit_facts,
    ingest,
    lifecycle,
)

from ._schema import assert_valid
from .conftest import NO_FILTERS

CTX = RunContext("h-regress", "2026-10-21T12:00:00+05:30", "fastapi/full-stack-fastapi-template",
                 "b1125d8839482cb7bbae603ddc6d0081bf87532e")


@pytest.fixture(scope="module")
def log_default(fsft_repo: RepoRef) -> HistoryLog:
    return ingest(fsft_repo, HistoryConfig())


@pytest.fixture(scope="module")
def log_off(fsft_repo: RepoRef) -> HistoryLog:
    return ingest(fsft_repo, NO_FILTERS)


def test_ingest_shape(log_default: HistoryLog) -> None:
    assert len(log_default.commits) == 1537
    assert len(log_default.first_parent) == 1537
    assert sum(c.is_merge for c in log_default.commits) == 0
    assert log_default.mailmap_blob is None


def test_lifecycle_replay_equals_ls_tree(log_default: HistoryLog) -> None:
    res = lifecycle(log_default, ctx=CTX)
    rc = res.report["replay_check"]
    assert rc["replayed_files"] == rc["ls_tree_files"] == 252
    assert rc["missing_in_replay"] == [] and rc["extra_in_replay"] == []


def test_bulk_moves(log_default: HistoryLog) -> None:
    res = lifecycle(log_default, ctx=CTX)
    moves = {(r["from"]["file"], r["to"]["file"]): r for r in res.records if r["relationship_kind"] == "prefix_moved"}
    assert len(moves) == 9
    src = moves[("src", ".")]
    assert src["metrics"]["files"] == 247 and src["citations"][0]["commit"].startswith("8558cf0")
    assert moves[("new-frontend", "frontend")]["metrics"]["files"] == 96
    assert all(r["status"] == "observed" for r in moves.values())
    assert_valid(res.records)


def test_commit_facts_valid_unique_and_deterministic(log_off: HistoryLog, fsft_repo: RepoRef) -> None:
    a = commit_facts(log_off, ctx=CTX)
    assert len(a.records) == 6460
    assert assert_valid(a.records) == 6460
    assert len({r["claim_id"] for r in a.records}) == len(a.records)
    assert all(r["status"] == "observed" for r in a.records)
    b = commit_facts(ingest(fsft_repo, NO_FILTERS), ctx=RunContext("h-other", "2026-10-22T08:00:00+05:30",
                                                                  CTX.repo, CTX.repo_sha))
    assert canonical_hash(a.records) == canonical_hash(b.records)
