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
