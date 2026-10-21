"""Regressions on fastapi/full-stack-fastapi-template@b1125d8 (contract section 18, HT1 to HT5).

Needs a local full-history clone (TRACES_HISTORY_FSFT_REPO). Skips with the reason when it is absent. The module only
reads Git objects from that clone; nothing in it is executed."""

from __future__ import annotations

import pytest

from traces.history import (
    FilterSpec,
    HistoryConfig,
    HistoryError,
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
from traces.history.impact import history_impact
from traces.history.manifests import manifest_changes
from traces.history.milestones import milestone_records, select_milestones, snapshot_compare
from traces.history.pr_context import link_prs, pr_context
from traces.history.records import recompute_claim_id
from traces.history.reverts import reverts

from ._schema import assert_valid
from .conftest import NO_FILTERS

FSFT_PR_LINKS = (752, 752)  # linked PR numbers, linked commits
IMPACT_N = 12  # history_impact candidates for Admin/AddUser.tsx
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
        for fn in (commit_facts, lifecycle, churn, hotspots, cochange, manifest_changes, reverts):
            out += list(fn(log, ctx=ctx).records)
        ms = select_milestones(log)
        out += list(milestone_records(log, ms, ctx=ctx).records)
        out += list(snapshot_compare(log, ms[0].sha, ms[-1].sha, ctx=ctx).records)
        co = [r for r in out if r.get("relationship_kind") == "co_changed_with"]
        out += list(history_impact("frontend/src/components/Admin/AddUser.tsx", co).by_source["history:co_change"])
        return out

    a = run(CTX)
    ids = [r["claim_id"] for r in a]
    assert sum(recompute_claim_id(r) != r["claim_id"] for r in a) == 0
    assert len(ids) == len(set(ids))
    assert len(ids) == 6460 + 9 + 235 + 145 + 144 + 653 + 54 + 8 + 416 + IMPACT_N
    b = run(RunContext("h-again", "2026-10-23T09:00:00+05:30", CTX.repo, CTX.repo_sha))
    assert canonical_hash(sorted(a, key=lambda r: r["claim_id"])) == canonical_hash(sorted(b, key=lambda r: r["claim_id"]))


def test_ht14_sqlmodel_added_at_558_before_559(log_default: HistoryLog) -> None:
    res = manifest_changes(log_default, ctx=CTX)
    assert_valid(res.records)
    assert res.report["unparseable"] == []
    assert len(res.records) == 653 and res.report["events_by_kind"] == {
        "dependency_added": 198, "dependency_version_changed": 334, "dependency_removed": 121}
    assert all(r["status"] == "observed" for r in res.records)
    added = [r for r in res.records if r["relationship_kind"] == "dependency_added"
             and r["provenance_raw"]["name"] == "sqlmodel"]
    first = min(added, key=lambda r: log_default.by_sha[r["citations"][0]["commit"]].committer_time)
    c558 = log_default.by_sha[first["citations"][0]["commit"]]
    assert c558.sha.startswith("e4877b7a") and "(#558)" in c558.subject
    c559 = next(c for c in log_default.commits if "(#559)" in c.subject)
    assert c558.committer_time < c559.committer_time
    assert first["to"]["symbol"] == "dep::pypi:backend/pyproject.toml:poetry:sqlmodel"


def test_reverts_and_quick_deletes(log_default: HistoryLog, fsft_repo: RepoRef) -> None:
    res = reverts(log_default, ctx=CTX)
    assert_valid(res.records)
    rv = [r for r in res.records if r["relationship_kind"] == "reverts"]
    assert len(rv) == 3 and all(r["status"] == "unvalidated" for r in rv)
    assert res.report["skipped"] == {"bot": 1} and res.report["unresolved"] == []
    qd = [r for r in res.records if r["relationship_kind"] == "deleted_soon_after_add"]
    assert len(qd) == 51 and all(r["status"] == "observed" for r in qd)
    # Lab C false revert: the Dependabot body quoting an upstream changelog resolves to nothing when bots are kept
    off = reverts(ingest(fsft_repo, HistoryConfig(filters=FilterSpec(exclude_bots_from_patterns=False))), ctx=CTX)
    assert [u["commit"][:8] for u in off.report["unresolved"]] == ["eb0b2c2f"]


def test_ht22_milestones(log_default: HistoryLog) -> None:
    a = select_milestones(log_default)
    assert a == select_milestones(log_default)
    shas = [m.sha for m in a]
    assert len(a) == 8 and shas[0].startswith("7f8bfc8f") and shas[-1] == CTX.repo_sha
    assert all(m.sha in set(log_default.first_parent) and m.reasons for m in a)
    assert any(s.startswith("8558cf00") for s in shas) and any(s.startswith("455de4d9") for s in shas)
    assert len(select_milestones(log_default, max_milestones=20)) == 20
    with pytest.raises(HistoryError):
        select_milestones(log_default, max_milestones=21)
    recs = milestone_records(log_default, a, ctx=CTX)
    assert_valid(recs.records)
    assert all(r["status"] == "observed" for r in recs.records)
    sc = snapshot_compare(log_default, shas[0], CTX.repo_sha, ctx=CTX)
    assert_valid(sc.records)
    assert (sc.report["files_at_base"], sc.report["files_at_head"]) == (198, 252)
    assert all(r["status"] == "observed" for r in sc.records)


def test_ht23_impact_adduser(log_default: HistoryLog) -> None:
    co = cochange(log_default, ctx=CTX).records
    res = history_impact("frontend/src/components/Admin/AddUser.tsx", co)
    recs = res.by_source["history:co_change"]
    assert_valid(recs)
    assert set(res.by_source) == {"history:co_change", "history:alias"} and res.known_gaps
    assert recs and all(r["status"] == "unvalidated" and r["relationship_kind"] == "history_impact_candidate"
                        for r in recs)
    assert len(recs) == IMPACT_N
    edit = next(r for r in recs if r["to"]["file"] == "frontend/src/components/Admin/EditUser.tsx")
    assert edit["qualifier"] == "history signal: changed together in 12 of 14 commits"
    assert history_impact("frontend/src/components/Admin/AddUser.tsx", co).by_source == res.by_source


def test_pr_context_links_and_offline(log_default: HistoryLog) -> None:
    from .test_pr_context import OfflineFake, cached

    links = link_prs(log_default)
    assert (len(links), sum(len(v) for v in links.values())) == FSFT_PR_LINKS
    (sha558,) = links[558]
    assert sha558.startswith("e4877b7a")
    none = pr_context(log_default, None, ctx=CTX)
    assert none.records == [] and none.report["pr_context"] == "none"
    fake = OfflineFake({558: cached(558, sha558, "Fixture body for an offline smoke test.", [])})
    res = pr_context(log_default, fake, ctx=CTX)
    assert_valid(res.records)
    assert len(res.records) == 2 and all(r["status"] == "observed" for r in res.records)
    assert len(res.report["prs_missing"]) == len(links) - 1


def test_run_end_to_end_totals(fsft_repo: RepoRef, tmp_path_factory: pytest.TempPathFactory) -> None:
    """run() on fsft. 8402 = the 8136 of the all-stage collision test, minus 12 impact candidates (impact is a
    query-time API, not a run stage), minus 416 first..head snapshot records, plus 694 records from the 7
    consecutive milestone pairs that run() compares (section 8.11)."""
    from traces.history.milestones import milestone_records as _mr
    from traces.history.records import finalize
    from traces.history.runner import run

    res = run(fsft_repo, HistoryConfig(), cache_dir=tmp_path_factory.mktemp("rcache"),
              run_id=CTX.run_id, at=CTX.at)
    rep = res.report
    st = {s["stage"]: (s["status"], s["reason"], s["records"]) for s in rep["stages"]}
    assert rep["complete"] is True and rep["records"] == len(res.records) == 8402
    assert {k: v[2] for k, v in st.items() if v[2]} == {
        "commit_facts": 6460, "lifecycle": 9, "churn": 235, "hotspots": 145, "cochange_file": 144,
        "manifests": 653, "reverts": 54, "milestones": 8, "snapshot_compare": 694}
    assert st["milestones"][:2] == ("truncated", "milestone_cap")
    log = ingest(fsft_repo, HistoryConfig())
    ms = select_milestones(log)
    assert [m["sha"] for m in rep["milestones"]] == [m.sha for m in ms]
    direct: list[dict] = []
    for fn in (commit_facts, lifecycle, churn, hotspots, cochange, manifest_changes, reverts):
        direct += list(fn(log, ctx=CTX).records)
    direct += list(_mr(log, ms, ctx=CTX).records)
    for a, b in zip(ms, ms[1:], strict=False):
        direct += list(snapshot_compare(log, a.sha, b.sha, ctx=CTX).records)
    assert rep["records_digest"] == canonical_hash(finalize(direct))
    v = rep["volatile"]
    assert v["finalize_s"] > 0 and v["elapsed_s"] >= v["finalize_s"]
