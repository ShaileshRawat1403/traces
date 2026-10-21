# Task 002 rulings (step 11)

Author: Traces (lead investigator seat). Date: 2026-10-21 IST.
Status of every ruling below: **my ruling pending Architect1 confirmation**. The spec in `task002/spec/` is not edited. If Architect1 confirms, the spec change named in each ruling goes into a spec v3 with a CHANGELOG entry.

Numbers come from my audit of run `t002-20261021T1049-3` (scripts and outputs in `task002/review/audit/`). TESTED means I ran a script against Lab's outputs or the source at `b1125d8`. DESK means reasoning over code or text only.

## R-1. `claim_id` has no location, so distinct claims collide

My ruling pending Architect1 confirmation: spec defect. Keep Lab's no-merge choice.

TESTED (`audit/claimid_collisions.txt`):

- 10,050 records carry 7,324 distinct `claim_id` values. 608 ids are shared, by 3,334 records. This matches Lab.
- Records in colliding groups by kind: 2,932 `unresolved_reference`, 175 `calls`, 137 `references`, 74 `imports`, 7 `contains`, 5 nodes, 4 `instantiates`.
- 29 groups mix statuses (`observed` with `unvalidated`). Merging would have hidden an unvalidated record under an observed one. No-merge is correct.
- Adding site lines alone is not enough: 341 groups still collide. Adding the anchor range with columns still leaves 394 collisions, because unresolved references carry no `to` symbol.

Proposed formula (spec v3, EVIDENCE_SCHEMA section 2, `claim_id`): sha256 of canonical JSON of `[repo_sha, claim_kind, relationship_kind or node_kind, from.symbol, to.symbol, granularity, originator.name, anchor, reference]` where:

- `anchor` = `[role, file, start_line, start_col, end_line, end_col]` of the first originator location, chosen in role order `site`, `to_decl`, `from_decl`, then lowest start position;
- `reference` = `[reference_name, reference_kind]` for `unresolved_reference`, else null.

TESTED effect: 34 groups (68 records) still collide. In all 34 the two CodeGraph `unresolved_refs` rows are identical except the row id (example: `AxiosInstance` at `frontend/src/client/client/types.gen.ts:139` col 12, rows 1663 and 1664). These are true duplicates in the extractor output. Rule for them: keep both records, add `duplicate_of` pointing at the lower row id, and count them in coverage. Do not use the CodeGraph row id in the hash, because it is not stable across index versions.

## R-2. EOF trailing-line leniency in L2

My ruling pending Architect1 confirmation: material limitation, documented as a rule, not silently tolerated.

What Lab does (DESK, `validators/run_validation.py:279`): L2 counts line starts, `len(text.split("\n"))`, so a file ending in a newline has a valid line N+1. CodeGraph file nodes end there (for example `types.gen.ts` ends at 948 for 947 newline-terminated lines).

TESTED (`audit/a4_eof.py`, `audit/eof_quant.txt`), strict count = `len(text.splitlines())`:

- 2,968 records have at least one location ending on the EOF position. All are CodeGraph records, across 152 files.
- Every affected location is a `range_kind: file` range: 2,968 `from_decl` file ranges and 405 `to_decl` file ranges. **No declaration, site or input range ends on the EOF position.**
- Under strict L2 every affected record turns `rejected` (the L1/L2 rule in `status()`):

| Kind | Status now | Records | Under strict L2 |
|---|---|---:|---|
| `contains` (file to top-level node) | verified | 1,455 | rejected |
| `imports` | verified | 1,213 | rejected |
| file nodes | observed | 152 | rejected |
| `calls` (module-level call sites) | verified | 111 | rejected |
| `references` | verified | 26 | rejected |
| `calls` | unvalidated | 2 | rejected |
| `imports` | rejected | 9 | rejected (reason changes) |
| **Total** | | **2,968** | **2,959 change status** |

So 2,805 of the 4,574 verified edges (61 percent) depend on the leniency, but only through the file-range endpoint, never through the location that carries the evidence.

Proposed rule (spec v3, EVIDENCE_SCHEMA section 4.1, row `file`): let L be `len(text.splitlines())`. A `file` range is `[1, L+1]` when the blob ends in a newline and `[1, L]` when it does not. Line L+1 is the EOF position and is valid only for `range_kind: file`. L2 for every other range kind uses the strict count. L3 for `file` ranges already checks the whole blob hash, which is the real evidence. Coverage reports the number of file ranges that use the EOF position (today 2,968 records).

