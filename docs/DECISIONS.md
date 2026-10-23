# Decisions (Traces v1)

Each entry: decision, reason, and what would change it. Times IST. Architect owns this file; seats propose entries by PR.

## D-001 Stack
Python on uv (CPython 3.14), FastAPI as a read-only query/index API, SQLite store with versioned migrations and JSON export, indexing and history in sandboxed worker subprocesses, CodeGraph `@colbymchenry/codegraph@1.6.2` pinned by integrity behind the fail-closed adapter, web on Vite + React + TypeScript with Cytoscape.js, Playwright e2e and GitHub Actions on free hosted runners. Reason: Architect's call (charter section 7); Python 3.14 is required because the Python validator parses the target with CPython 3.14 `ast`. Change only with a written reason here.

## D-002 Python 3.14.8 exactly
`.python-version` and CI pin 3.14.8 (`requires-python >=3.14,<3.15`). Reason: validator results depend on the `ast` of the running interpreter; the Task 002 baseline was produced on 3.14.

## D-003 License: MIT
Shailesh chose MIT. `LICENSE` (Copyright (c) 2026 Shailesh Rawat) is on `build/traces-v1`, and `license = "MIT"` is set in `pyproject.toml`, `web/package.json` and `toolchain/package.json`. Third-party notices: [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md). No GitNexus code or artifacts; no GPL Code Maat code.

## D-004 Pipeline emits 0.3, store and API use 0.4
The ported verification pipeline keeps emitting `traces-evidence/0.3` so its canonical hashes stay equal to the Task 002 closeout (`45600280...`, `73db432b...`), which is the strongest proof the port is faithful. `traces.evidence.migrate` converts to 0.4 on import; tests prove every baseline record migrates to a valid 0.4 record. Revisit when the pipeline is next changed on purpose: then emit 0.4 directly and re-freeze the hashes in the same PR.

## D-005 Schema 0.4 is generated from 0.3
`build_v04.py` derives 0.4 from the frozen 0.3 schema (steering decision (a) plus the approved History requests in history.md section 5). Reason: the 0.3 rules stay byte-identical inside 0.4, wrapped by scope; a test fails if the committed schema drifts from the generator. `status`, `label`, `class` and `evidence_scope` are closed enums; kinds, granularity, flags and check methods accept `x-` extensions. `review_state.reviewer`/`at` are nullable to match history.md's `none` state.

## D-006 Sandbox limits and the isolation fallback
`workers/sandbox.sh` runs the indexer and adapter with `unshare -rn` (no network), HOME and telemetry overridden, token/secret environment variables removed, and `ulimit` CPU 1800 s, file size 4 GiB, 4096 fds. No address-space limit by default: under `ulimit -v` CodeGraph's WebAssembly runtime fails ("WebAssembly.Memory(): could not allocate memory"). Memory capping is open (cgroup v2 via `systemd-run --user --scope -p MemoryMax=` or a container) and tracked in STATUS. `TRACES_LIMIT_AS_KB` opts in. Fallback when user namespaces are unavailable: superseded by D-026 (no automatic fallback; only an explicit `TRACES_ISOLATION=off` dev override, recorded on the snapshot; CT15 still fails for it). CI enables user namespaces with `sysctl kernel.apparmor_restrict_unprivileged_userns=0`.

## D-007 Components and layers are deterministic
Produced by rules on the evidence/indexing side (path and framework rules, recorded `rule` id per component), stored in `components`. No LLM output becomes a component or a claim.

## D-008 Three index runs per baseline
The port indexes the real copy and two throwaway copies (copyA, copyB) fresh on every run instead of reusing an index. Reason: CT14 determinism and CT15 isolation then always have fresh indexer evidence; the reused-index branch of CT15 (D-002B) is never taken.

## D-009 Contract test port changes
Pass criteria are the Task 002 ones except: CT7 no longer reads the Lab B verbatim script output (evidence only, never in the pass criterion); CT15 requires 3 indexer summaries and no reused log, and the allowed write scope is the run directory; CT16 locates source snapshots by the `## source` section. Details in TEST_MAPPING.md.

## D-010 N1 fixture constants instead of page text
The Task 002 negative control N1 quoted a third-party page (GitDiagram). The repo commits only its sha256 (`79f00568...`) and byte offsets `(38739, 57457)`; `TRACES_GITDIAGRAM_PAGE` can point at a local copy to re-verify. The target repository is fetched at `b1125d8` into the gitignored `.cache/targets/` and never committed.

