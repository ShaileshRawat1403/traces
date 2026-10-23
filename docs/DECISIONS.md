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
`workers/sandbox.sh` runs the indexer and adapter with `unshare -rn` (no network), HOME and telemetry overridden, token/secret environment variables removed, and `ulimit` CPU 1800 s, file size 4 GiB, 4096 fds. No address-space limit by default: under `ulimit -v` CodeGraph's WebAssembly runtime fails ("WebAssembly.Memory(): could not allocate memory"). Memory capping is open (cgroup v2 via `systemd-run --user --scope -p MemoryMax=` or a container) and tracked in STATUS. `TRACES_LIMIT_AS_KB` opts in. Fallback when user namespaces are unavailable: `TRACES_ISOLATION=none` runs without a network namespace, the adapter records the fallback (check 4.7 warning) and CT15 fails, so a non-isolated run can never pass the contract suite. CI enables user namespaces with `sysctl kernel.apparmor_restrict_unprivileged_userns=0`.

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
- Source is read with `git cat-file` from the pinned checkout. Paths containing `..`, a leading slash, a backslash or a leading `-` are 422. Ranges over 400 lines are 422. A missing checkout is 404, not fabricated text.
- History endpoints return stored history and documented records. Compare returns stored `snapshot_added` / `snapshot_removed` when those records exist. Otherwise it returns an identity diff of static claims already stored on the two snapshots (same claim ids and kinds). It does not write records and it does not map renames. Rename-aware `snapshot_*` records still require history to be given two evidence sets (the index job currently passes only the pinned SHA; milestone re-indexing, hook H3, is not done).
- `/meta` capability flags for these endpoints are true.

## D-025 TypeScript resolution stops at the checkout (2026-10-21)
The validator's compiler host refuses `node_modules` paths that sit outside the pinned checkout. TypeScript's own lib directory (`TS_MODULE`) stays readable, and a `node_modules` inside the checkout still resolves. Reason: module resolution walks parent directories. A checkout placed under another project (or a data directory under a repo that has `node_modules`) was resolving libraries such as react-hook-form from that parent and changing six check texts, so the Task 002 validation hash was no longer `73db432b...`. With the boundary, the same records hash to `73db432b...` whether or not a parent `node_modules` exists. What would change it: a decision to treat dependencies installed above the checkout as in-scope evidence.