## R-3. `setOpen` node unvalidated, declaration line 86

My ruling pending Architect1 confirmation: agree with Lab.

TESTED: `frontend/src/components/ui/sidebar.tsx:86` is `const setOpen = React.useCallback(`; lines 87 to 97 are the arrow-function body. CodeGraph reports 87-97. The word `setOpen` does not occur in 87-97 (`setOpenProp` and `_setOpen` do not match a word boundary), so L3 fails on the extractor range. The validator adds the declaration range 86-99. Status `unvalidated` with reason "declaration line differs from extractor line" is right. It is not `rejected`: the node exists, only its line is off.

## R-4. CT8 wording

My ruling pending Architect1 confirmation: Lab's reading is right; the spec wording is wrong.

ADAPTER_CONTRACT v2 CT8 says "1,891 of 1,893 containment records gain locations". In fact R-contains adds a location to all 1,893; 1,891 then pass `syntax_structure` and end `verified`; the 2 exceptions keep their recovered locations and end `unvalidated`. TESTED by rerunning `tests/ct_evaluate.py` on a copy of the run's inputs: `contains_records_with_locations_after_validation` 1,893, `R_contains_syntax_structure_pass` 1,891.

Corrected CT8 text: "Then R-contains adds a location to all 1,893 containment records; 1,891 are `verified` by `syntax_structure`; the 2 known exceptions (`createSseClient` to `abortHandler`; `SidebarProvider` to `setOpen`) keep their recovered locations and end `unvalidated` with the reasons in EVIDENCE_SCHEMA section 7, not `rejected`. Pass: 1,981 `missing_location` from the adapter; 0 rejected; 1,893 with locations after recovery; 1,891 verified; the two exceptions as stated."

## R-5. Limitations: tarball hash and schema checker

My ruling pending Architect1 confirmation.

a) CodeGraph tarball hash. TESTED offline, read-only: the tarball `@colbymchenry/codegraph/-/codegraph-1.6.2.tgz` is in two npm caches (`/home/box/.npm/_cacache` and `lab/tools/gitnexus/home/.npm/_cacache`; not in `task002/tools/home`). Recomputed from the 424,466-byte content: sha512 `hODH/mGn...zUH6Q==` and sha1 `372b7b4f0190197b07d444116d6692240883a2d5`, both equal to the pinned values. The extracted package (265 files) is identical to `task002/tools/node_modules/@colbymchenry/codegraph` (`diff -rq` clean). Limitation closed. Nothing was deleted or moved from either cache.

b) Custom schema checker instead of `jsonschema`. Keep as a stated limitation. `validators/schema_check.py` plus its self-test (`schema_selftest.txt`) is acceptable for Task 002 because it ran on every record and the self-test shows it rejects bad records. For Task 003, validate with a reference JSON Schema implementation pinned by hash, offline, and compare.

## R-6. Housekeeping

My ruling pending Architect1 confirmation: fine as is.

- Debug runs `t002-20261021T1039-dbg1`, `1040-dbg2`, `1040-dbg3`, `1047-1`, `1049-2` stay in `work/`. Nothing deleted. The final run is `1049-3`; `out/` is byte-identical to its `v1/validation/` outputs (TESTED with `cmp`).
- The `.db-shm` mtime change on the index is the SQLite shared-memory file; the index hash is logged. Fine.
- New item, open item O1 (HOME path): TESTED, `tools/offline.sh` exports `HOME=task002/tools/cghome`, an empty directory. `tools/home` holds the setup npm cache. So the wrapper and the netprobe log agree on `cghome`; the ENV.md wording "tools/home" is the inaccurate part. Close O1 as a documentation fix in ENV.md, no rerun needed.

## Erratum to R-5b (2026-10-21, Decision 002-B work)

In run `t002-20261021T1049-3` the schema checker self-test did not run: the command omitted the schema path, `schema_selftest.txt` is empty, and CT5 did not check it. The R-5b statement that the self-test shows bad records rejected was wrong for that run. Corrected in run `t002-20261021T1356-002b-2`: 23 of 23 self-test cases pass, and CT5 now requires it. See `CLOSEOUT_002.md` section 9.