## D-011 Rejected claims and missing locations (steering 2, 3)
Rejected is its own label "Rejected", shown only in reviewer and evidence views; graph/trace/claim lists hide rejected by default with `hidden_counts` and `include_rejected=true`. `missing_location` shows the claim's own label plus a "no source location" flag and is never verified.

## D-012 Job progress by polling with ETag
`GET /jobs/{id}` with `ETag` = job version and `If-None-Match` -> 304. No SSE: simpler behind proxies and enough at 1-2 s intervals.

## D-013 BYOK in the browser
Provider keys never reach the backend. Explain returns a deterministic answer or a scoped prompt bundle with citations and an outbound-content manifest; the browser sends it after consent. Request models forbid extra fields so a key cannot be posted.

## D-014 OpenAPI as the UI contract
FastAPI generates OpenAPI; `docs/contracts/openapi.json` is committed and checked current by a test; `web/src/api/schema.d.ts` is generated from it and checked by `npm run check:api`.

## D-015 Web TypeScript 5.9.3, validator TypeScript 6.0.3
The validator toolchain keeps TypeScript 6.0.3 (the Task 002 TS validator family). The web build uses 5.9.3 because `openapi-typescript@7.13.0` declares `typescript ^5.x` as a peer. They are separate lockfiles (`toolchain/`, `web/`).

## D-016 History hook points, GitHub client placement, Lab C
Shared record types live in `traces.evidence`; history owns `backend/traces/history` with its own git runner and writes `docs/contracts/history.md`; the GitHub client, token, cache and rate limits live in the API/ingest layer and reach history through an injected `PrContextProvider`. Lab C scripts are not ported (History is rewriting them).

## D-017 Store migration ranges
0001-0099 Traces, 0100-0199 History, 0200-0299 UI/explain. Duplicate numbers fail at startup.

## D-018 CI workflow file staged outside .github (temporary)
The available push token lacks the `workflow` scope, so GitHub refuses any push touching `.github/workflows/`. The workflow is committed at `ci/github-actions-ci.yml` and must be moved to `.github/workflows/ci.yml` by a credential with that scope (one `git mv`). Tracked in STATUS.

## D-019 Evidence-set diff keeps the git_recount check family in v1 (2026-10-21)
For v1, `evidence_set_diff` records (`snapshot_added` / `snapshot_removed`) keep using the `git_recount` check method for their independent check. A dedicated evidence-set recount check method is deferred to schema 0.5. No schema change in v1. Raised by Traces History in PR #11.

## D-020 PrContextProvider gains optional artifact_bytes (2026-10-21)
`PrContextProvider` gains an optional `artifact_bytes(pr_number) -> bytes | None`. When a provider offers it, history verifies the cached artifact's sha256 and quoted PR text can reach `observed` via `quote_match`; without it, PR quotes stay `unvalidated` with a reason. The real GitHub provider (client, token, cache, rate limits) will be wired by the API lane (Traces seat). Raised by Traces History in PR #11.

## D-021 INGEST: anonymous visibility check, pinned snapshot on registration, fetch caps (2026-10-21)
`POST /repos` now confirms the repository is public with a credential-free `git ls-remote --symref` (no credential helper, prompts off, askpass `/bin/false`, no token in the environment), records `default_branch`, `latest_discovered_sha/at` and the new `visibility_checked_at`, and pins a snapshot in state `pending` at `sha` or the discovered HEAD (never downgrading an existing snapshot). A private, missing or renamed repository gives 422 `repo_not_public` (GitHub answers the same for all three anonymously). `GET /repos/{id}/head` is implemented with a 60 s per-repo cache and a 5 s minimum interval (429 `rate_limited` with `Retry-After` only when nothing is cached). Migration 0002 adds `repos.visibility_checked_at` and `repos.external_ai_consent` (default 0; v1 has no endpoint that sets it, so explain bundles still need per-request consent). Both fields are added to `Repo` (backward compatible: new optional fields). New error codes: `repo_not_public`, `repo_empty`, `sha_not_found` (422), `too_large`, `too_many_files` (413), `fetch_timeout` (504), `upstream_unavailable`, `fetch_failed` (502), `rate_limited` (429). `invalid_sha` is now returned for a bad `sha` on registration (was `invalid_repo_url`). Clone caps (env, defaults): `TRACES_MAX_CLONE_MB` 1024 measured while `git clone` runs, `TRACES_CLONE_TIMEOUT_S` 900, `TRACES_MAX_FILES` 100000 and `TRACES_MAX_TREE_MB` 1024 checked from Git objects before checkout. Partial clones are always removed. Reason: charter 4A and section 5 (public only, safe clone, size/time limits). Change when private repos with stored credentials are in scope.

