# Traces v1 acceptance (charter section 7)

Owner: Traces Lab (QA, Integration, CI and Security seat).
Final acceptance pass: 2026-10-23, 14:51 to 15:20 IST, on `build/traces-v1` @ `0f32d4d` (PRs #31, #33, #35 to #38). Head now `033e1f8` (#39 History doc, #40 Lab, #41 O-13). `ws/lab-acceptance` was fast-forwarded to `033e1f8`. Evidence below is at `0f32d4d` unless it names `033e1f8`.

Labels used below:
- **CI**: a real GitHub Actions run passed. Run id and commit are given.
- **Local**: run on the Traces Lab box only (8 CPUs, Linux 6.12.94, CPython 3.14.8, Node 20.19.2, npm 11.21.0, uv 0.13.4). Not a CI result.
- **Box app**: checked read-only against the running review app (`/workspace/traces-review/traces`).
  - Verified at 14:51 IST:
    - `git log -1` there is `0f32d4d`.
    - API pid 2270658 (`traces serve --port 8731`) started at 14:45 IST, with cwd `/workspace/traces-review/traces`.
    - Web pid 2270655 (vite on 5731) started at 14:45 IST, with `TRACES_API_URL=http://127.0.0.1:8731` in its environment.
    - `/api/v1/meta` returns byte-identical responses through 5731 and 8731 (sha256 `78de1605...`).
  - The store is the same file as before: `.traces-data/traces.sqlite3`.
  - The one write, at Architect1's request: fsft@b1125d8 and itsdangerous@672971d were re-indexed through the box API at `0f32d4d` with `reindex: true`.
    - Before, both had been indexed before migration 0003, with an empty `isolation` field.
    - fsft: job `j_c43c3a1fc81142d9a19d`, 15:12 IST, 21 s. itsdangerous: job `j_415d7e33bd7a46aebe41`, 15:12 IST, 7 s. The only network use was the fetch of these two pinned SHAs.
    - The API re-indexes the same snapshot row (`repo@sha`). The old jobs and runs are kept, and nothing was deleted by hand.
    - Before and after counts, isolation values and hashes are in `.traces-data/acceptance/final/reindex/before.txt` and `after.txt`; see O-14 and O-15.
  - Row counts in every table were identical before and after each set of walks: 3 repos, 2 snapshots, 21,792 claims, with 3 jobs before the re-index and 5 after.

CI run for this pass:
- `39930532720`: push, `build/traces-v1` @ `0f32d4d`, success, 11 of 11 jobs, 14:45 to 14:52 IST. This is the first CI run on `0f32d4d`; PR run `39930539272` on the same commit is also success, 11 of 11.
- Counts from its log:
  - unit: 87 passed, 3 skipped (live GitHub checks need `TRACES_NETWORK_TESTS=1`)
  - explain: 96
  - api: 95
  - contract: 17
  - regression: 16
  - security: 136 passed, 0 xfailed (`tests/security` plus `tests/e2e/*.py`)
  - history: 176 passed, 0 skipped
  - vitest: 125 in 16 files
  - mypy: no issues in 43 files
  - ruff: clean
  - e2e on the real fsft@b1125d8 seed: Playwright 94 passed, 4 skipped; `real_snapshot.cjs` 21 of 21; `chat_g5.cjs` 13 of 13.
- Earlier runs: 39716507167 (`35499bc`), 39914041785 (`6384c78`), 39916651720 (`e532644`), all success.

Local counts at `0f32d4d`, all jobs PASS:
- Command: `TRACES_API_PORT=18031 TRACES_WEB_PORT=15231 ci/run_local.sh`. Logs are in `.traces-data/ci-local/final-0f32d4d/` (gitignored).
- Counts: same as CI except e2e timing.
  - lint: clean
  - types: mypy 43 files and tsc, clean
  - unit: 87 passed, 3 skipped (network)
  - explain: 96
  - api: 95
  - web-build: vitest 125 in 16 files, `check:api`, vite build
  - target: pinned HEAD ok
  - contract: 17
  - regression: 16
  - security: 136
  - history: 176, 0 skipped
  - e2e on the fsft seed: 94 passed, 4 skipped; real-snapshot 21 of 21; chat G-5 13 of 13
- e2e on the synthetic seed: `TRACES_E2E_SEED=synthetic ci/run_local.sh e2e` gives 84 passed, 14 skipped. The skips are fsft-only content checks.
- Python e2e suites, run alone (`uv run --frozen pytest -q tests/e2e/<file>`):
  - `test_cochange_explain.py`: 4 passed, with a new O-4 assertion over every sentence that cites a co-change record. The same file fails 1 of 4 against the `e532644` engine, on the O-4 summary sentence, so it catches O-4.
  - `test_express_patterns.py`: 4 passed, no xfail.
  - `test_python_package_patterns.py`: 3 passed.
- Perf bench `tests/perf/bench.py` at `0f32d4d`: see O-5 and [acceptance/PERF.md](acceptance/PERF.md).
- Box app walks against web 5731 (read-only):
  - `tests/e2e/demo_walk.cjs`: 16 of 16 after the box re-index (run at 15:16 IST), with updated steps 10, 11 and 13 and a new step 6b. Before the edits and the re-index, the first run was 14 of 15: step 11 failed on O-13. Step 13 failed once after the re-index on its old "47 rejected" text.
  - `tests/e2e/real_snapshot.cjs`: 21 of 21, before and after the re-index.
  - `tests/e2e/chat_g5.cjs`: 13 of 13, before and after the re-index, with exact-line manifest hashes (O-11). It found no key in `/tmp/box_api.log`, `/tmp/box_web.log` or the store.

Scratch re-index at `0f32d4d`, offline, from local full-history clones:
- Done with `IndexRun` and a local-path ref, the same way as `scripts/e2e_seed.py`; script `.traces-data/acceptance/final/index_local.py`.
- Repos: pallets/itsdangerous@672971d, pallets/markupsafe@4e11127 and hagopj13/node-express-boilerplate@179ae84 (served on scratch port 18850).
- Evidence is in `.traces-data/acceptance/final/` (gitignored).

Detail: [acceptance/EXPRESS.md](acceptance/EXPRESS.md), [acceptance/PERF.md](acceptance/PERF.md), [acceptance/SECOND_REPO.md](acceptance/SECOND_REPO.md), [acceptance/DEMO_SCRIPT.md](acceptance/DEMO_SCRIPT.md), [../tests/security/README.md](../tests/security/README.md), [../ci/README.md](../ci/README.md).

## 1. Section 7 checklist (final at `0f32d4d`)

| # | Charter item | Proof | Status |
| --- | --- | --- | --- |
| 1 | Valid public GitHub URL, index status, pinned SHA, populated overview | **CI 39930532720**: `tests/api` 95 passed, including `test_index_baseline.py` (the product index of fsft@b1125d8) and the F-6 `sha_not_found` guards. Box app: demo steps 1 to 3 | **Pass** (CI) |
| 2 | Interactive graph, focus, follow cross-file edges, open pinned source | **CI 39930532720**: e2e job on the real fsft seed, 94 passed, 4 skipped by design (Ollama absent; desktop-only and phone-only cases). Box app: demo steps 4, 5 and 15. The Routes, Components and Source pages render real data (G-3 closed) | **Pass** (CI) |
| 3 | fsft@b1125d8: nine Task 002 links traceable, persistence static only, H1/H2 inferred | **CI 39930532720**: regression 16 passed (`test_nine_links_and_library_hops`). Box app: demo step 6 (10 steps, 2 inferred library steps, 1 gap, "Static persistence path") | **Pass** (CI) |
| 4 | Nine wrong CodeGraph imports not verified; three injected negatives rejected; Task 002 16+8 still pass | **CI 39930532720**: contract 17 passed (CT1 to CT16 plus count), regression 16 passed. Box app: demo step 7 (12 rejected = 9 imports + 3 injected) | **Pass** (CI) |
| 5 | View and explain a Git-backed architecture change with cited commits; co-change is not causality | **CI 39930532720**: history 176 passed, 0 skipped; `tests/e2e/test_cochange_explain.py` in the security job. Box app: demo steps 8 to 10. Step 10's answer is a summary, then the 96-file move `9d703df` ranked first, asserted in order (O-12 fixed). "Which files changed together with backend/app/crud.py?" cites crud.py and test_users.py, 5 of 26 (F-8 fixed). Every sentence citing a co-change carries the caveat (O-4 fixed) | **Pass** (CI) |
| 6 | No-key mode useful; provider mode refuses unsupported claims, citations, privacy controls | **CI 39930532720**: explain 96, `tests/security/test_no_key_and_caps.py`, and `chat_g5.cjs` 13 of 13 with a stub provider in the e2e job. Box app: `chat_g5.cjs` 13 of 13 through 5731; demo steps 10 and 11 | **Pass** (CI) for no-key and the stub provider. Live provider untested (L-8). O-13 fixed at `033e1f8` |
| 7 | Second, different public repo indexed and explored; unknowns instead of invented links | Local re-index at `0f32d4d`. itsdangerous: 3,312 claims, 357 verified, **0 rejected** (was 47, F-4 and F-5), the same on the box app after its re-index (O-15). markupsafe: 3,232 claims, 233 verified, 0 rejected (was 2). Express: 3,671 claims, **107 verified, all imports**, 107 of 107 correct (F-10). The `register` trace is incomplete and lists `userService.createUser` and `tokenService.generateAuthTokens` as unresolved calls (F-9). `POST /register` explain cites the route (F-11). The src/itsdangerous layer is now `library`, with a reason (O-3). CI: `test_express_patterns.py` 4 and `test_python_package_patterns.py` 3 passed in the security job | **Pass** (local re-index, CI pattern tests). Limits L-2 to L-5 apply |
| 8 | Errors, unsupported types, missing keys, index failures, rate limits, malicious paths, oversized repos fail safely and visibly | **CI 39930532720**: security 136 passed, 0 xfailed. It covers bad URLs, traversal, symlinks, non-ASCII and leading-dash names (F-1, F-2), caps, timeouts, 429, no-key, key not echoed (F-3), failed-job visibility, and a final clone-size check (O-1). F-6 fixed (API and worker paths, local repro) | **Pass** (CI) |
| 9 | Desktop and mobile browser, touch navigation, evidence inspection | **CI 39930532720**: e2e job on the real fsft seed, desktop and android-360 with axe; `real_snapshot.cjs` 21 of 21 (nine fsft screens, axe WCAG 2.2 AA at 1280 px and 360 px, tap Open evidence, no sideways scroll). Box app: 21 of 21 | **Pass** (CI). axe covers automated rules only; no screen-reader pass |
| 10 | CI: unit, adapter/schema, regression, API, e2e browser; lint/types/build; no critical security risk; no unintended outbound calls; no secrets | **CI 39930532720**: all 11 jobs green. Outbound: `tests/security/test_outbound.py`. Secrets: a `git log -p --all` scan (GitHub, OpenAI, Anthropic, AWS, Slack and private-key patterns) at `0f32d4d` finds only the fake `ghp_abcd...` test token in `tests/security/test_repo_urls.py` | **Pass** (CI) |
| 11 | Docs: setup, architecture, licenses, coverage, limitations, reproducibility, rollback; screenshots; guided demo script | `docs/SETUP.md`, `docs/THIRD_PARTY_LICENSES.md`, `docs/TEST_MAPPING.md`, `docs/STATUS.md`, `docs/acceptance/WALKTHROUGH.md`, `docs/acceptance/DEMO_SCRIPT.md` (16 of 16 against the box app at 15:16 IST), limits in section 5 | **Partial**: no architecture diagram and no rollback section in `docs/` (G-6). `docs/STATUS.md` line 39 still calls the e2e job opt-in and a placeholder (G-2) |
| 12 | Final discrepancy table | Section 2 | **Done** |

## 2. Discrepancy table (final at `0f32d4d`)

| Capability | Claimed | Proven | Test | Remaining |
| --- | --- | --- | --- | --- |
| Public URL ingest and pinning | Public GitHub only, anonymous, pinned SHA | CI + local + box app | `tests/api`, `tests/security/test_repo_urls.py`, `test_fetch_limits.py` | none (F-6, O-9 fixed) |
| Sandboxed index (no network, no target code) | `unshare -rn`, credentials stripped, caps | CI + local | CT15, `test_outbound.py`, `test_no_key_and_caps.py`, `tests/unit/test_fetch_cleanup.py` | none (O-1 fixed) |
| Evidence statuses on fsft | 4,642 = 4,538/36/59/9, 12 rejected | CI | contract, regression | none |
| Evidence statuses on other Python code | Validators judge claims correctly | Local re-index: 0 rejected on itsdangerous and markupsafe | `tests/e2e/test_python_package_patterns.py` | none (F-4, F-5 fixed; the box app re-indexed at `0f32d4d` shows 0 rejected, O-14) |
| JavaScript evidence | Imports verified (D-030) | 107 of 107 Express imports verified and correct | `tests/e2e/test_express_patterns.py` | L-2: JS calls, references and instantiations stay unvalidated |
| Non-ASCII and odd file names | Any public repo | CI | `test_hostile_repo.py` | none (F-1, F-2 fixed) |
| Overview, graph, trace, review | Real data, unknowns shown | CI on the fsft seed; box app 16 of 16 | `demo_walk.cjs`, `real_snapshot.cjs`, `web/e2e` | L-6: graph truncation is reported, not avoided |
| Trace completeness | "Complete" only when every step is recorded | API `complete: false` with unresolved-call gaps; UI says why | `test_express_patterns.py`, demo 6b, `web/e2e/trace.spec.ts` | none (F-9, O-2 fixed) |
| Route, component and source pages | Route/API inventory screen (charter 4B) | Box app pages render real data | `web/e2e` inventory specs | L-3: Express `forEach` mounts not composed |
| History | Timeline, lifecycle, co-change, milestones, compare | CI + Git spot-checks | `tests/history`, `SECOND_REPO.md`, `EXPRESS.md` | Compare falls back to an identity diff (STATUS.md, H3); O-6 fixed (lineage restart disclosed) |
| No-key explain | Useful answers with citations | Box app, fsft | `tests/explain`, demo 10 and 11 | L-5 (O-13 fixed at `033e1f8`) |
| Co-change in explain | A pattern, never a cause, fact or code structure | CI | `tests/e2e/test_cochange_explain.py`, `tests/explain` | none (F-8, O-4 fixed) |
| Optional provider chat | Browser-side, consent, BYOK | CI and box app, stub provider | `chat_g5.cjs`, `web/e2e/chat.spec.ts` | L-7, L-8 |
| Persistence detection | FastAPI/SQL path | fsft | regression | L-4: Mongoose not recognised |
| Mobile and accessibility | Touch, 360 px, WCAG 2.2 AA | CI on the fsft seed | `real_snapshot.cjs`, `web/e2e` | No screen-reader pass |
| Performance | Not specified in numbers | Local baseline at `0f32d4d` | `tests/perf/bench.py` | L-1 (O-5) |
| CI | All suites | Run 39930532720 green on `0f32d4d`, e2e on the real fsft seed | `.github/workflows/ci.yml` | none |

## 3. Findings (final status at `0f32d4d`)

| Id | Severity | Owner | Summary | Final status and evidence |
| --- | --- | --- | --- | --- |
| F-1 | High | Traces (adapter) | A non-ASCII tracked file name failed the whole index with `E_PATH` | **Fixed**. `test_hostile_repo.py::test_non_ascii_path_indexes` passes in CI 39930532720 (no xfail) |
| F-2 | Low | Traces (views) | Source view refused names starting with `-` | **Fixed** (D-028). `test_hostile_repo.py` passes in CI 39930532720 |
| F-3 | Medium | Traces (API) | 422 envelope echoed rejected input, including a submitted key | **Fixed**. `test_no_key_and_caps.py::test_submitted_key_not_echoed` passes in CI 39930532720; `chat_g5.cjs` finds no key in API responses or logs |
| F-4 | High | Traces (Python validator) | Relative imports were rejected | **Fixed**. `test_relative_imports_not_rejected` passes in CI. Local re-index at `0f32d4d`: itsdangerous 0 rejected (was 46 imports + 1 call), markupsafe 0 (was 2) |
| F-5 | Medium | Traces (Python validator) | Calls into `@typing.overload` methods were rejected | **Fixed**. `test_overload_call_to_implementation_not_rejected` passes in CI; the itsdangerous call rejection is gone on re-index |
| F-6 | Low | Traces (API / ingest) | Nonexistent SHA left a failed snapshot row and an empty cache folder | **Fixed**. `tests/api/test_index_jobs.py` (422 `sha_not_found`, no job, no row) in CI. Worker path re-run at `0f32d4d`: job failed `sha_not_found`, `snapshot_id` NULL, no snapshot row, no cache folder (`.traces-data/acceptance/final/f6_worker.txt`) |
| F-7 | Medium | Traces UI (explain engine) | No-key explain matched keywords | **Fixed**. Box app: "What does create_item depend on?" gives `create_item depends on get_db` and `get_current_user`, uses Item, returns ItemPublic and the persistence path, all verified. "What changed in commit 9d703df25491?" cites that commit's records (343 items, first 8 listed) |
| F-8 | Medium | Traces (explain, history) | History questions ignored the file they named | **Fixed**. Box app: "Which files changed together with backend/app/crud.py?" and the two-file question both answer crud.py and test_users.py, 5 of 26, as a pattern with the caveat |
| F-9 | Medium | Traces (views, trace) | A trace called itself complete while calls were unresolved | **Fixed**. Express re-index: the `register` trace has `complete: false`, `incomplete_reasons` "gaps: 1" and "3 step(s) rest on relationships that are not verified or observed", and a gap listing `userService.createUser` and `tokenService.generateAuthTokens`. fsft `read_items` on the box app shows "Incomplete: this trace has 1 step with calls the trace cannot follow" (demo 6b). `test_express_patterns.py` passes without xfail in CI |
| F-10 | High (JS) | Traces (validators) | No JavaScript validator; 0 of 107 correct `require` imports verified | **Fixed for imports** (D-030). `/meta` lists `javascript: typescript@6.0.3 parser, imports only (D-030)`. Express re-index: 107 verified, all imports. JS calls stay unvalidated (L-2) |
| F-11 | Low | Traces (explain) | `POST /register` answered "no README or manifest records" | **Fixed**. Express re-index: the answer cites the route at `src/routes/v1/auth.route.js:9`, its reference to `register`, and the manifest history. It says runtime behaviour is not established and shows the README heading and frameworks as interpretations (L-5) |
| B-1 | Medium | Box app operator (Architect1) | Box web 5731 proxied to port 8000, not 8731 | **Fixed**. At 14:51 IST the 5731 process environment has `TRACES_API_URL=http://127.0.0.1:8731`, and `/meta` is identical through both ports. All three walks pass through 5731 |
| O-1 | Note | Traces (ingest) | No final clone-size check after git exits | **Fixed**. `ingest/fetch.py` checks once more after git exits; `tests/unit/test_fetch_cleanup.py` in CI |
| O-2 | Note | Traces (views) | Gap reason said "no outgoing static relationship" when the only one was rejected | **Fixed**. Box app, itsdangerous `TimestampSigner::validate`: "1 outgoing static relationship(s) from this step are hidden (1 rejected); send include_rejected=true to see rejected ones", with `hidden_rejected: 1` |
| O-3 | Note | Traces (components) | A library's `src/<pkg>` was labelled `backend` | **Fixed**. itsdangerous re-index: `src/itsdangerous` layer `library`, with the rule `library-v1:no-app-entrypoint` and a reason. The box app shows `library` after its re-index (O-14) |
| O-4 | Note | Traces (explain) | A summary sentence cited a co-change record without the caveat | **Fixed**. The new assertion in `test_cochange_explain.py` (every citing sentence carries the caveat) passes at `0f32d4d` and fails on the `e532644` engine with the original "Taken together ..." sentence |
| O-5 | Note | Traces (views) | `graph` and `trace` are about ten times slower than the other read endpoints on fsft | **Limit L-1**. Re-run at `0f32d4d`: graph p50 581 ms, p95 674 ms (was 543, 636); trace create_item p50 797 ms, p95 938 ms (was 541, 625). Trace is about 47 % slower than at `e532644`, probably the F-9 unresolved-call gaps; still under 1 s at p95 |
| O-6 | Note | Traces (history) | Co-change counted a path from its latest re-add without saying so | **Fixed** (D-H15). Express re-index: the sentence adds "History for src/services/user.service.js restarts after 1 delete and re-add gap in the analysed range; commits before the last re-add are not counted for this path" |
| O-7 | Note | Traces (routes) | Express `forEach` mounts are not composed | **Limit L-3**. Express re-index: routes still show `POST /register`, not `/v1/auth/register`. Middleware mounts are now flagged `mount` (`USE /v1`, `USE /v1/auth`) |
| O-8 | Note | Traces (views, persistence) | Mongoose persistence not recognised | **Limit L-4**. Express re-index: "Does register write to the database?" answers "No persistence path is recorded in this snapshot." (unknown, not invented) |
| O-9 | Note | Traces (API / ingest) | Pre-fix F-6 leftovers in the box store | **Fixed** (startup cleanup, `95eb2c5`). Box store, read-only, at 14:56 IST: no markupsafe snapshot row (0 rows with SHA `0000000000...`), no `.cache/targets/github.com__pallets__markupsafe/` folder, `GET .../markupsafe/snapshots` returns `[]`. The failed job stays visible with `snapshot_id` NULL |
| O-10 | Note | Traces UI | Provider key in plain text in browser storage | **Limit L-7** (by design) |
| O-11 | Note | Traces UI | Manifest rows hashed the statement only, not the `(label, where)` prefix | **Fixed** (#37, `eba1dee`). `chat_g5.cjs` now checks the sha256 and length of each exact line sent; 13 of 13 in CI 39930532720 and on the box app |
| O-12 | Note | Traces (explain) | The 96-file move came third | **Fixed** (#36). Box app: the summary first, then `9d703df` 96 files, then the 7-file and 4-file moves. `demo_walk.cjs` step 10 asserts the order |
| O-13 | Note (new) | Traces UI (explain engine) | Since `81d7d93` (F-7 intents), "Does create_item write to the database at runtime?" returns only "Static evidence cannot show runtime behavior, so how this behaves when the code runs is unknown." At `b37eef2` it also cited the verified fact "create_item has a statically established persistence path through get_db". The test `test_runtime_questions_are_only_unknown` makes this intended, but the answer no longer points to the static evidence a reader can check | **Fixed at `033e1f8`** (#41, `46218ce`). Box app (restarted on `033e1f8` at 15:52 IST, 5731 proxying to 8731): the answer is the unknown "Static evidence cannot show runtime behavior, so how this behaves when the code runs is unknown." plus the fact "The evidence records that create_item has a statically established persistence path through get_db, at backend/app/api/routes/items.py:68 (verified).", citing 1 claim. `demo_walk.cjs` step 11 asserts both: 16 of 16 at 15:56 IST. `tests/explain` 99 passed locally at `033e1f8`, including the new `test_runtime_static.py`. Before the fix it was bisected on a copy of the box store: `b37eef2` gave both sentences, and `81d7d93` to `0f32d4d` gave only the unknown. Evidence: `.traces-data/acceptance/final/explain_o13_033e1f8.json` |
| O-14 | Note (new) | Box app operator (Architect1) | The box store's fsft and itsdangerous evidence was indexed before `b37eef2` and before migration 0003. `isolation` was empty, and itsdangerous showed the 47 F-4/F-5 rejections and the `backend` layer | **Fixed** by the box re-index at `0f32d4d` (15:12 IST). Both snapshots have `isolation: unshare` (`unisolated: false` in the API). fsft: 4,642 edges = 4,538/36/59/9, 12 rejected (3 injected), validation canonical hash `73db432be3babab4`, adapter `45600280cb496a67`, 18,480 claims with every status count unchanged, history complete with 8,464 records. itsdangerous: 0 rejected, layer `library`. Demo step 13 now asserts no rejected claims |
| O-15 | Note (new, mismatch) | Architect1 (expectation), Traces validators (cause) | Architect1 expected the itsdangerous counts to be unchanged by the re-index. Totals are unchanged: 3,312 claims (1,062 nodes, 1,906 relationships, 344 unresolved references), 674 CodeGraph edges, and the adapter hash `7c06d935eb8547db`. Statuses changed: verified 310 to 357, observed 2,577 to 2,669, rejected 93 to 0, missing_location 46 to 0, unvalidated 286 (same). Edge statuses: verified 310 to 357, observed 3 to 49, rejected 47 to 0, missing_location 46 to 0, unvalidated 268 (same). The validation hash changed from `8c4679dae34692ae` to `1a2b4bd07800c775` | **Accepted by Architect1**: the itsdangerous status shift is what the F-4/F-5 fixes predict. Nothing was adjusted. The new counts equal Lab's independent offline re-index at `0f32d4d` (`.traces-data/acceptance/final/pylib/statuses.txt`: 357 verified, 2,669 observed, 286 unvalidated, 0 rejected). The change is what the F-4 and F-5 fixes predict: 46 relative imports and 1 overload call no longer rejected. Lab reads this as the fixes landing, not a regression |

## 4. Gaps

| Id | Owner | Gap | Status |
| --- | --- | --- | --- |
| G-1 | Traces Lab | CI e2e on the real fsft seed | **Closed (CI)**: run 39930532720, e2e job seed fsft, 94 passed, 4 skipped, real-snapshot 21 of 21 |
| G-2 | Architect | `docs/STATUS.md` line 39 says the e2e job is opt-in and a placeholder | **Open** at `0f32d4d`. Architect1 updates STATUS.md |
| G-3 | Traces UI | Routes, Components and Source pages were placeholders | **Closed**: the box app renders real routes, components and source (`ac8e191`) |
| G-4 | Traces Lab | Second stack | **Closed (local)**: Express re-indexed at `0f32d4d` (row 7) |
| G-5 | Traces UI | Provider chat end to end | **Closed (CI) with a stub provider**: `chat_g5.cjs` 13 of 13 in run 39930532720 and on the box app. Live provider: L-8 |
| G-6 | Architect | No architecture diagram or rollback section in `docs/` | **Open** at `0f32d4d` |
| G-7 | Traces Lab | Performance baseline | **Closed (local)**: re-run at `0f32d4d` in [acceptance/PERF.md](acceptance/PERF.md) |
| G-8 | Traces Lab | axe and 360 px on real data | **Closed (CI)**: run 39930532720 |
| G-9 | Traces Lab | History skips | **Closed (CI)**: 176 passed, 0 skipped in run 39930532720 |

## 5. v1 limits

These are the only open items accepted as limits, as named by Architect1. Anything that still fails or does not match is a finding in section 3 (none open at `033e1f8`; O-15 accepted) or a gap in section 4 (G-2, G-6).

| Id | Owner | Limit | Evidence at `0f32d4d` |
| --- | --- | --- | --- |
| L-1 (O-5) | Traces (views) | `graph` and `trace` are the slowest read endpoints on fsft | graph p50 581 ms, p95 674 ms; trace p50 797 ms, p95 938 ms; local, one bench run, [acceptance/PERF.md](acceptance/PERF.md) |
| L-2 (D-030) | Traces (validators) | JavaScript validation covers imports only; calls, references, instantiations and named import bindings are deferred to v1.1 and are never verified | Express: 153 calls, 21 instantiates and 37 references unvalidated; 107 imports verified |
| L-3 (O-7) | Traces (routes) | Express routers mounted with `forEach` over an array are not composed into full paths | Express: `POST /register` instead of `/v1/auth/register` |
| L-4 (O-8) | Traces (views, persistence) | Mongoose persistence is not recognised | Express: "No persistence path is recorded in this snapshot." |
| L-5 | Traces (explain) | README headings and framework names from manifests are shown as uncited interpretations | Express `POST /register`: README and manifest sentences have 0 citations and say they are documentation or named libraries, not verified facts |
| L-6 (D-028, review F4) | Traces (graph) | The graph truncates at `limit` and reports what it cut (`truncated_counts` by status); it does not page | D-028 |
| L-7 (O-10) | Traces UI | The BYOK key is kept in plain text in sessionStorage, or localStorage with "Remember on this device" (with a warning) | It never reaches the Traces API, logs, store or sent record (`chat_g5.cjs`, CI and box app) |
| L-8 | Traces UI | Live-provider chat is untested in v1: no paid key, no local Ollama | Only the stub provider path is verified (G-5) |
