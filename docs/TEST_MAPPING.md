# Test mapping: Task 002 research tests -> pytest

Research sources: `research/task002/tests/ct_evaluate.py` (CT1-CT16) and `research/task002/tests/regression_002b.py` (RT1-RT8), unchanged.
Ports: `tests/contract/_ct.py` and `tests/regression/_rt.py`. pytest wrappers: `tests/contract/test_contract.py`, `tests/regression/test_regression.py`.
Both evaluate one baseline run (fixture `baseline_run` in `tests/conftest.py`: a fresh run, or `TRACES_BASELINE_RUN=<run dir>` to reuse a finished one).

| Old test | What it checks (ADAPTER_CONTRACT.md / Decision 002-B) | New pytest id | Port change |
| --- | --- | --- | --- |
| CT1 | version pin: 1.6.3 index and wrong integrity -> `E_VERSION`, no records | `tests/contract/test_contract.py::test_contract[CT1]` | none |
| CT2 | schema drift -> `E_SCHEMA` naming the missing item | `...::test_contract[CT2]` | none |
| CT3 | SHA binding: changed byte, HEAD~1, wrong manifest SHA -> `E_SHA` | `...::test_contract[CT3]` | none |
| CT4 | every edge maps to one normalized provenance; `provenance_raw` equals the row | `...::test_contract[CT4]` | none |
| CT5 | 100% schema-valid adapter output, 0 null required fields, checker self-test all PASS | `...::test_contract[CT5]` | none |
| CT6 | adapter never establishes: 0 observed, 0 verified, 100% label inferred | `...::test_contract[CT6]` | none |
| CT7 | frozen line checker: 378/379, the miss is `setOpen`, declaration location at 86 | `...::test_contract[CT7]` | Lab B verbatim script output no longer read (never in the pass criterion) |
| CT8 | missing location (1,981) and R-contains recovery (1,891 + 2 exceptions) | `...::test_contract[CT8]` | none |
| CT9 | path normalization; absolute and `../` -> `E_PATH` | `...::test_contract[CT9]` | none |
| CT10 | unresolved references kept (3,314 rows), `create_item` 5 records at 68-71 | `...::test_contract[CT10]` | none |
| CT11 | generated files flagged exactly | `...::test_contract[CT11]` | none |
| CT12 | 7 known relationships present as inferred | `...::test_contract[CT12]` | none |
| CT13 | known absences preserved (0, 0, 0) | `...::test_contract[CT13]` | none |
| CT14 | determinism: equal canonical sha256 across index runs | `...::test_contract[CT14]` | always 3 fresh index runs (D-008) |
| CT15 | isolation of indexer and children, telemetry off, write scope | `...::test_contract[CT15]` | requires 3 indexer summaries and no reused-index log; write scope is the run dir |
| CT16 | injected claims stay out of the extractor path | `...::test_contract[CT16]` | source snapshot located by the `## source` section |
| (count) | exactly CT1-CT16 evaluated | `...::test_contract_count` | new |
| RT1 | claim_id unique and regenerable | `tests/regression/test_regression.py::test_regression[RT1_claim_id_unique_and_regenerable]` | none |
| RT2 | claim_id synthetic cases | `...::test_regression[RT2_claim_id_synthetic]` | none |
| RT3 | exact duplicates consolidate with history | `...::test_regression[RT3_exact_duplicates_consolidate_with_history]` | none |
| RT4 | EOF with terminal newline | `...::test_regression[RT4_eof_with_terminal_newline]` | none |
| RT5 | EOF without terminal newline, empty files | `...::test_regression[RT5_eof_without_terminal_newline_and_empty]` | none |
| RT6 | EOF never an evidence location | `...::test_regression[RT6_eof_never_an_evidence_location]` | none |
| RT7 | distribution 4,642 = 4,538 / 36 / 59 / 9 | `...::test_regression[RT7_distribution]` | none |
| RT8 | class independent of status | `...::test_regression[RT8_class_independent_of_status]` | none |
| (count) | exactly RT1-RT8 evaluated | `...::test_regression_count` | new |
| closeout s7 | edges 4,538/36/59/9 of 4,642 and 12 rejected records | `...::test_baseline_distribution` | new |
| closeout | the 9 expected-chain links and library hops | `...::test_nine_links_and_library_hops` | new |
| closeout s7 | adapter canonical `45600280...` (3 copies), validation canonical `73db432b...` (v1 = v2) | `...::test_canonical_hashes_match_task002` | new |
| new | all baseline records migrate to valid 0.4 (stdlib checker and jsonschema) | `tests/regression/test_migration_04.py::test_migrated_records_valid_04[...]` | new |
| new | store import 4,551/5,313/140/12 and NDJSON export | `tests/regression/test_migration_04.py::test_store_import_and_export` | new |