## D-022 INDEX worker, job runner, generic validation, memory cap (2026-10-21)
`POST /repos/{id}/index-jobs` is implemented. Jobs run in-process on a thread pool (`TRACES_INDEX_WORKERS`, default 1) and drive the 3.2 state machine through `traces.evidence.index.IndexRun`. Its phases are fetching (capped public clone, D-021), checking_out (throwaway copy in the run dir), indexing (CodeGraph in `workers/sandbox.sh`), adapting (isolation probe and adapter in one sandbox call, so adapter check 4.7 still holds), validating, storing (0.4 migration, deterministic components, languages, frameworks, `generated_paths`), history, then done.
- **Requests.** With no `sha`, the job uses the latest discovered HEAD. A job already queued or running for the same snapshot is returned instead of a duplicate. A ready snapshot without `reindex=true` returns 409 `already_indexed`.
- **Failure codes** (in `job.error`): `extract_failed`, `adapter_failed`, `validation_failed`, `toolchain_missing`, `index_timeout`, `memory_limit`, `internal_error` (message only, no paths or tracebacks), `interrupted` (set at startup for jobs a previous process left unfinished), plus the ingest codes.
- **Snapshot state on failure.** A failed first index marks the snapshot `failed`. A failed reindex of a `ready` snapshot leaves it `ready` with its previous evidence (amends 3.2).
- **Generic validation.** The orchestrator gains `--no-fixture`, used for every snapshot except Task 002's own. In that mode the TS validator builds one Program per tracked `tsconfig.json` directory plus the repo root, and the root gets default options when it has no tsconfig. The Task 002 snapshot keeps the expected-chain fixture and the injected negatives, so its 12 rejected records and both canonical hashes (`73db432b...`, `45600280...`) reproduce through the product path (tested). The fixture path is byte-identical. The Rules version gate now tolerates a missing `uv.lock` or `frontend/package.json`, and an invalid alternation token is matched literally instead of crashing. Neither change affects the baseline.
- **Memory cap.** An RSS watchdog sums VmRSS over the sandboxed session and kills it past `TRACES_MAX_RSS_MB` (default 6144). Measured on the box: `RLIMIT_DATA` at 4 GiB already breaks CodeGraph's WebAssembly (it passes at 8 GiB), and the box has no writable cgroup or user systemd. So rlimit-based memory caps stay off, which closes the D-006 open item without cgroups. Wall-clock cap per step: `TRACES_INDEX_TIMEOUT_S` (1800).
- **Outbound calls.** The worker runs no outbound network probes. `CONTROL_E=skipped`, and the CT15(e) control stays a baseline-only check.
- **History.** History is bound to the frozen entry point `traces.history.runner.run(repo, config, *, components, evidence_sets, cache_dir, max_milestones=8, run_id)` (history.md 8.11) through `history_entry_point()` in `traces.evidence.index`. `evidence_sets` carries the static 0.4 records stored for the pinned SHA. Outcomes: a missing module or the stub's `NotImplementedError` records the step as `skipped` with a reason; a result with `complete=false` (budget) records `completed_with_warnings` and keeps its records; any other error records `failed` with its code. In every case the job still succeeds and the static evidence stays stored.

## D-H6 History git-object fact claim_ids anchor to the commit (2026-10-21)
Requested by Traces History in PR #3, recorded verbatim:

> D-H6 (2026-10-21): History git-object fact claim_ids anchor to their commit SHA, not `repo_sha`. This differs from Task 002 claim_id v3, which hashes `repo_sha`. A git-object fact cannot change once its commit exists, so its id stays the same across re-pins and can be reused from the cache. History pattern records still anchor to their computed range.

Static (code) claims keep claim_id v3 anchored to `repo_sha`. No schema change is needed: the claim_id format (`c_` + 64 hex) is unchanged.

