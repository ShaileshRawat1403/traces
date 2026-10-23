"""Review F7: a baseline run emits chain.json and coverage.json (Task 002 steps 8 to 10) next to the validation output,
with every L1 to L9 link verified, the library hops kept inferred and the injected controls rejected."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.baseline


def test_chain_and_coverage_artifacts(baseline_run: Path):
    vd = baseline_run / "v1" / "validation"
    chain = json.loads((vd / "chain.json").read_text())
    cov = json.loads((vd / "coverage.json").read_text())
    assert chain["summary"] == {f"L{i}": "verified" for i in range(1, 10)}
    assert {k: v["status"] for k, v in chain["library_hops"].items()} == {"H1": "unvalidated", "H2": "unvalidated"}
    assert all(v["label"] == "inferred" for v in chain["library_hops"].values())
    assert {v["status"] for v in chain["negative_controls"].values()} == {"rejected"} and len(chain["negative_controls"]) == 3
    edges = cov["codegraph"]["edges"]
    assert edges["count"] == 4642 and edges["by_status"] == {"observed": 36, "rejected": 9, "unvalidated": 59, "verified": 4538}
    assert cov["decision_002B"]["claim_id"]["shared_ids"] == 0
    res = json.loads((baseline_run / "inside_result.json").read_text())
    assert res["validation"]["v1"]["report"]["exit"] == 0
