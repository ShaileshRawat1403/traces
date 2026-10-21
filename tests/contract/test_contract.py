"""CT1 to CT16 as pytest cases. Mapping to the research tests: docs/TEST_MAPPING.md."""
import json

import pytest

pytestmark = pytest.mark.baseline

CT = [f"CT{i}" for i in range(1, 17)]


@pytest.mark.parametrize("name", CT)
def test_contract(ct_results, name):
    r = ct_results[name]
    assert r["result"] == "PASS", f"{name} FAIL: {json.dumps(r['detail'], default=str)[:4000]}"


def test_contract_count(ct_results):
    assert sorted(ct_results, key=lambda k: int(k[2:])) == CT
