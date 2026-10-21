# Task 002 closeout (Decision 002-B corrections)

Author: Traces (lead investigator seat). Date: 2026-10-21 IST. Decision owner: Shailesh.
Decision applied: 002-B, ACCEPTED WITH CORRECTIONS (received 2026-10-21 13:34 IST), recorded in `spec/DECISIONS.md` section D-002B and `spec/CHANGELOG.md` version 3.
Corrected run: `t002-20261021T1356-002b-2` (13:56:48 to 13:57:30 IST). Repo: `fastapi/full-stack-fastapi-template` at `b1125d8839482cb7bbae603ddc6d0081bf87532e`. Extractor: CodeGraph 1.6.2, unchanged.

## 1. Conclusion

Traces has verified the nine defined source-level architecture links and statically established the persistence path. Two third-party library behavior transitions remain inferred, and no runtime database write has been observed.

## 2. How the corrected run was made

- No CodeGraph extraction. The run reuses the raw output of `t002-20261021T1049-3`: the real index `src/fsft/.codegraph/codegraph.db` and the two index copies `work/t002-20261021T1049-3/copyA`, `copyB`, read-only. All 1,055 files of that run directory hash the same before and after the corrected run.
- Adapter, validators (CPython 3.14.8 `ast`, TypeScript Compiler API 6.0.3), checker, report, CT1 to CT16 and the new regression tests ran fresh, inside one `tools/offline.sh` invocation (`unshare -rn`). Probe (a) to (e) passed in a fresh namespace (`net:[4026532211]`, outer `net:[4026531840]`). `tools/offline.sh` sha256 `81042fec...` unchanged. Wall time 42.9 s, peak RSS 615 MB.
- Code before the edits: `task002/_superseded_v1/` (adapter, validators, pipeline, tests, spec, fixtures, with `SHA256SUMS`). Previous export: `task002/out/_superseded_v1/`.
- New driver files: `pipeline/run_002b.sh`, `pipeline/inside_run_002b.py`, `tests/regression_002b.py`.
- Run `t002-20261021T1356-002b-1` stopped at the fixture build (a syntax error I introduced in `fixtures/build_fixture.py`). It produced no records and is kept, not deleted.

## 3. Corrected counts

All 10,016 records (10,050 in run 1049-3, minus 34 rows consolidated into their duplicates; every row is still attached).

| Set | verified | observed | unvalidated | missing_location | rejected | total |
|---|---|---|---|---|---|---|
| CodeGraph edges | 4,538 | 36 (observed import statements) | 59 | 0 | 9 | **4,642** |
| CodeGraph nodes | | 2,075 | 1 | | | 2,076 |
| CodeGraph unresolved references | | 3,202 | 78 | | | 3,280 records for 3,314 rows |
| Fixture claims (traces-lab-fixture) | 13 | | 2 (H1, H2) | | | 15 |
| Injected negatives (N1, N2a, N2b) | | | | | 3 | 3 |
| **All** | **4,551** | **5,313** | **140** | **0** | **12** | **10,016** |

- Correction A target met exactly: verified 4,538, observed import statements 36 (31 Python, 5 TSX), unvalidated 59, rejected 9, total 4,642. No deviation.
- Labels: observed 5,313, verified 4,551, inferred 152. Classes: `source_backed_declaration` 5,356, `statically_derived` 3,735, `analyzer_inference` 925. No record carries the old class name.
- Compared with run 1049-3, record by record: the only status changes are the 36 import edges (verified to observed). Every other record keeps its status, and no class changed except the rename.
- All 12 rejected records are in the export and visible: 9 CodeGraph `imports` edges (rows 2024, 2052, 2085, 2157, 2189, 2200, 2210, 2310, 2315) plus N1, N2a, N2b.

## 4. Rulings as applied

