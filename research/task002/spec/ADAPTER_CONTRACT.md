# CodeGraph 1.6.2 adapter contract (Task 002, step 3), version 2, with Decision 002-B amendments (CT4, CT5, CT10, CT15 indexer evidence for runs that reuse an index)

Status: DESK SPEC v2, 2026-10-21 (IST). Owner: Traces. Lab implements the adapter and contract tests CT1 to CT16 in step 4.
Record format: EVIDENCE_SCHEMA.md v2 and `evidence_record.schema.json` (`traces-evidence/0.2`). Decisions: DECISIONS.md.

## 1. Role and limits

CodeGraph 1.6.2 is accepted as the pinned **structural extractor only**: not a validator, not a reasoning engine, not a source of truth (D-002A.2). The adapter is Traces-owned code that reads CodeGraph's SQLite index read-only and writes evidence records. It is the only path by which CodeGraph output enters Traces.

The adapter must not:
- set any record to `observed` or `verified`; every CodeGraph record leaves the adapter with label `inferred`;
- add, drop, merge or re-resolve relationships (no replacement extractor); the only rewrite is the kind mapping `calls` with `synthesizedBy: jsx-render` to `renders` (D-002A.4), with the raw kind kept; and, from Decision 002-B ruling 2, the consolidation of exact duplicate rows into one record that keeps every contributing row (section 11.2 of EVIDENCE_SCHEMA);
- promote file-level reach (for example `impact` output) to a handler-level claim;
- read injected negative controls or write into the injected set (CT16);
- write to the shared source clone, use the network, call any LLM or the GitHub API, start the target app.

## 2. Run layout

| Path | Content |
|---|---|
| `task002/src/fsft/` | temporary checkout made by Lab at step 0 from the shared clone, clean at `b1125d8839482cb7bbae603ddc6d0081bf87532e`; only `.codegraph/` untracked. The shared clone `/workspace/traces-research/_src/full-stack-fastapi-template` is never written. |
| `task002/src/fsft/.codegraph/codegraph.db` | CodeGraph index, built under `task002/tools/offline.sh` |
| `task002/tools/offline.sh` | isolation wrapper (section 9) |
| `task002/work/<run_id>/manifest.json` | section 3 |
| `task002/work/<run_id>/adapter/records.jsonl` | evidence records, sorted by `claim_id` |
| `task002/work/<run_id>/adapter/report.json` | counts and warnings |
| `task002/work/<run_id>/adapter/errors.json` | on failure only |
| `task002/work/<run_id>/netprobe.log` | per-run isolation proof (section 9) |

Lab may change paths; the manifest records the actual ones and the tests read paths from the manifest.

## 3. Inputs (`manifest.json`)

```json
{
  "run_id": "t002-<yyyymmddThhmm>-<n>",
  "repo": "fastapi/full-stack-fastapi-template",
  "repo_sha": "b1125d8839482cb7bbae603ddc6d0081bf87532e",
  "checkout_path": "/workspace/traces-research/task002/src/fsft",
  "index_path": "/workspace/traces-research/task002/src/fsft/.codegraph/codegraph.db",
  "codegraph": {
    "package": "@colbymchenry/codegraph",
    "version": "1.6.2",
    "npm_integrity": "sha512-hODH/mGnCf3IUMs6rzktv/zbecJIKJfdZAYHZ9mqecb0G7ZkHaA8CZafDVnswANFEL1YFcG+lfAwc5SIXzUH6Q==",
    "npm_shasum": "372b7b4f0190197b07d444116d6692240883a2d5",
    "schema_version_max": 11,
    "extraction_version": "27"
  },
  "wrapper": {"path": "task002/tools/offline.sh", "sha256": "<sha256 at run time>"},
  "env": {"telemetry_disabled": true, "isolation": "unshare -rn", "netprobe_log": "<path>"}
}
```

Pins come from `task002/ENV.md`. Expected index metadata (Task 001 and Lab step 1): `indexed_with_version 1.6.2`, `indexed_with_extraction_version 27`, schema max 11, `indexed_at_commit` = `repo_sha`, `index_state complete`, files discovered = accounted = 175.

## 4. Pin and integrity checks

