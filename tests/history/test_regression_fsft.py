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
    churn,
    cochange,
    commit_facts,
    hotspots,
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


def test_users_py_revisions_and_churn(log_off: HistoryLog) -> None:
    """HT1: backend/app/api/routes/users.py has 43 revisions and 1,188 lines of churn (filters off), matching
    git log --follow --no-merges --numstat."""
    res = churn(log_off, ctx=CTX)
    u = next(r for r in res.records if r["from"]["file"] == "backend/app/api/routes/users.py")
    assert (u["metrics"]["revisions"], u["metrics"]["churn"]) == (43, 1188)
    assert (u["metrics"]["added"], u["metrics"]["deleted"]) == (710, 478)
    assert u["status"] == "observed"
    assert len(res.records) == 252
    assert_valid(res.records)


def test_churn_observed_or_explained(log_default: HistoryLog) -> None:
    res = churn(log_default, ctx=CTX)
    assert_valid(res.records)
    for r in res.records:
        assert r["status"] == "observed" or "recount" in r["status_reason"]
    assert sum(r["status"] == "observed" for r in res.records) >= 0.9 * len(res.records)


def test_hotspots_valid(log_default: HistoryLog) -> None:
    res = hotspots(log_default, ctx=CTX)
    assert_valid(res.records)
    assert len(res.records) == 145
    assert all("complexity_proxy" in r["flags"] for r in res.records)


def test_cochange_admin_forms(log_default: HistoryLog) -> None:
    res = cochange(log_default, ctx=CTX)
    assert_valid(res.records)
    r = next(x for x in res.records if (x["from"]["file"], x["to"]["file"]) == (
        "frontend/src/components/Admin/AddUser.tsx", "frontend/src/components/Admin/EditUser.tsx"))
    assert r["qualifier"] == "changed together in 12 of 14 commits"
    assert (r["metrics"]["support"], r["metrics"]["revs_a"], r["metrics"]["revs_b"]) == (12, 12, 14)
    assert r["status"] == "observed" and r["class"] == "history_pattern"
    assert res.report["commits_considered"] == 563
    assert res.report["skipped_commits"] == {"bot": 953, "large_changeset": 21}
    assert len(res.records) == 144


def test_zero_collisions_and_regenerable(fsft_repo: RepoRef, tmp_path_factory: pytest.TempPathFactory) -> None:
    """HT4/HT5: every record from every stage has a unique claim_id; a second run (cold cache, then warm cache)
    reproduces the same canonical hash."""
    cache = tmp_path_factory.mktemp("hcache")

    def run(ctx: RunContext) -> list[dict]:
        log = ingest(fsft_repo, HistoryConfig(), cache_dir=cache)
        out: list[dict] = []
        for fn in (commit_facts, lifecycle, churn, hotspots, cochange):
            out += list(fn(log, ctx=ctx).records)
        return out

    a = run(CTX)
    ids = [r["claim_id"] for r in a]
    assert len(ids) == len(set(ids)) == 6460 + 9 + 235 + 145 + 144
    b = run(RunContext("h-again", "2026-10-23T09:00:00+05:30", CTX.repo, CTX.repo_sha))
    assert canonical_hash(sorted(a, key=lambda r: r["claim_id"])) == canonical_hash(sorted(b, key=lambda r: r["claim_id"]))
