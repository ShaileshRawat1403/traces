# CodeGraph 1.6.2 adapter contract (Task 002, step 3)

Status: DESK SPEC, draft 1, 2026-10-21 (IST). Owner: Traces. Lab implements the adapter and the 15 contract tests in step 4, after step 1a.
Record format: EVIDENCE_SCHEMA.md and `evidence_record.schema.json`.

## 1. Role and limits

The adapter is Traces-owned code. It reads a CodeGraph SQLite index read-only and writes evidence records. It is the only path by which CodeGraph output enters Traces.

The adapter must not:
- set any record to `verified` (verification belongs to the validators);
- add, drop, merge or re-resolve CodeGraph relationships (no replacement extractor; addendum decision);
- read or write the shared source clone `/workspace/traces-research/_src/full-stack-fastapi-template`;
- use the network, call any LLM, or call the GitHub API.

The contract holds whatever step 1 finds. Step 1 decides only one thing the adapter reads: `codegraph_validator_eligible` (EVIDENCE_SCHEMA.md section 6), default `false`. The adapter writes CodeGraph's claims the same way in both cases.

## 2. Run layout

All paths under `/workspace/traces-research/task002/work/<run_id>/`:

| Path | Made by | Content |
|---|---|---|
| `repo/` | run setup | temporary checkout: `git clone --no-hardlinks <shared clone path> repo` then `git -C repo checkout --detach b1125d8839482cb7bbae603ddc6d0081bf87532e`. Cloning from a local path only reads the source clone. No `git worktree` (it would write into the shared clone's `.git`). |
| `repo/.codegraph/codegraph.db` | CodeGraph `init` and `index`, network off, telemetry off | input to the adapter |
| `manifest.json` | run setup | section 3 |
| `adapter/records.jsonl` | adapter | one evidence record per line, sorted by `claim_id` |
| `adapter/report.json` | adapter | counts (EVIDENCE_SCHEMA.md section 10) and every warning |
| `adapter/errors.json` | adapter on failure | failure code and detail (section 6) |

Lab's step 0 already created `task002/src/fsft` (a checkout) and `task002/tools/offline.sh` (seen by directory listing only, contents not read). Either layout is fine if it meets the same rules: checkout made from the shared clone without writing to it, pinned SHA, clean worktree, network off. Lab records the actual paths in `manifest.json`; the contract tests read paths from the manifest, not from this table.

`repo/` is deleted only by the run's own cleanup and only after records are written. The records do not depend on it: every location carries `blob_sha`, so a reviewer can re-read the source from git.

## 3. Inputs

`manifest.json` (written by Lab at run setup, read by the adapter):

```json
{
  "run_id": "t002-<yyyymmdd>-<hhmm>-<n>",
  "repo": "fastapi/full-stack-fastapi-template",
  "repo_sha": "b1125d8839482cb7bbae603ddc6d0081bf87532e",
  "checkout_path": ".../task002/work/<run_id>/repo",
  "index_path": ".../repo/.codegraph/codegraph.db",
  "codegraph": {
    "package": "@colbymchenry/codegraph",
    "version": "1.6.2",
    "npm_integrity": "<sha512 from step 0 install>",
    "tarball_sha256": "<sha256 of the installed package tarball>",
    "schema_version_max": 11,
    "extraction_version": "27"
  },
  "node_version": "v20.19.2",
  "env": {"telemetry_disabled": true, "network": "blocked"},
  "codegraph_validator_eligible": false
}
```

Expected values for 1.6.2 come from the Task 001 index (read-only): `project_metadata.indexed_with_version = 1.6.2`, `indexed_with_extraction_version = 27`, `schema_versions` max 11, `indexed_at_commit = b1125d88...`, `index_state = complete`, `index_files_discovered = index_files_accounted = 175`. **TESTED** (read of an existing artifact). The integrity hash is not recorded yet; Lab records it at step 0.

## 4. Version pin and integrity check

Before reading any row the adapter checks, in this order, and stops at the first failure:
1. Installed package `version` equals `1.6.2`; package integrity equals `manifest.codegraph.npm_integrity`.
2. `project_metadata.indexed_with_version` equals `1.6.2`.
3. `max(schema_versions.version)` equals 11; `indexed_with_extraction_version` equals `27`.
4. `indexed_at_commit` equals `repo_sha`; `indexed_dirty_paths.paths` is empty; `git -C repo status --porcelain` is empty; `git -C repo rev-parse HEAD` equals `repo_sha`.
5. `index_state` equals `complete`; files discovered equals files accounted.
6. The tables and columns in section 5 exist with the listed names.

## 5. Mapping to evidence records

The adapter reads only these tables and columns (CodeGraph `src/db/schema.sql:20-101`, **VERIFIED-IN-CODE**; matched by the Task 001 index, **TESTED**):

| Table | Columns read |
|---|---|
| `nodes` | `id, kind, name, qualified_name, file_path, language, start_line, end_line, start_column, end_column, decorators` |
| `edges` | `id, source, target, kind, metadata, line, col, provenance` |
| `files` | `path, content_hash, language, generated, errors` |
| `unresolved_refs` | `id, from_node_id, reference_name, reference_kind, line, col, candidates, file_path, status` |
| `project_metadata` | `key, value` |
| `schema_versions` | `version` |

5.1 Files. Each `files` row is checked, not emitted as a claim: `path` must exist at `repo_sha`; `content_hash` must equal sha256 of the blob bytes (observed: `deps.py` hash `84c30966...` equals `sha256sum`, **TESTED**); non-empty `errors` is copied into `report.json` and every record from that file gets flag `extractor_file_errors`. `generated = 1` gives every record from that file the flag `generated_file` (20 files in Task 001, including `frontend/src/client/sdk.gen.ts` and `types.gen.ts`).

5.2 Nodes. One `node` record per row. `class = source_backed_declaration`, `provenance = codegraph:declaration`, `granularity = symbol`, status `unvalidated`. Location: `start_line..end_line`, precision `declaration`, `start_col` and `end_col` as given (0-based observed: `items.py` `create_item` has `start_column = 0`). `range_rule`: `def_to_body_end` for function and method nodes (observed: `create_item` 62..72, so CodeGraph function ranges start at `def`, not the decorator); `declaration_line` for `route` nodes (observed: `route:backend/app/api/routes/items.py:61:POST:/` at line 61, the decorator). Route node names such as `POST /items` are router-local; the adapter copies them into `provenance_raw.route_local_path` and never into a full-path field. Full paths belong to FASTAPI_RULES.md R1.

5.3 Edges. One `relationship` record per row. `relationship_kind` = `edges.kind`. `from` and `to` from the joined nodes. `granularity = symbol`, except `file`-kind source nodes give `file`. Provenance, class and initial status per EVIDENCE_SCHEMA.md section 8. Location:
- `line` not null and no `synthesizedBy`: `site` location at `line`, `col` (0-based), plus `from_decl` and `to_decl` locations from the node ranges.
- `metadata.synthesizedBy` present: `enclosing_scope` location at `line` (observed: `jsx-render` lines equal the enclosing function's start line).
- `line` null: no `site` location; status `missing_location`; `from_decl` and `to_decl` kept in `provenance_raw` for recovery.

`metadata.confidence` and `metadata.resolvedBy` go into `provenance_raw` unchanged.

5.4 Unresolved references. One `unresolved_reference` record per row, `from` = the source node, no `to`, `statement` = `"<from> refers to <reference_name> (<reference_kind>), not resolved by CodeGraph"`, `site` location from `line`, `col`. Example from Task 001: `items.py` `create_item` has 5 such rows at lines 68 to 71 (`Item.model_validate`, `current_user.id`, `session.add`, `session.commit`, `session.refresh`), while it has 0 outgoing edges. **TESTED**. These rows are evidence that CodeGraph saw the call sites; they are not resolved relationships.

5.5 Canonical output. Records sorted by `claim_id`; keys sorted; no timestamps from CodeGraph (`updated_at`, `indexed_at`, `modified_at`) in records; `run_id` and `at` are the only run-varying fields and are excluded from the determinism hash.

## 6. Failure modes

The adapter fails closed: it writes `errors.json`, writes no `records.jsonl`, exits nonzero.

| Code | Condition |
|---|---|
| `E_VERSION` | package version, integrity, indexed version, schema version or extraction version differs from the pin |
| `E_SCHEMA` | a required table or column is missing or renamed |
| `E_SHA` | HEAD, `indexed_at_commit` or manifest SHA differ; dirty worktree; non-empty `indexed_dirty_paths` |
| `E_INDEX_INCOMPLETE` | `index_state` not `complete`, or files discovered differs from files accounted |
| `E_PROVENANCE_UNKNOWN` | a `provenance`, `resolvedBy` or `synthesizedBy` value not in the map |
| `E_DANGLING` | an edge whose `source` or `target` has no node row |
| `E_PATH` | a path not present at `repo_sha`, absolute, or containing `..` |
| `E_HASH` | `files.content_hash` differs from the blob sha256 |
| `E_NETWORK` | an outbound connection attempt during index or adapter steps |
| `E_TELEMETRY` | telemetry not disabled per CodeGraph `TELEMETRY.md` before indexing |
| `E_WRITE_SCOPE` | any write outside `task002/work/<run_id>/` |

Warnings, written to `report.json` without failing: non-empty `files.errors`; `unresolved_refs` count; edges with null line by kind.

## 7. Contract tests (Lab implements in step 4)

Fixtures: the temporary checkout and its index from one run; a second run for CT14; small hand-made SQLite files derived from the real index for the negative cases (CT1, CT2, CT4, CT9). The tests never modify the real index; negative fixtures are copies.

**CT1. Version pin.**
Given a copy of the index with `project_metadata.indexed_with_version` set to `1.6.3`, and separately a manifest with a wrong `npm_integrity`.
When the adapter runs on each.
Then it exits nonzero with `E_VERSION` and writes no records.
Pass: both cases fail with `E_VERSION`; the unmodified index passes check 4.1 to 4.3.

**CT2. Schema drift.**
Given a copy of the index with `edges.provenance` renamed to `prov`, and a copy with table `unresolved_refs` dropped.
When the adapter runs.
Then `E_SCHEMA`, naming the missing column or table.
Pass: both fail with the right name in the detail.

**CT3. SHA binding.**
Given (a) the checkout with one byte changed in `README.md`, (b) the checkout at `HEAD~1`, (c) a manifest with a different `repo_sha`.
When the adapter runs.
Then `E_SHA` in all three.
Pass: 3 of 3 fail; the clean checkout passes.

**CT4. Provenance map is total.**
Given the real index, and a copy with one edge's `metadata.resolvedBy` set to `guess`.
When the adapter runs.
Then on the real index every edge maps to exactly one normalized `provenance` from EVIDENCE_SCHEMA.md section 8, and `provenance_raw` equals the raw row; on the copy, `E_PROVENANCE_UNKNOWN`.
Pass: 0 unmapped edges on the real index; the copy fails.

**CT5. Required fields complete.**
Given adapter output on the real index.
When every record is validated against `evidence_record.schema.json`.
Then 0 schema errors and 0 nulls in `extractor.name`, `extractor.version`, `provenance`, `class`, `status`.
Pass: 100% of records valid.

**CT6. Adapter never verifies.**
Given adapter output on the real index, with `codegraph_validator_eligible` set to `true` and then `false`.
When statuses are counted.
Then 0 records have status `verified` in both runs, and outputs are identical apart from `run_id`.
Pass: count of `verified` is 0 twice.

**CT7. Line and column base.**
Given these declarations, located independently by reading the blob at `repo_sha` (1-based lines):
`items.py` `create_item` def 62, decorator 61; `items.py` `router` 10; `deps.py` `get_db` 21, `SessionDep` 26, `TokenDep` 27, `get_current_user` 30, `CurrentUser` 49, `get_current_active_superuser` 52; `crud.py` `create_user` 10, `create_item` 63; `private.py` `create_user` def 24, decorator 23; `models.py` `Item` 87, `ItemCreate` 76, `ItemPublic` 97; `AddItem.tsx` `AddItem` 40, `onSubmit` 68; `items.tsx` `Items` 57; `sdk.gen.ts` `ItemsService` 287, `createItem` 307.
When the adapter emits their node records.
Then each `start_line` equals the listed line (route nodes equal the decorator line), and `start_col` is 0 for the module-level ones.
Pass: 20 of 20 match.

**CT8. Missing location handled as missing.**
Given the real index.
When the adapter runs.
Then every edge with null `line` is `missing_location`, none is `rejected`, each keeps `from_decl` and `to_decl` ranges in `provenance_raw` for recovery, and `report.json` gives the count by edge kind.
Pass: count equals `select count(*) from edges where line is null` (1,981 in Task 001), 0 of them rejected.

**CT9. Path normalization.**
Given the real index, and a copy with one `nodes.file_path` set to `/abs/path.py` and one set to `../x.py`.
When the adapter runs.
Then on the real index every path is repo-relative POSIX and `git cat-file -e <sha>:<path>` passes; the copies fail `E_PATH`.
Pass: 0 bad paths on the real index; both copies fail.

**CT10. Unresolved references kept.**
Given the real index.
When the adapter runs.
Then the number of `unresolved_reference` records equals the `unresolved_refs` row count (3,314 in Task 001), each with a `site` location, and `create_item` in `items.py` has exactly the 5 records at lines 68 to 71 listed in section 5.4.
Pass: counts equal; the 5 records present.

**CT11. Generated files flagged.**
Given the real index.
When the adapter runs.
Then every record whose location is in a file with `files.generated = 1` carries `generated_file`, including `frontend/src/client/sdk.gen.ts`.
Pass: 0 records from generated files without the flag; 0 records from non-generated files with it.

**CT12. Known relationships present.**
Given the real index.
When the adapter runs.
Then these edge records exist with these site lines: `AddItem` calls `ItemsService::createItem` at `AddItem.tsx:56`; `AddItem` references `onSubmit` at `AddItem.tsx:88`; `route POST /items` (items.py:61) references `create_item`; `CurrentUser` references `get_current_user` at `deps.py:49`; handler `users.py::create_user` calls `crud.py::create_user` at `users.py:68`; handler `login.py::login_access_token` calls `crud.py::authenticate` at `login.py:30`.
Pass: 6 of 6 present. A miss is reported as a CodeGraph finding for step 1a, not fixed in the adapter.

**CT13. Known absence preserved.**
Given the real index.
When the adapter runs.
Then no record has `from` = `backend/app/api/routes/items.py::create_item` and `to` in `backend/app/crud.py`, and the adapter has not synthesized any edge from the 5 unresolved references.
Pass: 0 such records.

**CT14. Determinism.**
Given two fresh temporary checkouts and two index runs at the same SHA with the same manifest.
When the adapter runs on each.
Then sha256 of the canonical `records.jsonl` (with `run_id` and `at` removed) is equal.
Pass: hashes equal. If not equal, the diff is attached and the run stops (stop condition, plan section 8).

**CT15. No network, no telemetry, no writes outside scope.**
Given the index and adapter steps run with outbound network blocked and CodeGraph telemetry disabled.
When the steps run.
Then both complete; the network log shows 0 outbound connections; a file listing before and after shows writes only under `task002/work/<run_id>/`; the shared clone's `git status` and mtime of `.git/index` are unchanged.
Pass: all four facts hold. Lab chooses the network-blocking method at step 0 and records it.

## 8. Open questions

- CT12 rows were checked against the Task 001 index (read-only): all 6 present with the listed site lines and function-level sources. **TESTED**
- **Q4 (Lab, step 0; may need Shailesh).** How network is blocked on the box for CT15 (for example a network namespace or an outbound firewall rule) needs to be decided and may need an approval.