In order, stop at the first failure:
1. Installed package `version` 1.6.2; package integrity and shasum equal the manifest.
2. `project_metadata.indexed_with_version` = `1.6.2`.
3. `max(schema_versions.version)` = 11; extraction version `27`.
4. `indexed_at_commit` = `repo_sha`; `indexed_dirty_paths.paths` empty; `git status --porcelain` shows nothing except `?? .codegraph/`; `git rev-parse HEAD` = `repo_sha`.
5. `index_state` = `complete`; discovered = accounted.
6. Tables and columns of section 5 exist.
7. The run's `netprobe.log` exists and shows the denials of section 9.

## 5. Mapping to evidence records

Columns read (`src/db/schema.sql:20-101`): `nodes(id, kind, name, qualified_name, file_path, language, start_line, end_line, start_column, end_column, decorators)`; `edges(id, source, target, kind, metadata, line, col, provenance)`; `files(path, content_hash, language, generated, errors)`; `unresolved_refs(id, from_node_id, reference_name, reference_kind, line, col, candidates, file_path, status)`; `project_metadata(key, value)`; `schema_versions(version)`.

Every record: `originator = {name: codegraph, version: 1.6.2, role: extractor}`, `injected: false`, `evidence_scope: static`, `label: inferred`.

5.1 Files: checked, not emitted. Path must exist at `repo_sha`; `content_hash` must equal sha256 of the blob bytes; non-empty `errors` copied to `report.json` and flag `extractor_file_errors`; `generated = 1` gives flag `generated_file` (20 files, including `frontend/src/client/sdk.gen.ts` and `types.gen.ts`).

5.2 Nodes: `node` records, class `source_backed_declaration`, provenance `codegraph:declaration`, status `unvalidated`. Location `source: originator`, `range_kind: declaration` with the range CodeGraph gives (function nodes start at `def`; route nodes at the decorator). Where the frozen checker shows the range is a body (`setOpen`), the adapter does not fix it; the validator appends the declaration (EVIDENCE_SCHEMA 4.1). Route names such as `POST /items` are router-local and go into `provenance_raw.route_local_path` only.

