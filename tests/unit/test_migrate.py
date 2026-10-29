import pytest

from traces.evidence.migrate import V03, V04, migrate_record_03_to_04, to_current


def rec(status: str, label: str, flags=None) -> dict:
    return {"schema_version": V03, "claim_id": "c_x", "status": status, "label": label, "flags": list(flags or [])}


def test_rejected_gets_own_label():
    r = migrate_record_03_to_04(rec("rejected", "inferred"))
    assert (r["schema_version"], r["migrated_from"], r["label"]) == (V04, V03, "rejected")


def test_missing_location_flag_and_label_kept():
    r = migrate_record_03_to_04(rec("missing_location", "inferred"))
    assert r["label"] == "inferred" and r["flags"] == ["no_source_location"]
    assert migrate_record_03_to_04(rec("missing_location", "inferred", ["no_source_location"]))["flags"] == ["no_source_location"]


def test_other_fields_untouched_and_input_not_mutated():
    src = rec("verified", "verified")
    r = migrate_record_03_to_04(src)
    assert src["schema_version"] == V03 and r["claim_id"] == "c_x" and r["label"] == "verified"


def test_to_current():
    assert to_current({"schema_version": V04})["schema_version"] == V04
    with pytest.raises(ValueError):
        to_current({"schema_version": "traces-evidence/0.2"})
