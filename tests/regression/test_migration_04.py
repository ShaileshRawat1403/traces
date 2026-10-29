"""Every record the baseline produced (0.3) migrates to a valid traces-evidence/0.4 record, checked by the stdlib
checker and by jsonschema (reference implementation) over all records; and the run loads into the store."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import jsonschema
import pytest

from traces.evidence.migrate import V04, load_schema, migrate_jsonl
from traces.evidence.schema_check import Validator
from traces.evidence.store import Store, import_pipeline_run

pytestmark = pytest.mark.baseline


@pytest.mark.parametrize("rel", ["v1/validation/evidence.jsonl", "adapter_real/out/records.jsonl"])
def test_migrated_records_valid_04(baseline_run: Path, rel: str):
    recs = list(migrate_jsonl(open(baseline_run / rel)))
    s = load_schema(V04)
    std = Validator(s)
    js = jsonschema.Draft202012Validator(s, format_checker=jsonschema.FormatChecker())
    assert recs
    bad_std = [r["claim_id"] for r in recs if std.errors(r)]
    bad_js = [r["claim_id"] for r in recs if not js.is_valid(r)]
    assert bad_std == [] and bad_js == []
    assert all(r["label"] == "rejected" for r in recs if r["status"] == "rejected")
    assert all("no_source_location" in r["flags"] for r in recs if r["status"] == "missing_location")


def test_store_import_and_export(baseline_run: Path, tmp_path: Path):
    st = Store(":memory:")
    res = import_pipeline_run(baseline_run, st)
    assert res["records"] == 10016
    assert res["by_status"] == {"verified": 4551, "observed": 5313, "unvalidated": 140, "rejected": 12}
    m = st.export_jsonl(res["snapshot_id"], tmp_path / "export.jsonl")
    lines = (tmp_path / "export.jsonl").read_text().splitlines()
    assert m["records"] == len(lines) == 10016
    assert Counter(json.loads(x)["schema_version"] for x in lines) == {V04: 10016}