5.3 Edges: `relationship` records, provenance and class per EVIDENCE_SCHEMA section 8.
- `line` set, no `synthesizedBy`: `site` location at `line`, `col`, plus `from_decl` and `to_decl`.
- `synthesizedBy: jsx-render`: `relationship_kind: renders`, `enclosing_scope` location at `line` (Lab: line = the component's `function` line on every heuristic JSX edge).
- other `synthesizedBy`: `enclosing_scope`.
- TanStack route-to-component edges whose line is `createFileRoute`: `enclosing_scope` (Lab step 1: 8 such edges).
- `line` null: status `missing_location`; node ranges kept in `provenance_raw` for recovery.

5.4 Unresolved references: `unresolved_reference` records, class `source_backed_declaration`, provenance `codegraph:unresolved`, `site` location. Example: `items.py` `create_item` has 5 (lines 68 to 71: `Item.model_validate`, `current_user.id`, `session.add`, `session.commit`, `session.refresh`) and 0 outgoing edges.

5.5 Canonical output: sorted by `claim_id`, keys sorted, no CodeGraph timestamps; `run_id` and `at` excluded from the determinism hash.

## 6. Failure modes (fail closed: `errors.json`, no records, nonzero exit)

| Code | Condition |
|---|---|
| `E_VERSION` | version, integrity, shasum, indexed version, schema or extraction version differs |
| `E_SCHEMA` | required table or column missing or renamed |
| `E_SHA` | HEAD, `indexed_at_commit` or manifest SHA differ; tracked changes; non-empty dirty paths |
| `E_INDEX_INCOMPLETE` | index state not complete; discovered not equal to accounted |
| `E_PROVENANCE_UNKNOWN` | unmapped `provenance`, `resolvedBy` or `synthesizedBy` |
| `E_DANGLING` | edge endpoint with no node row |
| `E_PATH` | path absent at SHA, absolute, or containing `..` |
| `E_HASH` | `content_hash` differs from blob sha256 |
| `E_ISOLATION` | no per-run probe log, a probe connected, or a process ran outside the wrapper's net namespace |
| `E_TELEMETRY` | telemetry not disabled |
| `E_WRITE_SCOPE` | write outside `task002/src/fsft/.codegraph/` and `task002/work/<run_id>/` |
| `E_INJECTED` | adapter input or output contains an injected claim |

## 7. Contract tests

Negative cases use copies of the index; the real index is never modified. Expected values below are from Lab step 1 and the 6.0.3 recheck.

**CT1. Version pin.** Given a copy with `indexed_with_version = 1.6.3`, and a manifest with a wrong integrity. When the adapter runs. Then `E_VERSION`, no records. Pass: both fail; the real index passes checks 4.1 to 4.3.

**CT2. Schema drift.** Given a copy with `edges.provenance` renamed and a copy without `unresolved_refs`. Then `E_SCHEMA` naming the missing item. Pass: both fail with the right name.

**CT3. SHA binding.** Given (a) one tracked byte changed, (b) HEAD at `HEAD~1`, (c) a manifest with another SHA. Then `E_SHA`. Pass: 3 of 3 fail; clean checkout passes. The test makes these changes on a separate throwaway copy, never on `task002/src/fsft` or the shared clone.

**CT4. Provenance map is total.** Given the real index, and a copy with one `resolvedBy` set to `guess`. Then every real edge maps to exactly one normalized value with `provenance_raw` equal to the row; the copy gives `E_PROVENANCE_UNKNOWN`. Pass: 0 unmapped; 616 records with `codegraph:name-match`, all class `analyzer_inference` (renamed by D-002B.5).

**CT5. Required fields.** Given adapter output. When validated against `evidence_record.schema.json`. Pass: 100% valid, 0 nulls in required fields, and (D-002B) the schema checker self-test ran and every case passed. In run t002-20261021T1049-3 the self-test command lacked the schema path, produced an empty file, and CT5 did not check it; corrected from run t002-20261021T1356-002b-2.

**CT6. Adapter never establishes.** Given adapter output. Then 0 records with status `observed` or `verified`; 100% with label `inferred`. Pass: counts 0, 0 and 100%.

**CT7. Line base and range kind, frozen checker.** Given `line_checker_v1.0.0` `--mode parser` (`task002/checker/`, sha256 values in DECISIONS.md). When it runs over the adapter's function, method and route node records in `backend/app` and `frontend/src`. Then 378 of 379 start lines match, and the one miss is `sidebar.tsx` `setOpen` (CodeGraph 87 to 97 = body; declaration 86). The `--mode lab_route` (351) and original `check_lines.py` (320) figures are also logged for audit. Pass: exactly 378, the miss is `setOpen`, and its record carries a validator `declaration` location at 86 with flag `extractor_location_is_body` after validation. Any other count is reported as a regression, not re-scored.

**CT8. Missing location and recovery.** Given the real index. Then every edge with null line is `missing_location` (1,981: 1,893 `contains`, 88 `references`), none `rejected`. When R-contains runs (validators only). Then 1,891 of 1,893 containment records gain locations and the 2 known exceptions (`createSseClient` to `abortHandler`; `SidebarProvider` to `setOpen`) end `unvalidated` with the reasons in EVIDENCE_SCHEMA section 7, not `rejected`. Pass: 1,981; 0 rejected; 1,891; the two exceptions as stated.

**CT9. Path normalization.** Given the real index and copies with an absolute and a `../` path. Pass: 0 bad paths on the real index; both copies `E_PATH`.

**CT10. Unresolved references kept.** Pass: unresolved records plus the extra rows held in `consolidation` = row count (3,314) (D-002B.2: 34 exact duplicate pairs consolidate, 3,280 records), each with a `site` location; `items.py::create_item` has exactly the 5 records at lines 68 to 71.

**CT11. Generated files flagged.** Pass: 0 records from `generated = 1` files without `generated_file`; 0 others with it.

**CT12. Known relationships present (as inferred).** Then these records exist, label `inferred`: `AddItem` calls `ItemsService::createItem` at `AddItem.tsx:56`; `AddItem` references `onSubmit` at `AddItem.tsx:88`; route `POST /items` (`items.py:61`) references `create_item`; `CurrentUser` references `get_current_user` at `deps.py:49`; `users.py::create_user` calls `crud.py::create_user` at `users.py:68`; `login.py::login_access_token` calls `crud.py::authenticate` at `login.py:30`; `Items` renders `AddItem` (kind `renders`, `enclosing_scope` at `items.tsx:57`). Pass: 7 of 7 present with these kinds and lines. A miss is a CodeGraph finding, not an adapter fix.

**CT13. Known absence preserved.** Then no record from `items.py::create_item` to anything in `crud.py`; no handler-level `depends_on` record of any kind (CodeGraph makes none); no record synthesized from unresolved references or from `impact` output. Pass: 0, 0, 0.

**CT14. Determinism.** Given two index runs at the same SHA, each under the wrapper. Then sha256 of canonical `records.jsonl` (without `run_id`, `at`) is equal. Pass: equal; otherwise stop and attach the diff.

**CT15. Isolation of the indexer and all child processes, telemetry off, write scope.** (D-002B: a run that reuses an earlier index, without extraction, takes the indexer evidence from that run's log, copied as `netprobe_index_reused.log`, and checks the indexer processes against that run's wrapper namespace; probe (a) to (e) still runs fresh.) Given the index and adapter steps run under `task002/tools/offline.sh` (`unshare -rn`, D-Q5, D-002A.6).
When each run starts, a probe runs inside the same wrapper invocation, before the indexer, from a child process the wrapper spawned: (a) `ip link` shows only `lo`, DOWN; (b) `sh -c 'curl ... https://registry.npmjs.org/'` fails (exit 6) and `curl https://1.1.1.1/` fails (exit 7); (c) the bundled Node 24.16.0 (`codegraph-linux-x64/node`) spawns a child via `child_process` and makes direct `https` and `net` connections, all denied; (d) the net namespace id of the wrapper shell, each probe child and the indexer process is logged and is the same and differs from the outer shell's; (e) the same probe set runs outside the wrapper as a control and connects.
Then the run proceeds only if (a) to (e) hold; otherwise `E_ISOLATION`, the run stops and is reported. Environment variables (`CODEGRAPH_TELEMETRY=0`, `DO_NOT_TRACK=1`, `CODEGRAPH_NO_DOWNLOAD=1`) are required for telemetry but do not count as isolation.
Also: a file listing before and after shows writes only in the allowed scope; the shared clone's `git status` and `.git/index` mtime are unchanged.
Pass: all hold, probe and output logs kept with the run. Accepted reference evidence: `task002/logs/netprobe.log`, sections for the basic probe (10:04 IST) and `CHILD-PROCESS ISOLATION PROBES` (10:08 IST): fresh namespace per wrapper run shared by children (for example `net:[4026532230]` for parent and child; outer `net:[4026531840]`), `sh -c curl`, Node 24.16.0 `child_process`, direct `https` and `net` all denied, control connects.

**CT16. Injected claims stay out of the extractor path (D-002A.8).** Given the injected set (N1, N2) in its own file under `task002/work/<run_id>/validator_inputs/`. When the adapter runs and the index is built. Then the injected file is not read by the adapter; the index and `records.jsonl` contain no record with `injected: true`; the target checkout has no new or changed file. Pass: 0 injected records in adapter output; checkout unchanged; injected records appear only in the validation output, with `injected: true`.

## 8. What the adapter hands to validation

`records.jsonl` (all `inferred`), plus `report.json`. Validation (step 7) adds checks with families `cpython-ast` and `typescript-compiler` only, and the expected-chain fixture and injected set are added there, not here.

## 9. Isolation (D-Q5, D-002A.6)

- Accepted mechanism: OS-level `unshare -rn` via `task002/tools/offline.sh`. Container `--network none` would also be OS-level; not used here.
- Not accepted as isolation: environment variables, app or tool config, proxy settings.
- Proof per run: CT15 (a) to (e), logged to `task002/work/<run_id>/netprobe.log` and kept with the run's output logs.
- Telemetry stays off on every run.
- If isolation cannot be shown, that run stops, nothing from it is used, and the failure is reported.
