# Traces v1 contracts

Owner: Architect. Integration branch: `build/traces-v1`. Status of each item: [STATUS.md](STATUS.md). Reasons: [DECISIONS.md](DECISIONS.md).
A change to anything here goes through a PR into `build/traces-v1` that edits this file in the same PR.

Contents: 1 domain model and evidence schema, 2 user labels, 3 store and state machines, 4 REST API, 5 history interface and hook points, 6 ownership, 7 branches and PRs, 8 test contract.

## 1. Domain model and evidence schema

| Entity | Identity | Notes |
| --- | --- | --- |
| Repo | `github.com__<owner>__<name>` (lowercase) | Public GitHub only in v1. Registered from `https://github.com/<owner>/<repo>`; nothing else is accepted. |
| Snapshot | `<repo_id>@<sha>` | One repo at one full 40-hex commit. Every claim, view and source line is pinned to a snapshot. `generated_paths` lists generator-config paths (history's generated filter). |
| Claim (evidence record) | `claim_id` = `c_` + sha256 of the canonical identity (claim_id v3, Task 002) | One JSON record per claim, `traces-evidence/0.4`. Stable across runs at the same SHA. |
| Check | `check_id` = `k_` + 64 hex | A validator run against a claim. Independent checks can promote status; non-independent ones cannot. |
| Component | `component::<name>` | Deterministic output of the evidence/indexing side (rule id recorded). Never produced by an LLM. |
| Job | opaque id | Index, reindex, history, baseline. Polled; see 3.2. |
| Run | opaque id | One pipeline execution and its artifacts directory. |

### 1.1 Schema versions

- `traces-evidence/0.3` (`backend/traces/evidence/schema/evidence_record.v0.3.schema.json`) is the frozen Task 002 format. The verification pipeline still emits 0.3 so its output stays byte-comparable with the Task 002 closeout hashes (D-004).
- `traces-evidence/0.4` (`evidence_record.v0.4.schema.json`) is the store and API format. It is generated from 0.3 by `backend/traces/evidence/schema/build_v04.py`; a test fails if the committed file differs from the generator output.
- Migration: `traces.evidence.migrate.to_current()`. 0.3 to 0.4 changes `schema_version`, sets `migrated_from`, gives `rejected` records the label `rejected`, and adds the flag `no_source_location` to `missing_location` records. `claim_id`, checks, status and class are untouched. Tested over all 10,016 evidence and 9,998 adapter records of the baseline run with both the stdlib checker and `jsonschema`.

### 1.2 What 0.4 adds

| Area | 0.4 |
| --- | --- |
| Extensibility | `relationship_kind`, `granularity`, `flags` and check `method` accept registered values or `x-<name>` extensions. `status`, `label`, `class` and `evidence_scope` are closed. Provenance namespaces: `codegraph:`, `external:`, `fixture:`, `git:`, `history:`, `github-cache:`, `x-<ns>:`. |
| Scope | `evidence_scope`: `static` (code at the SHA), `history` (Git objects and statistics over them), `documented` (quoted PR or commit text). |
| Classes | 0.3 classes plus `git_object_fact`, `history_pattern`, `history_inferred`, `documented_rationale`, `snapshot_diff`. |
| Endpoints | Optional `entity`: `symbol`, `file`, `commit`, `component`, `dependency`, `repo`. `file` is required for `symbol`/`file` (or no entity). Symbol forms `commit::<sha>`, `file::<path>`, `component::<name>`, `dep::<eco>:<manifest>:<name>`, `repo::<owner>/<name>[#pr]`. |
| New fields | `citations` (commit, parents, paths with old_path/status/similarity/blob_before/blob_after, optional `pr`), `parameters` (`digest` + `values`), `metrics`, `review_state` (`none`/`confirmed`/`disputed`, reviewer, at; never changes status), `migrated_from`. |
| Origin | `origin.kind` adds `git_object`, `history_derived`, `cached_pr` (`artifact`, `sha256`, `quote` required). Originator `role: history_analyzer`. |
| Check methods | adds `git_object_check`, `git_recount`, `quote_match` (validator families `git`, `text`). |

### 1.3 Status rules (enforced by the schema's `allOf`, 22 rules)

| Rule | Effect |
| --- | --- |
| `verified` | Only with `evidence_scope: static` and an independent passing check with source locations (Task 002 rules unchanged). History and documented records can never be verified. |
| Git object facts (`git_object_fact`) | Max `observed`, with a qualifier and an independent passing `git_object_check` or `git_recount`. `claim_id` anchors to the commit. |
| Co-change, hotspot, churn statistics (`history_pattern`) | Max `observed` under the recorded `parameters` (required). Never `verified`. Statements say "pattern, not causation". |
| `history_inferred` (alias suggestions, etc.) | Never `observed`; `unvalidated` with label `inferred`, or `rejected`. |
| Commit/PR text (`documented_rationale`) | Only `evidence_scope: documented`; `observed` only as a quote (`quote_match` passes against the cached artifact), never as proof of intent. |
| Locations vs citations | Static records need at least one location unless `missing_location`. History/documented records need at least one citation; `locations` may be empty. |
| `missing_location` | Label stays the claim's own (`inferred`), plus flag `no_source_location`. Never `verified`. |
| `rejected` | Label `rejected`. Kept in the store; hidden by default in graph, trace and claim lists. |
| `review_state` | Annotation only. Never promotes or demotes. |

## 2. User-facing labels

| Status | Label shown | Where |
| --- | --- | --- |
| `verified` | Verified | everywhere |
| `observed` | Observed | everywhere; history and documented claims show their qualifier ("changed together in 18 of 19 commits", "quoted rationale, not proof of intent") |
| `unvalidated` | Inferred | everywhere, with the status reason in the evidence drawer |
| `missing_location` | Inferred + "no source location" | everywhere; never Verified |
| `rejected` | Rejected | reviewer view (`/review`) and the evidence drawer only; never "Inferred" (amends the 0.3 mapping) |

Gap and library_contract trace hops are shown as Inferred with their reason. Every analysis view carries "Static analysis only. No runtime behavior has been observed."

## 3. Store and state machines

SQLite at `$TRACES_DATA_DIR/traces.sqlite3` (default `.traces-data/`). Migrations are numbered SQL files applied in order and recorded in `schema_migrations`. Ranges: `0001`-`0099` evidence/ingest/API (Traces), `0100`-`0199` history (Traces History), `0200`-`0299` explain (Traces UI). A duplicate number fails at startup.

### 3.1 Tables (migration 0001)

| Table | Purpose |
| --- | --- |
| `repos` | id, host, owner, name, url, visibility (`public` only), latest discovered SHA and time, default branch; 0002: `visibility_checked_at`, `external_ai_consent` (D-021); 0003: `external_ai_consent_at`, `external_ai_consent_text_version` (D-027) |
| `snapshots` | id, repo_id, sha, state (`pending`/`indexing`/`ready`/`failed`), evidence_schema, extractor pins, languages, frameworks, `generated_paths`, stats; 0003: `isolation` (`unshare`/`off`, D-026) |
| `jobs` | id, repo, snapshot, kind, state, phase, progress, message, error code/detail, `version` (ETag), timestamps |
| `job_events` | append-only progress log per job |
| `runs` | pipeline runs per snapshot with their run directory and result |
| `claims` | one row per claim: indexed columns (status, label, class, scope, kind, endpoints, injected) plus the full 0.4 `record_json` |
| `claim_locations` | file/line ranges per claim (source view overlap queries) |
| `components` | deterministic components per snapshot: layer, kind, paths, rule; `record_json.reason` (D-029) |

Export: `GET .../export` or `Store.export_jsonl()` writes one 0.4 record per line sorted by `claim_id`, with a manifest (counts by status, schema and store version).

### 3.2 Job and index state machine

```
queued -> running -> succeeded
   |         |----> failed
   |         `----> cancelled
   `-> failed | cancelled
```

Phases while running: `fetching`, `checking_out`, `indexing`, `adapting`, `validating`, `storing`, `history`, then `done` or `failed`. Progress is monotonic in [0, 1]. Every update increments `version`, appends a `job_events` row and is visible to pollers. Terminal states are final; a reindex is a new job. Snapshot state follows: `pending` on job creation, `indexing` while running, `ready` after `storing`, `failed` on failure. Enforced in `traces.evidence.store.update_job` (tested).

The index worker (milestone INDEX) runs: validate URL, resolve SHA, `ensure_pinned_checkout` (hardened git: hooks off, symlinks off, protocol allowlist, LFS off), then CodeGraph, adapter, validators and store, each inside `workers/sandbox.sh` (no network via `unshare -rn`, credentials stripped, CPU/file/fd limits). The target repo's code, hooks, installs and tests are never run.

## 4. REST API

Base path `/api/v1`. JSON. Read-only except repo registration and job creation. Generated OpenAPI: [contracts/openapi.json](contracts/openapi.json); a test fails if it is stale, and the UI's TypeScript types are generated from it (`web/src/api/schema.d.ts`, `npm run check:api`).

Errors use one envelope: `{"error": {"code", "message", "owner", "milestone", "detail"}}`. Codes: `invalid_request` (422), `invalid_repo_url` (422), `invalid_sha` (422), `not_found` (404), `not_implemented` (501, with the owning seat and milestone); ingest (D-021): `repo_not_public`, `repo_empty`, `sha_not_found` (422), `too_large`, `too_many_files` (413), `rate_limited` (429, `Retry-After`), `upstream_unavailable`, `fetch_failed` (502), `fetch_timeout` (504). Stubs never return placeholder data.

`S` = `/repos/{repo_id}/snapshots/{sha}`.

| # | Method and path | Purpose | Build status |
| --- | --- | --- | --- |
| 4.1 | `GET /health`, `GET /meta` | liveness, versions, schema, pins, isolation mode, capability flags | implemented |
| 4.2 | `POST /repos` `{url, sha?}` | validate, confirm public with an anonymous `ls-remote`, register, pin a `pending` snapshot at `sha` or HEAD (no clone; D-021) | implemented |
| | `GET /repos`, `GET /repos/{id}` | list, get | implemented |
| | `PUT /repos/{id}/ai-consent` `{consent, consent_text_version}` | record or revoke repo-level consent to send evidence to an external AI provider, with time and consent-text version (D-027) | implemented |
| | `GET /repos/{id}/head` | latest discovered HEAD vs displayed snapshot (`behind`); cached 60 s, rate limited | implemented |
| 4.3 | `GET /repos/{id}/snapshots`, `GET S` | snapshots and metadata | implemented |
| 4.4 | `POST /repos/{id}/index-jobs` `{sha?, reindex}` | start index job (202 + Job, `Location`); active job for the same snapshot is returned; ready snapshot without `reindex` -> 409 `already_indexed` (D-022) | implemented |
| | `GET /jobs/{job_id}` | poll; `ETag` = job version, `If-None-Match` gives 304; poll 1-2 s; no SSE | implemented |
| 4.5 | `GET S/overview` | business / architecture / implementation facts, each tagged fact, interpretation or unknown, with claim ids | implemented (D-024). Purpose is unknown unless a README heading is quoted as interpretation |
<<<<<<< HEAD
| 4.6 | `GET S/components` | deterministic components and layers with claim counts | implemented (D-024). Rows are what the index stored |
| 4.7 | `GET S/routes` | route and API inventory with status and claim ids | implemented (D-024). Method is UNKNOWN when the record does not carry one. An Express-style `app.use()`/`router.use()` mount is method `USE` with flag `mount`, not an operation (D-031). Limit (O-7): paths of routers mounted in a computed way (e.g. `forEach` over an array of `{path, route}`) are not prefixed with the mount path; only literal mounts are composed by the extractor |
=======
| 4.6 | `GET S/components` | deterministic components and layers with claim counts; `reason` per component (counted files and rule behind the layer; null for rows stored before D-029); layer `library` for a repository that declares a package and has no application framework or entrypoint (D-029) | implemented (D-024). Rows are what the index stored |
| 4.7 | `GET S/routes` | route and API inventory with status and claim ids; optional `label` = the route name exactly as the extractor recorded it (null when none, never synthesized) | implemented (D-024). Method is UNKNOWN when the record does not carry one |
>>>>>>> origin/build/traces-v1
| 4.8 | `GET S/graph?focus&depth&layer&rel&status&q&include_rejected&limit` | filtered graph or neighborhood (`focus`, `depth` 0-4); static relationships only; `hidden_counts` by status (scoped to filters and focus, D-028); `truncated`, `truncated_counts` by status | implemented (D-024). History patterns are not edges here |
| 4.9 | `GET S/claims?status&claim_kind&kind&symbol&file&include_rejected&offset&limit` | claim list; rejected excluded unless `include_rejected=true`; `hidden_counts` | implemented |
| | `GET S/claims/{claim_id}` | evidence by claim: full 0.4 record (locations, checks, status history, provenance, citations) | implemented |
| | `GET S/export` | NDJSON export of all 0.4 records | implemented |
| 4.10 | `GET S/source?path&start&end` | source lines at the SHA from Git objects, blob SHA, `generated`, overlapping claim ids | implemented (D-024). 422 `invalid_request` if the path escapes the tree or the range exceeds 400 lines. 404 if the checkout or blob is absent |
<<<<<<< HEAD
| 4.11 | `GET S/trace?from&to&include_rejected` | ordered `hops`: `edge` (claim), `gap` (no claim; inferred, reason required), `library_contract` (inferred, reason required); `complete=false` when gaps exist; `hidden_counts`. A step with outgoing calls stored only as unresolved references gets a `gap` hop with `unresolved_calls`; an `edge` hop that is not verified or observed also makes `complete=false`; `incomplete_reasons` says why (D-031) | implemented (D-024). Rejected claims are not used as bridges |
=======
| 4.11 | `GET S/trace?from&to&include_rejected` | ordered `hops`: `edge` (claim), `gap` (no claim; inferred, reason required), `library_contract` (inferred, reason required); `complete=false` when gaps exist; `hidden_counts`; each `gap` hop's reason states how many outgoing static relationships of that step are hidden, by status, and `hidden_rejected` gives the rejected count (D-029) | implemented (D-024). Rejected claims are not used as bridges |
>>>>>>> origin/build/traces-v1
| 4.12 | `GET S/history/timeline`, `/lifecycle?path`, `/hotspots?level`, `/cochange?target&level`, `/milestones`, `/rationale?target`; `GET /repos/{id}/compare?base&head` | history views over history records (0.4 `evidence_scope` history/documented). Compare returns stored `snapshot_added` / `snapshot_removed` when history wrote them, otherwise an identity diff of static claims that already exist on the two snapshots (their own kinds, not new records) | implemented (D-024) |
| 4.13 | `POST S/explain` `{question, focus_claim_ids, mode}` | `no_llm`: deterministic answer from evidence with citations and categories (code structure, history patterns, documented decisions, inference, runtime observations). `prepare_bundle`: scoped prompt bundle + `outbound_manifest` (what would leave the browser, with sha256 per item); `requires_consent: true` | implemented (D-023), Traces UI, EXPLAIN |
| | `POST S/chat/bundle` | same bundle for a chat turn | implemented (D-023) |

BYOK: provider keys never reach the backend. The browser holds the key, shows the outbound manifest, asks for consent and calls the provider directly. Request models forbid extra fields, so a request carrying `api_key` is refused with 422 (tested).

Rejected claims: graph, trace and claim lists exclude them by default and report them in `hidden_counts`; `include_rejected=true` is the reviewer view. A deep link to a rejected claim id returns it.

## 5. History interface and hook points

The history module's contract is [docs/contracts/history.md](contracts/history.md), written and owned by Traces History (merged from PR #3). This document only links it and fixes the hook points; the stand-in signatures are in `backend/traces/history/interface.py`.

| Hook | Direction | Contract |
| --- | --- | --- |
| H1 | index worker -> history | `HistoryRunner.run(repo=HistoryRepoRef(path, repo, sha), config=..., budget=..., components=..., evidence_sets=..., pr_provider=..., cache_dir=...)` with a full-history clone made by `traces.ingest.fetch` and a pinned SHA; `config` (`HistoryConfig`) and `budget` (`RunBudget`) default to the runner's own. Concrete runner: `traces.history.GitHistoryRunner(config, budget, max_milestones=8)`, or the function `traces.history.run(repo, config, budget=...)`. Returns `HistoryResult(records, report)`; records are 0.4 with `evidence_scope` history or documented; report is `traces-history-run/1` with per-stage status and partial flags (docs/contracts/history.md section 8.11). |
| H2 | evidence -> history | `traces.evidence.types.ComponentMap` (deterministic, with digest) for the snapshot SHA. |
| H3 | history -> index worker | `select_milestones()` returns up to 8 SHAs (20 on demand). The worker runs the evidence pipeline at each and passes `{sha: EvidenceSet}` back through `evidence_sets`. |
| H4 | API/ingest -> history | `PrContextProvider.get(pr_number) -> CachedPr`. The GitHub client, token, cache and rate limits live in the API/ingest layer; history never touches the network or a token. |

History owns its hardened git runner (`backend/traces/history/gitcmd`). Shared record types (`EvidenceRecord`, `EvidenceSet`, `ComponentMap`) live in `traces.evidence` (Traces seat). History store tables use migrations 0100-0199.

## 6. Ownership

| Seat | Owns |
| --- | --- |
| Traces | `backend/traces/evidence` (schema, migrations, store, pipeline), `adapter`, `validators`, `ingest`, `core`, `api` (endpoints and models), `workers/`, `toolchain/` |
| Traces History | `backend/traces/history` (including `gitcmd`), [`docs/contracts/history.md`](contracts/history.md), history migrations 0100-0199 |
| Traces UI | `web/`, `backend/traces/explain`, explain migrations 0200-0299 |
| Traces Lab | `tests/e2e` (Playwright), CI workflow, security tests, second-repo acceptance |
| Architect | `docs/CONTRACTS.md`, `docs/DECISIONS.md`, `docs/STATUS.md`, integration branch, merges into `build/traces-v1` |

A seat changes another seat's area only through a PR that the owner approves. The API surface (`api/models.py`, `openapi.json`) is changed by Traces; a UI or History request for a field goes to Traces with the OpenAPI diff.

## 7. Branches and PRs

- Integration branch `build/traces-v1`, branched from `main`. Never merged to `main` without the owner's decision; the draft PR "Traces v1 (integration, do not merge)" tracks it.
- Seat work: `ws/<seat>-<topic>` off `build/traces-v1` (e.g. `ws/history-gitcmd`, `ws/ui-graph-view`), PR into `build/traces-v1`.
- No force-push, no history rewrite on shared branches. Commits state their validation (commands and counts).
- A PR that changes the API regenerates `docs/contracts/openapi.json` and `web/src/api/schema.d.ts` in the same PR.

## 8. Test contract

pytest is the runner (`pyproject.toml`). The 16 contract tests (CT1-CT16) and 8 regression tests (RT1-RT8) from Task 002 run against a fresh or reused baseline run and must stay green; mapping in [TEST_MAPPING.md](TEST_MAPPING.md). Baseline numbers that must reproduce: 4,642 edges = 4,538 verified + 36 observed + 59 unvalidated + 9 rejected; 12 rejected records overall; adapter canonical sha256 `45600280...` for all three index copies; validation canonical `73db432b...` for both validation passes.
