"""RT1 to RT8 (Decision 002-B) as pytest cases, plus the Task 002 baseline distribution and canonical hashes."""
import json
from collections import Counter

import pytest

pytestmark = pytest.mark.baseline

RT = ["RT1_claim_id_unique_and_regenerable", "RT2_claim_id_synthetic", "RT3_exact_duplicates_consolidate_with_history",
      "RT4_eof_with_terminal_newline", "RT5_eof_without_terminal_newline_and_empty", "RT6_eof_never_an_evidence_location",
      "RT7_distribution", "RT8_class_independent_of_status"]

# Task 002 closeout (research/task002/review/CLOSEOUT_002.md section 7): canonical hashes with run_id/at stripped.
ADAPTER_CANONICAL = "45600280cb496a67647ff3dab0ba96abcd810e52e1c72ebca1da98d1376cef8e"
VALIDATION_CANONICAL = "73db432be3babab4922f3158a9ed86b63a2454f61647d883f978701f5ff0053d"


@pytest.mark.parametrize("name", RT)
def test_regression(rt_results, name):
    r = rt_results[name]
    assert r["result"] == "PASS", f"{name} FAIL: {json.dumps(r['detail'], default=str)[:4000]}"


def test_regression_count(rt_results):
    assert list(rt_results) == RT


def _evidence(run):
    return [json.loads(line) for line in open(run / "v1" / "validation" / "evidence.jsonl")]


def test_baseline_distribution(baseline_run):
    ev = _evidence(baseline_run)
    edges = [r for r in ev if r["originator"]["name"] == "codegraph" and r["claim_kind"] == "relationship"]
    assert len(edges) == 4642
    assert Counter(r["status"] for r in edges) == {"verified": 4538, "observed": 36, "unvalidated": 59, "rejected": 9}
    assert len(ev) == 10016
    assert Counter(r["status"] for r in ev) == {"verified": 4551, "observed": 5313, "unvalidated": 140, "rejected": 12}
    rej = [r for r in ev if r["status"] == "rejected"]
    assert sorted(r["origin"].get("row_ref") or r["origin"].get("fixture_id") or "N1" for r in rej) == sorted(
        ["edges:2024", "edges:2052", "edges:2085", "edges:2157", "edges:2189", "edges:2200", "edges:2210", "edges:2310", "edges:2315", "N1", "N2a", "N2b"])
    assert all(r["visible_to_reviewer"] for r in rej)


def test_nine_links_and_library_hops(baseline_run):
    ev = {r["origin"].get("fixture_id"): r for r in _evidence(baseline_run) if r["originator"]["name"] == "traces-lab-fixture"}
    for fid in ("L1", "L2A", "L2B", "L3", "L4", "L5", "L6", "L7", "L7T1", "L7T2", "L8", "L9A", "L9B"):
        assert ev[fid]["status"] == "verified", fid
    assert ev["L8"]["qualifier"] == "statically established persistence path"
    assert ev["L8"]["evidence_scope"] == "static"
    for fid in ("H1", "H2"):
        assert ev[fid]["status"] == "unvalidated" and ev[fid]["label"] == "inferred" and "library_contract" in ev[fid]["flags"]


def test_canonical_hashes_match_task002(baseline_run):
    r = json.loads((baseline_run / "inside_result.json").read_text())
    assert set(r["canonical_hash"].values()) == {ADAPTER_CANONICAL}
    assert {v["canonical_hash"] for v in r["validation"].values()} == {VALIDATION_CANONICAL}
