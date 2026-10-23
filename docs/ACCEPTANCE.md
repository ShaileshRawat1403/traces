# Traces v1 acceptance (charter section 7)

Owner: Traces Lab (QA, Integration, CI and Security seat). Living document, updated at each Lab checkpoint.
Last update: 2026-10-23 12:40 IST, branch `ws/lab-acceptance` (PR #22 into `build/traces-v1`).

Labels used below:
- **CI**: a real GitHub Actions run passed. Run id and commit are given.
- **Local**: run on the Traces Lab box only. Not a CI result.
- **Box app**: checked read-only against the running review app (`/workspace/traces-review/traces`, build `35499bc`, web 5731, API 8731).

CI runs referenced:
- `39716507167`: push, `build/traces-v1` @ `35499bc`, success, 9 of 9 jobs. unit 47 passed 2 skipped, api 47, contract 17, regression 15, e2e 54 passed 2 skipped.
- `39914041785`: push, `ws/lab-acceptance` @ `6384c78`, success, 11 of 11 jobs. Adds security 122 passed 3 xfailed, history 163 passed 2 skipped (see G-9), explain 11, vitest 89.

Detail: [acceptance/SECOND_REPO.md](acceptance/SECOND_REPO.md), [acceptance/DEMO_SCRIPT.md](acceptance/DEMO_SCRIPT.md), [../tests/security/README.md](../tests/security/README.md), [../ci/README.md](../ci/README.md).

## 1. Section 7 checklist

| # | Charter item | Proof | Status |
| --- | --- | --- | --- |
| 1 | Valid public GitHub URL, index status, pinned SHA, populated overview | CI: `tests/api` (run 39716507167, includes `test_index_baseline.py`, the product index of fsft@b1125d8). Local: `POST /repos` + `POST /index-jobs` for itsdangerous@672971d (6 s) and markupsafe@4e11127 (8.5 s) on a fresh store. Box app: demo steps 1 to 3 | **Pass** (CI for API; browser on real data local only, G-1) |
| 2 | Interactive graph, focus, follow cross-file edges, open pinned source | Box app: demo steps 4, 5, 15 (`tests/e2e/demo_walk.cjs`, 15 of 15 local). CI: `web/e2e/graph.spec.ts` on the synthetic seed | **Pass** local on real data; CI only on synthetic data (G-1) |
| 3 | fsft@b1125d8: nine Task 002 links traceable, persistence static only, H1/H2 inferred | CI: `tests/regression/test_regression.py::test_nine_links_and_library_hops` (runs 39716507167, 39914041785). Box app: demo step 6 (10 steps, 2 inferred library steps, 1 gap, "Static persistence path") | **Pass** (CI) |
| 4 | Nine wrong CodeGraph imports not verified; three injected negatives rejected; Task 002 16+8 still pass | CI: contract 17 passed (CT1 to CT16 plus count), regression 15 passed (RT1 to RT8, distribution 4,642 = 4,538/36/59/9, canonical hashes). Box app: demo step 7, 12 rejected = 9 imports + 3 injected | **Pass** (CI) |
| 5 | View and explain a Git-backed architecture change with cited commits; co-change is not causality | CI: `tests/history` (163 passed in run 39914041785; 165 passed 0 skipped local). Box app: demo steps 8 to 10 (milestone 9d703df "Move new-frontend to frontend", 96 renames confirmed with `git show -M50%`; co-change says "not evidence of a code dependency") | **Pass** for view; **partial** for explain (F-7) |
| 6 | No-key mode useful; provider mode refuses unsupported claims, citations, privacy controls | CI: `tests/explain` 11, `tests/security/test_no_key_and_caps.py` (explain cites stored claims, bundle is a manifest, keys cannot be submitted). Box app: demo steps 10, 11 | No-key **pass** (CI). Provider mode **gap** (G-5); F-3 open |
| 7 | Second, different public repo indexed and explored; unknowns instead of invented links | Local and box app: itsdangerous@672971d verified independently (identical 3,312 claim ids, Git spot-checks 30/30, 20/20, 30/30). Overview shows purpose and entry points as unknown; no routes or frameworks invented | **Partial**: works, but Python only (G-4), and F-4/F-5 reject true claims on it |
| 8 | Errors, unsupported types, missing keys, index failures, rate limits, malicious paths, oversized repos fail safely and visibly | CI: `tests/security` 122 passed, 3 xfailed (run 39914041785). Covers 28 bad URLs, traversal, symlinks, caps, timeouts, 429, no-key, failed-job visibility | **Pass** with open findings F-1, F-2, F-3, F-6 |
| 9 | Desktop and mobile browser, touch navigation, evidence inspection | CI: Playwright desktop + android-360 with axe, 54 passed, on the synthetic seed. Box app: demo steps 14, 15 on a 360 px touch context (tap Open evidence; no sideways scroll) | **Pass** local on real data; CI real-data run pending (G-1, G-8) |
| 10 | CI: unit, adapter/schema, regression, API, e2e browser; lint/types/build; no critical security risk; no unintended outbound calls; no secrets | CI run 39914041785: lint, types, unit, explain, vitest, build, contract, regression, api, history, security, e2e all green. Outbound: `tests/security/test_outbound.py` (worker clones only the target; app serves inside an empty `unshare -rn` namespace; audit hook sees no off-loopback connect). Secrets: `git log -p --all` scan for GitHub, OpenAI, AWS, Slack and private-key patterns found only the fake test token in `test_repo_urls.py` | **Pass** (CI), with G-1 and G-9 |
| 11 | Docs: setup, architecture, licenses, coverage, limitations, reproducibility, rollback; screenshots; guided demo script | `docs/SETUP.md`, `docs/THIRD_PARTY_LICENSES.md`, `docs/TEST_MAPPING.md`, `docs/STATUS.md`, `docs/acceptance/WALKTHROUGH.md` (screenshots), `docs/acceptance/DEMO_SCRIPT.md` (checked 15 of 15 against the box app) | **Partial**: no architecture diagram and no rollback section found (G-6); STATUS.md e2e text stale (G-2) |
| 12 | Final discrepancy table | Section 2 below | **In progress** |

## 2. Discrepancy table

| Capability | Claimed | Proven | Test | Gap |
| --- | --- | --- | --- | --- |
| Public URL ingest and pinning | Public GitHub only, anonymous, pinned SHA | CI + local + box app | `tests/api`, `tests/security/test_repo_urls.py`, `test_fetch_limits.py` | F-6: nonexistent SHA leaves a failed snapshot row and empty cache dir |
| Sandboxed index (no network, no target code) | `unshare -rn`, credentials stripped, caps | CI + local | CT15, `test_outbound.py`, `test_no_key_and_caps.py` | O-1: clone size checked every 0.5 s, no final check after git exits |
| Evidence statuses on fsft | 4,642 = 4,538/36/59/9, 12 rejected | CI | contract, regression | none |
| Evidence statuses on other Python code | Validators judge claims correctly | Not true on library code | `tests/e2e/test_python_package_patterns.py` (xfail) | F-4 relative imports rejected (46 of 47 itsdangerous rejections, 2 of 2 markupsafe); F-5 `@overload` call rejected |
| Non-ASCII file names | Any public repo | Fails closed | `test_hostile_repo.py::test_non_ascii_path_indexes` (xfail) | F-1: whole index fails with `E_PATH` |
| Source view | Any tracked path, traversal refused | Traversal refused; odd names readable | `test_hostile_repo.py` | F-2: names starting with `-` refused |
| Overview, graph, trace, review | Real data, unknowns shown | Box app, 15 of 15 demo steps | `tests/e2e/demo_walk.cjs` (local) | G-1 CI uses synthetic data; O-2 gap reason text when only a rejected edge exists |
| Route, component and source pages | Route/API inventory screen (charter 4B) | API serves them; UI pages show "scheduled for the next UI checkpoint" | box app `F/routes`, `F/components` | G-3 |
| History | Timeline, lifecycle, co-change, milestones, compare | CI + Git spot-checks on itsdangerous | `tests/history`, `SECOND_REPO.md` | Compare falls back to identity diff (STATUS.md, H3) |
| No-key explain | Useful answers with citations | Grounded, but retrieval is keyword based | `tests/explain`, demo 10, 11 | F-7 |
| Optional provider chat | Browser-side, consent, BYOK | Bundle and manifest only | `test_no_key_and_caps.py` | G-5; F-3 echoes rejected input |
| Second repo, different stack | Not overfit to FastAPI + React | Python library only | `SECOND_REPO.md` | G-4 Express or Django not run; layer rule calls a library `backend` |
| Mobile and accessibility | Touch, 360 px, WCAG 2.2 AA | CI axe on synthetic; local touch on real data | `web/e2e` (android-360), demo 14, 15 | G-8 axe on real snapshot not yet run |
| Performance | Not specified in numbers | Index wall time only: fsft 23 s, itsdangerous 31 s incl. queue (box app); itsdangerous 6 s, markupsafe 8.5 s (local) | none yet | G-7 |
| CI | All suites | Run 39914041785 green | `.github/workflows/ci.yml` | G-9 |

## 3. Findings (open)

| Id | Severity | Owner | Summary | Repro |
| --- | --- | --- | --- | --- |
| F-1 | High | Traces (adapter / `traces.core.common` blob reader) | A non-ASCII tracked file name makes the adapter fail with `E_PATH`; the whole repository cannot be indexed. Likely `git ls-tree -r` without `-z` | `tests/security/test_hostile_repo.py::test_non_ascii_path_indexes` |
| F-2 | Low | Traces (`evidence/views.safe_repo_path`) | Source view refuses names starting with `-` with a wrong message | `GET .../source?path=-rf.py` on the hostile fixture |
| F-3 | Medium | Traces (`api/app.py` validation handler) | 422 envelope echoes rejected input, including a submitted key | `tests/security/test_no_key_and_caps.py::test_submitted_key_not_echoed` |
| F-4 | High | Traces (`validators/python_ast.py` import check) | Relative imports are rejected (ignores `ImportFrom.level`) | `tests/e2e/test_python_package_patterns.py::test_relative_imports_not_rejected` |
| F-5 | Medium | Traces (`validators/python_ast.py` binding resolution) | Calls into `@typing.overload` methods resolve to the first stub; correct edge rejected | `...::test_overload_call_to_implementation_not_rejected` |
| F-6 | Low | Traces (API / ingest) | Nonexistent SHA: full clone, then a permanent failed snapshot row and an empty cache dir | `POST /repos/github.com__pallets__markupsafe/index-jobs {"sha":"000...001"}` (box app job `j_26a08a94da4e467dbba0`) |
| F-7 | Medium | Traces UI (explain engine, D-023) | No-key explain matches keywords: "What does create_item depend on?" lists `create_random_item` and SDK imports instead of `create_item depends_on get_db`; "What changed in commit 9d703df25491?" answers with an unrelated persistence fact | `POST F/explain` on the box app with those questions |
| O-1 | Note | Traces (ingest) | No final clone-size check after git exits | code read, `ingest/fetch.py::_clone_capped` |
| O-2 | Note | Traces (views) | Trace gap reason says "no outgoing static relationship" when the only one is rejected and hidden | itsdangerous trace from `TimestampSigner::validate` |
| O-3 | Note | Traces (components) | Layer rule labels a library's `src/<pkg>` as `backend` | itsdangerous overview |

## 4. Gaps (open)

| Id | Owner | Gap | Plan |
| --- | --- | --- | --- |
| G-1 | Traces Lab | CI e2e seeds a synthetic 4-file repo (`scripts/e2e_seed.py`, `octo/synth`), not the real fsft snapshot | Checkpoint 4: seed fsft@b1125d8 from the cached clone in CI; keep the synthetic seed as the fast local option |
| G-2 | Architect | `docs/STATUS.md` says the e2e job is an opt-in placeholder; CI runs it on every push | Architect1 updates STATUS.md |
| G-3 | Traces UI | Routes, Components and Source pages are placeholders in the UI | UI checkpoint |
| G-4 | Traces Lab | Second repo is Python; no Express or Django app run | After checkpoint 4 |
| G-5 | Traces UI | Provider (BYOK) chat path not exercised end to end; no AI calls are allowed in Lab runs. PR #20 (ws/ui-chat) landed in `build/traces-v1` @ `01c5023` after the runs above; the box app (`35499bc`) does not have it | Lab: test consent, rejected-claim exclusion and the outbound manifest with a stub provider (no network) |
| G-6 | Architect | No architecture diagram or rollback section found in `docs/` | Architect |
| G-7 | Traces Lab | No API latency (p50/p95) or index-time benchmark yet | Checkpoint 4 |
| G-8 | Traces Lab | axe and android-360 on the real snapshot not yet in CI | Checkpoint 4 (with G-1) |
| G-9 | Traces Lab | CI run 39914041785 skipped 2 history no-network tests (no user namespaces in that job) | Fixed on `ws/lab-acceptance` after `a33853c`: the history job enables user namespaces and fails on any skip; needs a CI run to confirm |
