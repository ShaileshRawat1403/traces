"""Records, citations and claim_id (contract section 7; HT4, HT5, HT19)."""

from __future__ import annotations

import pytest

from traces.history import HistoryError, RunContext, claim_id
from traces.history.model import Change, Commit
from traces.history.records import citation, ep_commit, ep_file, ep_path, finalize, make_record, parameters

from ._schema import assert_valid, schema_errors

CTX = RunContext("h-1", "2026-10-21T15:30:00+05:30", "o/r", "b" * 40)
CTX2 = RunContext("h-2", "2026-10-22T09:00:00+05:30", "o/r", "b" * 40)
C = Commit("1" * 40, ("2" * 40,), "A", "a@x", 1, 1, "msg", (
    Change("M", "src/a.py", None, None, "3" * 40, "4" * 40, "100644", "100644", 1, 0),))


def _rec(ctx: RunContext = CTX, params: dict | None = None, check: dict | None = None, **kw):  # type: ignore[no-untyped-def]
    base = dict(claim_kind="relationship", kind="commit_modifies", granularity="file", frm=ep_commit(C.sha),
                to=ep_file("src/a.py"), statement="Commit modified src/a.py.", cls="git_object_fact",
                provenance="git:diff-tree", provenance_raw={}, origin={"kind": "git_object", "commit": C.sha},
                qualifier="git tree change", citations=[citation(C, C.changes)], anchor={"commit": C.sha},
                params=params or {"rename_threshold": 50}, max_status="observed",
                check=check if check is not None else {"method": "git_object_check", "establishes": "presence",
                                                        "result": "pass", "detail": "ok"})
    base.update(kw)
    return make_record(ctx, **base)


def test_claim_id_deterministic_and_run_independent() -> None:
    a, b = _rec(CTX), _rec(CTX2)
    assert a["claim_id"] == b["claim_id"]
    assert a["claim_id"].startswith("c_") and len(a["claim_id"]) == 66
    assert a["checks"][0]["check_id"] == b["checks"][0]["check_id"]


def test_claim_id_changes_with_parameters_anchor_and_subject() -> None:
    base = _rec()["claim_id"]
    assert _rec(params={"rename_threshold": 60})["claim_id"] != base
    assert _rec(anchor={"commit": "9" * 40})["claim_id"] != base
    assert _rec(to=ep_file("src/b.py"))["claim_id"] != base
    assert _rec(kind="commit_adds")["claim_id"] != base


def test_symmetric_claim_id() -> None:
    p = parameters({"min_revs": 5})["digest"]
    kw = dict(claim_kind="relationship", kind="co_changed_with", granularity="file", anchor={"range": [None, "b" * 40]},
              parameters_digest=p)
    ab = claim_id(frm=ep_file("a.py"), to=ep_file("b.py"), symmetric=True, **kw)
    ba = claim_id(frm=ep_file("b.py"), to=ep_file("a.py"), symmetric=True, **kw)
    assert ab == ba
    assert claim_id(frm=ep_file("a.py"), to=ep_file("b.py"), **kw) != claim_id(frm=ep_file("b.py"), to=ep_file("a.py"), **kw)
    r = _rec(kind="co_changed_with", frm=ep_file("z.py"), to=ep_file("a.py"), symmetric=True, cls="history_pattern")
    assert (r["from"]["file"], r["to"]["file"]) == ("a.py", "z.py")


def test_observed_needs_passing_independent_check() -> None:
    ok = _rec()
    assert (ok["status"], ok["label"]) == ("observed", "observed")
    bad = _rec(check={"method": "git_recount", "establishes": "presence", "result": "inconclusive", "detail": "3 != 4"})
    assert (bad["status"], bad["label"]) == ("unvalidated", "inferred") and "3 != 4" in bad["status_reason"]
    capped = _rec(max_status="unvalidated", cls="history_inferred", unvalidated_reason="inferred")
    assert capped["status"] == "unvalidated"
    assert_valid([ok, bad, capped])


def test_citation_required_and_paths_checked() -> None:
    with pytest.raises(HistoryError) as ei:
        _rec(citations=[])
    assert ei.value.code == "E_SCHEMA"
    for bad in ("/abs.py", "../up.py", "a/../b.py", "dir/"):
        with pytest.raises(HistoryError) as ei:
            ep_file(bad)
        assert ei.value.code == "E_PATH"
    assert ep_path("src/new-frontend")["entity"] == "file" or ep_path("src/new-frontend")


def test_finalize_dedupes_sorts_and_detects_collision() -> None:
    a = _rec()
    b = _rec(to=ep_file("src/b.py"))
    out = finalize([b, a, _rec(CTX2)])
    assert [r["claim_id"] for r in out] == sorted([a["claim_id"], b["claim_id"]])
    forged = dict(a)
    forged["statement"] = "something else"
    with pytest.raises(HistoryError) as ei:
        finalize([a, forged])
    assert ei.value.code == "E_COLLISION"


def test_schema_rejects_verified_history() -> None:
    r = _rec()
    r["status"] = "verified"
    r["label"] = "verified"
    assert schema_errors(r)