| Ruling | Result |
|---|---|
| 1 EOF | 2,968 records with a normalized whole-file range (3,373 file-range locations). Each stores the original CodeGraph coordinates in `original` and the normalized range `[1, n]` with `end_exclusive_line` n + 1 and `terminal_newline`. Strict L2 applies everywhere else. 0 locations of any kind address the EOF position (94,472 locations and check inputs checked). Normalization changed no status. |
| 2 claim_id | Shared ids: 0 of 10,016 (was 608 ids shared by 3,334 records). Exact duplicates consolidated: 34 records holding 68 rows, all unresolved references, each listing both rows with `row_ref`, full `provenance_raw` and `status_history`. 0 `E_COLLISION`. Adapter rows in = rows covered = 10,032. |
| 3 H1, H2 | Unchanged: `library_contract`, status unvalidated, label inferred. No library source downloaded. |
| 4 A1 to A3 | Wording updated in `spec/FASTAPI_RULES.md` and `spec/EXPECTED_CHAIN.md`. |
| 5 rename | `analyzer_inference`; class is origin only and no longer constrains status in `spec/evidence_record.schema.json` (`traces-evidence/0.3`) and `spec/EVIDENCE_SCHEMA.md`. |

## 5. Verified links and unresolved library behavior

Verified source-level links (each through independent checks; CodeGraph never establishes a link):

| Link | Claim | Established by |
|---|---|---|
| L1 | `Items` renders `AddItem` | TS syntax_structure, binding_resolution |
| L2 | `AddItem` binds `onSubmit`; `onSubmit` calls `mutation.mutate` | TS syntax_structure, binding_resolution |
| L3 | `mutationFn` calls `ItemsService.createItem` | TS syntax_structure, binding_resolution |
| L4 | `createItem` implements POST `/api/v1/items/` (`items-create_item`) | rule R3 |
| L5 | the operation routes to `items.py::create_item` | rules R1, R3 |
| L6 | `create_item` depends on `get_db` | rule R2 |
| L7 | `create_item` depends on `get_current_user` (transitive steps L7T1, L7T2 verified) | rule R2 |
| L8 | `create_item` persistence path through the `SessionDep`-bound session | rule R4, qualifier "statically established persistence path" |
| L9 | `create_item` uses `Item` and returns `ItemPublic` | Python syntax_structure, binding_resolution |

Unresolved library behavior (not verified, not part of the nine links):

| Hop | Claim | Status |
|---|---|---|
| H1 | react-hook-form `form.handleSubmit(onSubmit)` calls `onSubmit` (`AddItem.tsx:88`) | inferred, unvalidated library-contract assumption |
| H2 | TanStack Query `mutation.mutate(data)` calls the `mutationFn` (`AddItem.tsx:69` to `:56`) | inferred, unvalidated library-contract assumption |

L8 is static only. No runtime database write has been observed; the app was never started.

## 6. Tests

- Contract tests CT1 to CT16: **16 of 16 PASS** (`out/ct_results.json`). Amended for 002-B: CT4 class name; CT5 now also requires the schema checker self-test to have run and passed (23 of 23 cases); CT10 counts consolidated rows (3,280 records cover 3,314 rows); CT15 takes indexer evidence from the reused run's log (`netprobe_index_reused.log`, indexer processes in that run's wrapper namespace `net:[4026532230]`), with a fresh probe in this run.
- Regression tests: **8 of 8 PASS** (`out/regression_results.json`).

| Test | What it shows |
|---|---|
| RT1 | 10,016 distinct ids, 0 shared in the export and in the adapter output; every id recomputes from record content |
| RT2 | synthetic: same content gives the same id; another line, column, target name, extractor version or declared range gives another id |
| RT3 | the 34 real consolidations keep both rows and their history; synthetic duplicates merge with history; distinct content under one id raises `E_COLLISION` |
| RT4 | EOF with a terminal newline: synthetic `a\nb\n` and real `frontend/src/client/types.gen.ts` (original end 948, normalized 947, exclusive 948); L2 rejects a site on the EOF position |
| RT5 | EOF without a terminal newline (`a\nb`) and the empty blob, synthetic only: no indexed file at `b1125d8` lacks a terminal newline (142 end in a newline, 10 are empty) |
| RT6 | the EOF position is never an evidence location: 94,472 locations and check inputs, 16,959 file ranges, 0 violations |
| RT7 | distribution of section 3 and the 12 visible rejected records |
| RT8 | validation never changes class |

