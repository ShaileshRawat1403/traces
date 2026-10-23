"""run() / GitHistoryRunner end to end on synthetic repos (contract section 8.11, D-H12)."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

from traces.evidence.types import ComponentDef, ComponentMap, EvidenceSet
from traces.history import HistoryConfig, HistoryError, HistoryRepoRef, commit_facts, ingest, lifecycle
from traces.history import runner as R
from traces.history.config import canon
from traces.history.gitcmd import CallLimits, GitRunner, call_limits, limit_violation
from traces.history.milestones import select_milestones
from traces.history.records import RunContext, canonical_hash, finalize, strip_volatile
from traces.history.runner import STAGE_ORDER, GitHistoryRunner, RunBudget, run

from ._repo import SynthRepo
from ._schema import assert_valid
from .conftest import ref
from .test_milestones import _build as _build_ms
from .test_pr_context import OfflineFake, cached

AT = "2026-10-21T12:00:00+05:30"


def _build(r: SynthRepo) -> dict[str, str]:
    s = _build_ms(r)
    r.write("src2.py", "pr\n")
    s["pr7"] = r.commit("Tidy src2 (#7)")
    s["head"] = s["pr7"]
    return s


def _stages(res: Any) -> dict[str, tuple[str, str | None, int]]:
    return {s["stage"]: (s["status"], s["reason"], s["records"]) for s in res.report["stages"]}


def _stable(report: dict[str, Any]) -> str:
    return canon({k: v for k, v in report.items() if k != "volatile"})


@pytest.fixture
def built(synth: SynthRepo) -> tuple[SynthRepo, dict[str, str]]:
    return synth, _build(synth)


def test_defaults_missing_inputs_not_partial_and_deterministic(built: Any, tmp_path: Path) -> None:
    r, s = built
    cache = tmp_path / "cache"
    a = run(ref(r), HistoryConfig(), cache_dir=cache, run_id="h-a", at=AT)
    b = run(ref(r), HistoryConfig(), cache_dir=cache, run_id="h-b", at="2026-10-22T09:00:00+05:30")  # warm cache
    c = run(ref(r), HistoryConfig())
    assert_valid(a.records)
    rep = a.report
    assert rep["report_version"] == "traces-history-run/1" and rep["complete"] is True and rep["partial_reasons"] == []
    assert rep["stage_order"] == list(STAGE_ORDER) and [x["stage"] for x in rep["stages"]] == list(STAGE_ORDER)
    st = _stages(a)
    assert st["cochange_component"] == ("skipped", "no_component_map", 0)
    assert st["evidence_set_diff"] == ("skipped", "no_evidence_sets", 0)
    assert st["pr_context"] == ("skipped", "no_pr_provider", 0)
    assert st["aliases"] == ("skipped", "not_in_v1_default", 0)
    assert st["commit_facts"][0] == "completed" and st["snapshot_compare"][0] == "completed"
    assert rep["records"] == len(a.records) == sum(v[2] for v in st.values())
    assert [x["claim_id"] for x in a.records] == sorted(x["claim_id"] for x in a.records)
    for other in (b, c):
        assert canonical_hash(other.records) == canonical_hash(a.records) == other.report["records_digest"]
        assert _stable(other.report) == _stable(a.report)
        assert canon(strip_volatile(list(other.records))) == canon(strip_volatile(list(a.records)))
    assert set(rep["volatile"]) >= {"run_id", "at", "elapsed_s", "stage_elapsed_s", "finalize_s", "rss_growth_mb"}
    assert a.report["volatile"]["run_id"] == "h-a" and all(x["run_id"] == "h-a" for x in a.records)


def test_all_inputs_and_truncations(built: Any) -> None:
    r, s = built
    log = ingest(ref(r), HistoryConfig())
    ms = select_milestones(log)
    cm = ComponentMap(s["head"], {
        "component::lib": ComponentDef("component::lib", "lib", "backend", ("lib",), "t"),
        "component::src2": ComponentDef("component::src2", "src2", "backend", ("src2.py", "work.py"), "t")}, "d" * 64)
    sets = {m.sha: EvidenceSet("synthetic/repo", m.sha, "traces-evidence/0.4", []) for m in ms[:-1]}
    prov = OfflineFake({7: cached(7, s["pr7"], "Tidy src2 because it was noisy.", [])})
    res = run(ref(r), HistoryConfig(), components=cm, evidence_sets=sets, pr_provider=prov, run_id="h", at=AT)
    assert_valid(res.records)
    st = _stages(res)
    assert res.report["complete"] is True
    assert st["evidence_set_diff"][:2] == ("truncated", "evidence_sets_missing_for_some_milestones")
    assert st["pr_context"] == ("completed", None, 2)
    assert st["cochange_component"][0] in ("completed", "truncated")
    assert res.report["inputs"] == {"components_digest": "d" * 64, "evidence_set_shas": sorted(sets),
                                    "pr_provider": True, "max_milestones": 8}
    one = {ms[0].sha: sets[ms[0].sha]}
    st1 = _stages(run(ref(r), HistoryConfig(), evidence_sets=one))
    assert st1["evidence_set_diff"][:2] == ("skipped", "no_evidence_sets")


def _baseline(r: SynthRepo) -> Any:
    return run(ref(r), HistoryConfig(), run_id="h", at=AT)


def _wrap(monkeypatch: pytest.MonkeyPatch, stage: str, before: Any = None, after: Any = None) -> None:
    orig = R.STAGE_FUNCS[stage]

    def go(st: Any) -> Any:
        if before:
            before()
        out = orig(st)
        if after:
            after()
        return out
    monkeypatch.setitem(R.STAGE_FUNCS, stage, go)


def test_time_budget_mid_stage_abort_and_pre_stage_skip(built: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    r, _ = built
    base = _baseline(r)
    t = {"now": 0.0}
    _wrap(monkeypatch, "churn", before=lambda: t.update(now=1e6))
    with R.probes(clock=lambda: t["now"]):
        res = run(ref(r), HistoryConfig(), run_id="h", at=AT)
    st = _stages(res)
    assert st["lifecycle"][0] == "completed"
    assert st["churn"] == ("aborted", "budget_time", 0)
    assert all(st[x][:2] == ("skipped", "budget_time") for x in STAGE_ORDER[STAGE_ORDER.index("churn") + 1:])
    assert res.report["complete"] is False and res.report["partial_reasons"][0]["stage"] == "churn"
    kept = {"commit_facts", "lifecycle"}
    log = ingest(ref(r), HistoryConfig())
    ctx = RunContext("h", AT, "synthetic/repo", log.repo.sha)
    direct = finalize([*commit_facts(log, ctx=ctx).records, *lifecycle(log, ctx=ctx).records])
    assert len(res.records) == sum(st[k][2] for k in kept)
    assert canonical_hash(res.records) == canonical_hash(direct)
    assert {x["claim_id"] for x in res.records} <= {x["claim_id"] for x in base.records}
    assert_valid(res.records)

    monkeypatch.undo()
    t["now"] = 0.0
    _wrap(monkeypatch, "commit_facts", after=lambda: t.update(now=1e6))
    with R.probes(clock=lambda: t["now"]):
        res2 = run(ref(r), HistoryConfig(), run_id="h", at=AT)
    st2 = _stages(res2)
    assert st2["commit_facts"][0] == "completed"
    assert st2["lifecycle"][:2] == ("skipped", "budget_time") and "not started" in [
        x for x in res2.report["stages"] if x["stage"] == "lifecycle"][0]["detail"]


def test_memory_budget_probe_and_memoryerror(built: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    r, _ = built
    m = {"rss": 100.0}
    _wrap(monkeypatch, "hotspots", before=lambda: m.update(rss=100.0 + 5000))
    with R.probes(rss_mb=lambda: m["rss"]):
        res = run(ref(r), HistoryConfig())
    st = _stages(res)
    assert st["churn"][0] == "completed" and st["hotspots"] == ("aborted", "budget_memory", 0)
    assert st["cochange_file"][:2] == ("skipped", "budget_memory") and res.report["complete"] is False

    monkeypatch.undo()

    def oom(st: Any) -> Any:
        raise MemoryError
    monkeypatch.setitem(R.STAGE_FUNCS, "manifests", oom)
    st2 = _stages(run(ref(r), HistoryConfig()))
    assert st2["manifests"] == ("aborted", "budget_memory", 0) and st2["reverts"][:2] == ("skipped", "budget_memory")


def test_records_cap_is_deterministic(built: Any) -> None:
    r, _ = built
    base = _stages(_baseline(r))
    upto = sum(base[x][2] for x in STAGE_ORDER[:STAGE_ORDER.index("cochange_file") + 1])
    assert base["manifests"][2] > 1
    b = RunBudget(max_records=upto + 1)
    x = run(ref(r), HistoryConfig(), budget=b, run_id="h", at=AT)
    y = run(ref(r), HistoryConfig(), budget=b, run_id="h2", at=AT)
    st = _stages(x)
    assert st["manifests"] == ("aborted", "budget_records", 0)
    assert all(st[s][:2] == ("skipped", "budget_records") for s in STAGE_ORDER[STAGE_ORDER.index("manifests") + 1:])
    assert x.report["records"] == upto and x.report["records_digest"] == y.report["records_digest"]
    assert _stable(x.report) == _stable(y.report)


def test_on_exhausted_fail_raises(built: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    r, _ = built
    fail = RunBudget(on_exhausted="fail")
    t = {"now": 0.0}
    _wrap(monkeypatch, "churn", before=lambda: t.update(now=1e6))
    with R.probes(clock=lambda: t["now"]), pytest.raises(HistoryError) as ei:
        run(ref(r), HistoryConfig(), budget=fail)
    assert ei.value.code == "E_TIMEOUT" and ei.value.stage == "churn"
    monkeypatch.undo()
    m = {"rss": 0.0}
    _wrap(monkeypatch, "lifecycle", before=lambda: m.update(rss=1e6))
    with R.probes(rss_mb=lambda: m["rss"]), pytest.raises(HistoryError) as ei:
        run(ref(r), HistoryConfig(), budget=fail)
    assert ei.value.code == "E_LIMIT"
    monkeypatch.undo()
    with pytest.raises(HistoryError) as ei:
        run(ref(r), HistoryConfig(), budget=RunBudget(max_records=5, on_exhausted="fail"))
    assert ei.value.code == "E_LIMIT" and ei.value.stage == "commit_facts"


def test_contract_errors_fail_closed(built: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    r, s = built
    cases = [
        (HistoryRepoRef(tmp_path / "nope", "o/r", s["head"]), "E_REPO"),
        (HistoryRepoRef(r.path, "o/r", "f" * 40), "E_SHA"),
    ]
    for repo, code in cases:
        with pytest.raises(HistoryError) as ei:
            run(repo, HistoryConfig())
        assert ei.value.code == code
    bogus = {s["side_dep"]: EvidenceSet("synthetic/repo", s["side_dep"], "traces-evidence/0.4", [])}
    with pytest.raises(HistoryError) as ei:
        run(ref(r), HistoryConfig(), evidence_sets=bogus)
    assert ei.value.code == "E_EVIDENCE_SET"
    good = _baseline(r).records

    def bad_schema(st: Any) -> Any:
        rec = dict(good[0])
        rec["claim_id"] = "c_" + "0" * 64
        rec["status"] = "verified"
        return R._StageRun([rec], {})
    monkeypatch.setitem(R.STAGE_FUNCS, "reverts", bad_schema)
    with pytest.raises(HistoryError) as ei:
        run(ref(r), HistoryConfig())
    assert ei.value.code == "E_SCHEMA" and ei.value.stage == "finalize"

    def collide(st: Any) -> Any:
        rec = dict(good[0])
        rec["statement"] = "different"
        return R._StageRun([rec], {})
    monkeypatch.setitem(R.STAGE_FUNCS, "reverts", collide)
    with pytest.raises(HistoryError) as ei:
        run(ref(r), HistoryConfig(), run_id="h", at=AT)
    assert ei.value.code == "E_COLLISION"


def test_runner_cap_is_ceiling_and_reuses_log(built: Any) -> None:
    r, _ = built
    gr = GitHistoryRunner(max_milestones=6)
    low = gr.select_milestones(ref(r), max_milestones=4)
    assert len(low) == 4
    with pytest.raises(HistoryError) as ei:
        gr.select_milestones(ref(r), max_milestones=8)
    assert ei.value.code == "E_CONFIG"
    with pytest.raises(HistoryError) as ei:
        GitHistoryRunner(max_milestones=21)
    assert ei.value.code == "E_CONFIG"
    sets = {m.sha: EvidenceSet("synthetic/repo", m.sha, "traces-evidence/0.4", []) for m in low}
    res = gr.run(ref(r), evidence_sets=sets)
    assert res.report["inputs"]["max_milestones"] == 6
    assert {m.sha for m in low} <= {m["sha"] for m in res.report["milestones"]}
    assert _stages(res)["evidence_set_diff"][0] in ("completed", "truncated")
    direct = run(ref(r), HistoryConfig(), evidence_sets=sets, max_milestones=6)
    assert direct.report["records_digest"] == res.report["records_digest"]


def test_git_children_limits_fail_closed(built: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    r, _ = built
    with GitRunner(r.path) as g:
        assert g.run("rev-parse", ["HEAD"]).strip()
        with call_limits(CallLimits(as_bytes=4 << 20)), pytest.raises(HistoryError) as ei:
            g.run("log", ["-1", "--format=%H"])
        assert ei.value.code == "E_LIMIT"
    assert limit_violation(-signal.SIGXCPU, b"") and limit_violation(-signal.SIGKILL, b"")
    assert limit_violation(128, b"fatal: Out of memory, malloc failed") and limit_violation(0, b"") is None
    assert limit_violation(128, b"fatal: bad revision") is None
    monkeypatch.setattr(R, "GIT_AS_HEADROOM_MB", 0)
    with R.probes(rss_mb=lambda: 0.0), pytest.raises(HistoryError) as ei:
        run(ref(r), HistoryConfig(), budget=RunBudget(memory_mb=4))
    assert ei.value.code == "E_LIMIT"


def test_run_inside_network_namespace(built: Any) -> None:
    r, s = built
    unshare = shutil.which("unshare")
    if unshare is None:
        pytest.skip("unshare not available")
    probe = subprocess.run([unshare, "-rn", "true"], capture_output=True)
    if probe.returncode != 0:
        pytest.skip(f"unprivileged network namespace not permitted here: {probe.stderr.decode().strip()[:120]}")
    outside = run(ref(r), HistoryConfig(), run_id="h", at=AT).report["records_digest"]
    code = textwrap.dedent(f"""
        import socket, sys
        from pathlib import Path
        from traces.history import HistoryConfig, HistoryRepoRef, run
        try:
            socket.create_connection(("1.1.1.1", 443), timeout=2)
            sys.exit("network reachable inside the namespace; test is not meaningful")
        except OSError:
            pass
        res = run(HistoryRepoRef(Path({str(r.path)!r}), "synthetic/repo", {s["head"]!r}), HistoryConfig(),
                  run_id="h", at={AT!r})
        print(res.report["records_digest"], res.report["complete"])
    """)
    pkg = Path(R.__file__).resolve().parents[2]
    env = {**os.environ, "PYTHONPATH": str(pkg)}
    p = subprocess.run([unshare, "-rn", sys.executable, "-c", code], capture_output=True, env=env, timeout=300)
    assert p.returncode == 0, p.stderr.decode()[-800:]
    assert p.stdout.decode().split() == [outside, "True"]


def test_runtime_finalize_uses_stdlib_validator_only() -> None:
    import ast

    tree = ast.parse(Path(R.__file__).read_text())
    mods = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    mods |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not any(m.split(".")[0] == "jsonschema" for m in mods)
    assert R.VALIDATE_EVERY_RECORD is True


def test_aliases_opt_in_stage(synth: SynthRepo, tmp_path: Path) -> None:
    """D-H14: HistoryConfig.aliases=True runs the aliases stage; other stages' records and claim_ids are unchanged."""
    from traces.history.aliases import alias_suggestions

    from .test_aliases import _build as _build_alias

    r = synth
    _build_alias(r)
    off = run(ref(r), HistoryConfig(), run_id="h-a", at=AT)
    on = run(ref(r), HistoryConfig(aliases=True), run_id="h-a", at=AT)
    on2 = run(ref(r), HistoryConfig(aliases=True), cache_dir=tmp_path / "c", run_id="h-b",
              at="2026-10-22T09:00:00+05:30")
    assert_valid(on.records)
    st = _stages(on)
    direct = alias_suggestions(ingest(ref(r), HistoryConfig()),
                               ctx=RunContext("h-a", AT, ref(r).repo, ref(r).sha)).records
    assert len(direct) == 2 and st["aliases"] == ("completed", None, 2)
    assert _stages(off)["aliases"] == ("skipped", "not_in_v1_default", 0)
    alias_ids = {x["claim_id"] for x in direct}
    assert {x["claim_id"] for x in on.records} - alias_ids == {x["claim_id"] for x in off.records}
    assert all(x["parameters"]["values"]["aliases"] is True for x in direct)
    assert on.report["config"]["aliases"] is True and off.report["config"]["aliases"] is False
    assert on.report["config_digest"] != off.report["config_digest"]
    assert canonical_hash(on2.records) == canonical_hash(on.records) == on.report["records_digest"]
    with pytest.raises(HistoryError) as ei:
        HistoryConfig(aliases="yes").validate()  # type: ignore[arg-type]
    assert ei.value.code == "E_CONFIG"