## D-H1..D-H9 History decisions (summary pointer)
The binding text is in [docs/contracts/history.md section 20](contracts/history.md#20-decisions-architect1-2026-10-21-ist); it supersedes conflicting text in that document. Summary:

| Id | Decision |
| --- | --- |
| D-H1 | Co-change, churn and hotspot values may reach `observed` after an independent recount; class stays `history_pattern`, never `verified`; coupling interpretations stay `unvalidated`. |
| D-H2 | Git plumbing checks that do not read the log parse are independent for git-object facts; `quote_match` establishes only that a quote exists. |
| D-H3 | New `citations` field; every record has at least one entry in `locations` or `citations`. |
| D-H4 | `review_state` (none/confirmed/disputed, reviewer, at) is separate from status and never promotes it. |
| D-H5 | "All commits" means all non-merge commits for lifecycle and churn, with replay along first-parent. |
| D-H6 | Git-object fact claim_ids anchor to the commit, not `repo_sha` (entry above). |
| D-H7 | `dist/` and `build/` are filtered at any depth, matching whole directory segments only. |
| D-H8 | The evidence side supplies `generated_paths`, including generator-config output dirs. |
| D-H9 | Milestone cap: 8 by default for the index worker, 20 for on-demand compare. |

## D-023 API explain and chat bundle call the deterministic explain engine (2026-10-21)
`POST S/explain` calls `traces.explain.bundle.explain(snapshot_id, question, focus_claim_ids, store=st)` for `mode=no_llm` and `prompt_bundle(...)` for `mode=prepare_bundle`. `POST S/chat/bundle` always calls `prompt_bundle(...)`. A `LookupError` from the engine maps to 404 `not_found`, and an unknown snapshot is 404 before the engine runs. `/meta` reports `explain` and `chat_bundle` as true. There's no LLM call in the backend and no provider credential path: the request model still forbids extra fields, and the bundle is sent by the browser only after consent. This is additive. The response model is unchanged, and the only OpenAPI change is that the 501 response is removed from these two operations.

## D-024 Views and history queries read the store (2026-10-21)
Overview, components, routes, graph, source, trace, and the history endpoints are implemented in `traces.evidence.views` and no longer return 501. Rules that keep the product honest:
- The graph and trace use `evidence_scope=static` only. Co-change, hotspots and other history patterns are not drawn as architecture.
- Rejected claims stay stored, are excluded by default, and are reported in `hidden_counts`. A rejected edge is never a bridge in a trace.
- A missing trace link is a `gap` hop with label `inferred` and a reason. `complete` is false when any hop is a gap. `library_contract` (kind or flag) stays a library-contract hop.
- Route methods are taken from the stored record. If none is recorded the method is `UNKNOWN` and the flag `method_not_recorded` is set. There is no source scan that guesses routes.
- Overview purpose is `unknown` unless a README heading can be quoted, and that quote is `interpretation`, not a capability.
- Source is read with `git cat-file` from the pinned checkout. Paths containing `..`, a leading slash or `~`, a backslash, NUL or a line break are 422 with a message naming the cause. A leading `-` is a legal file name since D-028 (it reaches Git only inside `<sha>:<path>` after `--end-of-options`). Ranges over 400 lines are 422. A missing checkout is 404, not fabricated text.
- History endpoints return stored history and documented records. Compare returns stored `snapshot_added` / `snapshot_removed` when those records exist. Otherwise it returns an identity diff of static claims already stored on the two snapshots (same claim ids and kinds). It does not write records and it does not map renames. Rename-aware `snapshot_*` records still require history to be given two evidence sets (the index job currently passes only the pinned SHA; milestone re-indexing, hook H3, is not done).
- `/meta` capability flags for these endpoints are true.

## D-025 TypeScript resolution stops at the checkout (2026-10-21)
The validator's compiler host refuses `node_modules` paths that sit outside the pinned checkout. TypeScript's own lib directory (`TS_MODULE`) stays readable, and a `node_modules` inside the checkout still resolves. Reason: module resolution walks parent directories. A checkout placed under another project (or a data directory under a repo that has `node_modules`) was resolving libraries such as react-hook-form from that parent and changing six check texts, so the Task 002 validation hash was no longer `73db432b...`. With the boundary, the same records hash to `73db432b...` whether or not a parent `node_modules` exists. What would change it: a decision to treat dependencies installed above the checkout as in-scope evidence.

## D-026 Isolation fails closed; `TRACES_ISOLATION=off` is the only unisolated mode (2026-10-23)
Review F2 against D-Q5 and D-002A.6 (stop the run when isolation cannot be shown). `resolve_isolation` probes `workers/sandbox.sh` itself under `unshare -rn`. `auto` (the default) and `unshare` give `unshare` or fail. They never fall back. Any other value is refused, including the old `none`. The index job resolves isolation before fetching anything. When isolation cannot be shown, the job fails with `isolation_failed` and a message starting `E_ISOLATION:`, nothing is cloned, the first index marks the snapshot `failed`, and no claims are stored. A failing per-run probe (adapter check 4.7 `E_ISOLATION`) maps to the same code. `workers/sandbox.sh` accepts `unshare` or `off` and exits 64 for anything else. The baseline pipeline exits with `E_ISOLATION` too.
- **Dev override.** `TRACES_ISOLATION=off` runs the workers without a network namespace. The job logs a warning event, the adapter records `4.7 SKIPPED: isolation=off`, and migration 0003 stores `snapshots.isolation = 'off'`. `Snapshot` gains `isolation` (`unshare` | `off` | null) and `unisolated` (true only for `off`). An unisolated snapshot is never acceptance evidence, and CT15 fails for it. `/meta.isolation` reports `off` or `unshare`, and `none` stays in the enum only for compatibility.
- Reason: the product index was storing ready snapshots from unisolated runs with only a warning. To change this, a sandbox other than user namespaces (container, cgroup netns) would have to be added as a second way to show isolation.

## D-027 Repo-level AI consent endpoint (2026-10-23)
`PUT /repos/{id}/ai-consent` `{consent, consent_text_version}` records the repo-level consent the BYOK UI asks for. Migration 0003 adds `repos.external_ai_consent_at` and `repos.external_ai_consent_text_version` next to 0002's `external_ai_consent`. `Repo` exposes all three. Granting requires `consent_text_version` (1-64 chars, `[A-Za-z0-9._:-]`). Revoking sets consent false, keeps the time of the change and clears the version. It returns the updated `Repo`, 404 for an unknown repo, and 422 for a bad body (extra fields such as `api_key` included). The change is additive, and it is bookkeeping only. No key or provider call reaches the backend, and the browser still shows the outbound manifest and asks before each send. Reason: the UI needs a stored, versioned consent per repository (charter BYOK). It would change if consent moved to per-user accounts.

## D-028 Hardening from the security suite and the v1 evidence review (2026-10-23)
- **Git paths (F-1).** Every place that lists tracked paths parses `git ls-tree -z` (core `Blobs`, ingest tree caps, TS validators; components already did). Before this, Git C-quoted non-ASCII names, and the adapter refused the whole index with `E_PATH`.
- **Source paths (F-2).** `safe_repo_path` accepts legal names such as `-rf.py` and gives an accurate 422 message per cause. Git gets paths only as `<sha>:<path>` after `--end-of-options`, so a path is never an option.
- **No input echo (F-3).** A 422 validation body lists only `loc`, `msg` and `type`, never pydantic's `input`, `ctx` or `url`. Error details are redacted at any depth for names like key, token, secret, authorization, password, credential or cookie.
- **Ingest cleanup (D-021 follow-up).** `git clone` runs in its own process group, and a cap kill stops all its helpers. Before this, they kept writing pack files after the partial clone was removed, about 860 KB in the audit. Cleanup runs in a `finally` for every failure and interrupt. The clone size is checked again after git exits, in addition to the 0.5 s polling.
- **Unknown SHA (audit, Lab F-6).** `POST /repos` with a `sha` other than HEAD, and `POST /repos/{id}/index-jobs` with a `sha` that is not the discovered HEAD or a ready snapshot, check the commit with an anonymous shallow fetch of that commit object only (`--depth=1 --filter=tree:0`, throwaway bare repo, no credentials). An unknown commit gives 422 `sha_not_found` and stores nothing. This uses D-021's existing code, so it does not conflict with the contract: registration still pins `pending` snapshots, but only for commits that exist. If the worker still meets a missing commit, it removes the empty snapshot row (the failed job keeps `snapshot_id` null) and the empty cache directory.
- **Python validator (Lab F-4, F-5).** Relative imports keep their dots (`.enc`, `..`), as CodeGraph names them, in the import check and in import declarations. Class-member binding skips `@overload` stubs, so a call resolves to the runtime implementation. Otherwise the first definition still wins. The Task 002 validation hash stays `73db432b...` (fsft uses absolute imports and no overloads).
- **Evidence output (review F3, F4, F5).** Claim summaries, graph edges and trace hops carry `injected`, and injected records also carry the flag `injected_control`, so a negative control never reads as a repository fact. The graph reports `truncated_counts` by status for edges cut by `limit`. `hidden_counts` now follows the request's filters, and with a focus it counts only hidden edges that touch the focused neighbourhood or component. New response fields are optional in OpenAPI (additive).
- **Tests and artifacts (review F1, F7, F8).** The CT4 negative clause runs again and fails when broken. A baseline run writes `v1/validation/chain.json` and `coverage.json` (`traces.evidence.report`, a port of research `report.py`), identical to the research output apart from `run_id`. `test_index_worker` asserts that missing_location is never verified. `schema_check.py` is checked with per-module strict mypy flags.

## D-029 Component layer reasons, a `library` layer, route labels and per-step trace gaps (2026-10-23)
- **Why.** UI asks (O-3). On pallets/itsdangerous@672971d the only code component, `src/itsdangerous`, was labelled `backend` with nothing to say why, which overstates a library as a server.
- **Reason per component.** Every component now stores a `reason` naming the counted files and the rule, e.g. `backend: 4 of 6 file(s) are code outside api, data and UI paths (layer-v1:path-and-extension)`. It lives in `components.record_json`, so no migration is needed. Older rows return `reason: null`. The reason is not part of the component-map digest, so history inputs do not change.
- **`library` layer.** A repository is a library when it declares a package (top-level `pyproject.toml` with `[project]` or `[tool.poetry]`, `setup.py`/`setup.cfg`, or a `package.json` with a name that is not `private`), no application framework (FastAPI, Django, Flask, Starlette, Express, Fastify, NestJS, Next.js, React, Vue, Svelte, Angular, Vite) is a runtime dependency (JS `devDependencies` do not count), and no application entrypoint file (`manage.py`, `wsgi.py`, `asgi.py`, `app.py`, `main.py`, `server.py`, `server.js/ts`, `index.html`, `Procfile`) exists outside tests, docs and examples. In a library, components whose layer would be `backend` become `library`, with rule `dir-v1:container-strip+library-v1:no-app-entrypoint`. The decision and its reason are recorded in snapshot facts (`sources.repo_kind`). Other layers do not change. The rule is deterministic, works from Git objects only, and is a heuristic: a library that ships an `app.py` stays `backend`.
- **fsft is unchanged.** full-stack-fastapi-template has no top-level package declaration and depends on FastAPI and React, so every layer stays as before (checked component by component), and the Task 002 validation hash is unchanged. For a library, the component-map digest changes once, because the layer is in it. That is intended.
- **Routes.** `RouteItem.label` is the recorded route name (`provenance_raw.row.name`), capped at 200 characters, or null. It is never built from method and path.
- **Trace gaps.** A gap hop's reason says how many outgoing static relationships of that step the request hides, by status, and how to show rejected ones. `hidden_rejected` carries the rejected count (0 when none are hidden).
- All new fields are optional in OpenAPI (additive). `library` is a new enum value for `Component.layer`, so a UI with an exhaustive switch must handle it. A separate git-history category in explain is deferred to v1.1.

## D-030 A minimal JavaScript import check; JavaScript calls are v1.1 (2026-10-23)
- **Why (Lab F-10, G-4 on hagopj13/node-express-boilerplate@179ae84).** JavaScript had no validator family, so nothing could be verified and the default graph was empty for JS repos. The L3 text check accepted only `import`, `from` or `export`, so every correct `require()` failed it.
- **L3.** For an `imports` site in a `.js`, `.cjs`, `.mjs` or `.jsx` file, L3 passes on the same `import|from|export` word as before, or on `require('x')` / `require("x")` whose specifier matches exactly: a file target must be the file the specifier resolves to, and a package import node must have the same module string. Other languages are unchanged.
- **Independent check.** The pinned TypeScript 6.0.3 parser (Apache-2.0, already in `toolchain/`; no new dependency) parses the importing file read from the clean checkout, after its bytes are checked against the git blob id. It runs as a parser only, with no Program and no type checker. It lists `import/export ... from`, `require()` and `import()` with literal specifiers. Python then resolves relative specifiers against the Git tree with Node's CommonJS order: the exact path; then `.js .cjs .mjs .jsx .json`; then the directory's `package.json` `main`; then `index.*`. The check is `binding_resolution`, family `typescript-compiler`. It passes when the specifier on the site line resolves to the edge's target file, fails when every specifier resolves to some other repo file, and is inconclusive otherwise: a package, absolute, aliased or computed specifier, no reference on the line, or a file that rebinds `require`. A package import node gets `parser_presence`, so it is observed, never verified, as for Python (Decision 002-B correction A). Status rules are unchanged, so a JS import is verified only when this check passes and L1 to L3 pass. No target code runs.
- **Deferred to v1.1.** Validation of JavaScript calls, references, instantiations and named import bindings (`import { add } from './math'` to `add`). Those records keep "no validator family" or an inconclusive check, so they stay unvalidated or observed and are never verified. `/meta` lists `javascript: typescript@6.0.3 parser, imports only (D-030)`.
- **Result.** On node-express-boilerplate@179ae84, 107 imports are verified, which matches Lab's manual 107 of 107. Nothing else is verified and nothing is rejected. The Task 002 fsft validation hash is unchanged.

## D-031 Trace completeness, Express mounts and git process groups (2026-10-23)
- **Trace (Lab F-9).** A step whose outgoing calls are stored only as unresolved references (`calls`/`instantiates`; `require` excluded, since it is the module import) now gets a `gap` hop that names them (`unresolved_calls`). An `edge` hop that is not verified or observed also keeps the trace from being complete. `complete` is false in both cases, and `incomplete_reasons` says why. The UI's "Complete: every step is backed by a recorded relationship" is then true when shown.
- **Mounts (O-7, partly).** A route record the extractor named `USE <path>` (an `app.use`/`router.use` mount) is listed with method `USE` and flag `mount` instead of `UNKNOWN` with `method_not_recorded`. Prefixing paths of routers mounted through a computed `forEach` needs data-flow and is a documented limit (CONTRACTS 4.7, STATUS). Mongoose persistence (O-8) is also a documented limit, not a few-line change.
- **Process groups (Lab report: a fake-git shim alive after a test).** Every git call in the fetch path (`git()`: cat-file, ls-tree, checkout; and the capped clone) runs in its own session. On a timeout, interrupt or normal exit, the whole process group gets SIGKILL and is waited for. Tests assert that no process the shim started survives a timeout or an interrupt.

- **Focused hidden counts (F5 consistency, Traces seat on b37eef2).** With a symbol focus, an edge is shown only when both ends are in the neighbourhood. A hidden edge now counts only under the same rule, using the neighbourhood computed with the hidden edges included. So `hidden_counts` equals what `include_rejected=true` (or adding the status) would add. On fsft, `create_item` at depth 1 goes from 2 rejected to 1, and the extra one was N2a. A component focus keeps its "either end in the component" rule for both. Depth 0 shows no edges and counts none.
- **`/meta` isolation.** `/meta` reports the probed result, not the configured value: `unshare` when the sandbox probe passes, `unavailable` when `auto` or `unshare` is set but the probe fails (index jobs then fail closed with E_ISOLATION), and `off` for the explicit override. The result is cached for 60 s.
- **Startup cleanup (O-9).** On first store use, the API removes snapshot rows in state `failed` whose latest job failed with `sha_not_found` and that have no claims, together with their cache directories, but only directories that are empty. Jobs stay, with `snapshot_id` NULL. Nothing else is touched. Each removal is logged as a warning on `traces.maintenance`. The step is idempotent. A read-only dry run on a copy of the review store finds exactly one row: `github.com__pallets__markupsafe@000…001`.
- `test_index_baseline` runs only when it needs no network: when `TRACES_NETWORK_TESTS=1`, when `TRACES_BASELINE_RUN` is set, or when the pinned fsft checkout is already cached (CI restores it). Otherwise it is skipped, like the other live-GitHub tests.