- Schema: 10,016 of 10,016 export records and 9,998 of 9,998 adapter records valid against `traces-evidence/0.3`.

## 7. Hashes

`out/` (sha256, also in `out/SHA256SUMS`):

| File | sha256 |
|---|---|
| evidence.jsonl | `cb0f0032f29d864bbcbe59f28110c3b7f08443a019b56ac718086aadb5e6fb2f` |
| chain.json | `b810ab582c7d2ebbdccb5d555da9ea833c8bd35b9d9cf03fc74c0a4c8f1a92c7` |
| coverage.json | `7214247a8a87bcc61537a2d65ef7fefd81b5b8e4380440b35f9759feeffa2062` |
| rule_findings.json | `09c973940f4b645b356374a544b0ee1c67cf2fcc42668c475b616be537f8f0dc` |
| ct_results.json | `98465519c41210faf67b110d31d21a557fc23730d5a18d28a6eef4b8d106d07e` |
| regression_results.json | `db217e37b9e99b36a8cebf0b16fafb06e3a16e01080881225fbff96586aefb4e` |

Canonical (run-independent) hashes:

- Adapter output, real index = copyA = copyB: `45600280cb496a67647ff3dab0ba96abcd810e52e1c72ebca1da98d1376cef8e`.
- Validation run v1 = v2: `73db432be3babab4922f3158a9ed86b63a2454f61647d883f978701f5ff0053d`. The two files differ byte-wise only in run-specific fields.

Superseded (run 1049-3, kept in `out/_superseded_v1/`): validation canonical `47bd353b...`, adapter canonical `201d0686...`.

## 8. Scope caveats

1. ChatGPT reviewed `REVIEW_PACKAGE_002.md` only, not `RULINGS.md` or `review/audit/`. These are rulings on the five summarized questions, not approval of every implementation detail.
2. The TypeScript recheck in the 60-edge audit sample was narrower than a second compiler-based validation: a resolver over import statements and range nesting, not a second compiler.

## 9. Disclosures

- **Self-test defect in run 1049-3.** `schema_selftest.txt` was empty: the command omitted the schema path and crashed, and CT5 passed without checking it. My ruling R-5b said the self-test showed bad records rejected; that was wrong for 1049-3. Fixed in this run (23 of 23 cases pass) and CT5 now requires it. Erratum appended to `RULINGS.md`.
- **Box restore.** During the work, a box restore removed the previous `out/`, the adapter output directories of run 1049-3, `node_modules`, the npm cache and `tools/cghome`. I rebuilt `out/_superseded_v1/` from the run directory (the five files match the sha prefixes in the audit record), recreated `tools/cghome`, and reinstalled the pinned toolchain offline from the local cache with `npm ci --offline --ignore-scripts` (TypeScript 6.0.3, 5.9.3, CodeGraph 1.6.2). The lost adapter outputs of 1049-3 were regenerated by this run; they are not restored copies. See `out/_superseded_v1/README.md`.

## 10. Residual open items

- CT8 wording (`missing_location` expectations) still describes the adapter stage only; worth one sentence of clarification.
- `RULINGS.md` and `review/audit/` remain unreviewed by ChatGPT.
- O1 (HOME path wording in the Lab docs) is still open in `spec/DECISIONS.md`.
- Fixture claims carry class `analyzer_inference`; a separate fixture class might read better and would need a decision.
- No reference `jsonschema` validator was used; `validators/schema_check.py` is a stdlib subset. A pinned reference validator stays planned for Task 003.
- The case without a terminal newline is covered by synthetic tests only, since the repo has no such file.
- H1, H2 and assumption A4 stay unresolved by design in Task 002.
- Task 003 not opened. Nothing pushed.
