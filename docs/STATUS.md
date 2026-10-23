# Status (Traces v1)

State of `build/traces-v1` at **`033e1f8`** (merge of PR #41), written 2026-10-23 IST. Every seat PR through #41 is merged. Lab's final acceptance pass ran at `0f32d4d`; `033e1f8` adds only #39 (history contract, D-H16), #40 (Lab final ACCEPTANCE.md) and #41 (O-13 explain fix). Authority is the code and CI, not seat notes. Acceptance evidence is in [ACCEPTANCE.md](ACCEPTANCE.md) (Lab). The review package is [review/V1_REVIEW_PACKAGE.md](review/V1_REVIEW_PACKAGE.md), with [ARCHITECTURE](review/ARCHITECTURE.md) and [ROLLBACK](review/ROLLBACK.md).

## What each module does

| Module | Owner | What it does at `0f32d4d` |
| --- | --- | --- |
| `backend/traces/ingest` | Traces | Public GitHub HTTPS URLs only. Anonymous `ls-remote` visibility and HEAD check. A requested SHA is checked with a shallow, credential-free fetch (unknown is 422 `sha_not_found`). Capped clone (1024 MB, 900 s, 100,000 files, 1024 MB tree) in its own process group, with hooks, LFS and submodules off; cleanup runs on every failure (D-021, D-028, D-031) |
| `evidence/jobs.py`, `evidence/index.py` | Traces | Index jobs on a thread pool. Isolation is resolved first and fails closed (`E_ISOLATION`); `TRACES_ISOLATION=off` is an explicit dev override stored on the snapshot (D-026). Then clone, CodeGraph, adapter, validators, store, report, history. RSS watchdog 6144 MB, index timeout 1800 s (D-022) |
| `workers/sandbox.sh` | Traces | `unshare -rn` (no network), HOME and telemetry overridden, secrets stripped, ulimits. Runs CodeGraph, the adapter and the validators |
| `toolchain/` | Traces | CodeGraph 1.6.2 and TypeScript 6.0.3, integrity-pinned, installed with `--ignore-scripts` |
| `backend/traces/adapter` | Traces | Fail-closed CodeGraph-to-evidence 0.3 mapping, `claim_id` v3, consolidation, EOF rules, isolation probe check 4.7 |
| `backend/traces/validators` | Traces | Python (CPython 3.14 `ast`, FastAPI rules R1-R4, A3 qualified per D-032), TypeScript (Compiler API, resolution stops at the checkout, D-025), JavaScript **imports only** (TypeScript parser plus Node CommonJS resolution, D-030). Paths listed with `git ls-tree -z` |
| `evidence/store.py`, migrations | Traces | SQLite, WAL, per-thread connections. Migrations 0001-0003 (0003: snapshot isolation, consent fields). Startup removes empty failed `sha_not_found` snapshot rows (O-9, D-031) |
| `evidence/report.py` | Traces | `chain.json` and `coverage.json` for baseline runs (F7) |
| `evidence/views.py`, `evidence/components.py` | Traces | Overview (README heading and frameworks as interpretation), components with layer `reason` and a `library` layer (D-029), routes with `label` and Express `USE` mounts, graph and trace (rejected hidden with `hidden_counts`; `truncated_counts`; `injected` flag; trace gaps with `unresolved_calls` and `incomplete_reasons`, D-031), source by `git cat-file` |
| `backend/traces/history` | Traces History | Timeline, lifecycle, churn, hotspots, co-change, milestones, rationale; aliases opt-in (D-H14); lineage-restart caveat (D-H15). Runs in the index job with hardened `gitcmd` (`protocol.allow=never`, no lazy fetch, RLIMITs), not in its own namespace (D-H16). fsft default digest `2fb288167ebf`, 8,402 records |
| `backend/traces/explain` | Traces UI | No-key, deterministic: intent routing (`intents.py`), cited answer or `unknown`. Co-change answered only as a history pattern with the caveat (#24). A runtime persistence question gives the runtime unknown, then the verified static persistence path (O-13, #41). `chat/bundle` returns a prompt and an outbound manifest; each row hashes the exact line sent (O-11) |
| `backend/traces/api` | Traces | FastAPI, OpenAPI contract in `docs/contracts/openapi.json`. `PUT /repos/{id}/ai-consent` (D-027). 422 bodies never echo input (F-3). `/meta` reports probed isolation |
| `web/` | Traces UI | React, React Router, TanStack Query, Cytoscape.js, Shiki, Radix. Home, job, overview, components, routes, graph and evidence drawer, trace, history, ask, claims, source, settings, BYOK chat |

## Tests and CI

CI run on `033e1f8`: push [39938654127](https://github.com/ShaileshRawat1403/traces/actions/runs/39938654127) and pull_request [39938661185](https://github.com/ShaileshRawat1403/traces/actions/runs/39938661185), both **success, 11 of 11 jobs**. Lab's final pass used the run on `0f32d4d` ([39930532720](https://github.com/ShaileshRawat1403/traces/actions/runs/39930532720)). Counts from the `033e1f8` job logs:

| CI job | Command | Result |
| --- | --- | --- |
| lint | `ruff check backend tests` | pass |
| types | `mypy`, web `tsc` | pass |
| unit | `pytest tests/unit`, `pytest tests/explain` | 87 passed, 3 skipped (live GitHub); explain 99 passed |
| api | `pytest tests/api` | 95 passed |
| web-build | vitest, `check:api`, `vite build` | vitest 16 files, 125 tests passed; API types current; build pass |
| target | pinned fsft@b1125d8 cache, hardened git | pass |
| contract | `pytest tests/contract` (CT1-CT16, fresh baseline, `unshare -rn`) | 17 passed |
| regression | `pytest tests/regression` (RT1-RT8, 0.4 migration, report) | 16 passed |
| security | `pytest -rxXs tests/security tests/e2e` (Python e2e pattern tests) | 136 passed, 0 xfailed |
| history | `pytest tests/history` on the full-history fsft clone; any skip fails | 176 passed |
| e2e | `scripts/e2e_ui.sh` with `TRACES_E2E_SEED=fsft` | Playwright 94 passed, 4 skipped by design; `real_snapshot.cjs` 21 of 21; `chat_g5.cjs` 13 of 13 |

### Which end-to-end checks are real

| Check | Data | Where it runs |
| --- | --- | --- |
| Playwright (`web/e2e`, desktop and android-360, axe) | **Real**: fsft@b1125d8 from the cached full-history clone, indexed with history by `scripts/e2e_seed.py --seed fsft` | CI `e2e` job. Locally `scripts/e2e_ui.sh` defaults to the 4-file synthetic seed (`octo/synth`) unless `TRACES_E2E_SEED=fsft` |
| `tests/e2e/real_snapshot.cjs` | Real fsft snapshot: nine screens, axe WCAG 2.2 AA at 1280 px and 360 px touch | CI `e2e` job (fsft seed only) |
| `tests/e2e/chat_g5.cjs` | Real fsft snapshot, BYOK chat against an in-process **stub** provider | CI `e2e` job (fsft seed only) |
| `tests/e2e/demo_walk.cjs` | The running box app (15 demo steps, read-only) | Local only, not in CI ([acceptance/DEMO_SCRIPT.md](acceptance/DEMO_SCRIPT.md)) |
| `tests/e2e/test_*.py` | Worker-indexed scratch repos (co-change explain, Express patterns, Python package patterns) | CI `security` job |

A live LLM provider is not tested in v1 (no paid key, no local model).

## Merged into `build/traces-v1`

| PR | Merge SHA | Branch | What landed |
| --- | --- | --- | --- |
| #1 | `bcc9c2c` | `task/002-evidence-core` | Task 002 research and Decision 002-B closeout (on `main`) |
| #3 | `7d93fae` | `ws/history-contract` | History contract |
| #5 | `1bfb082` | `ws/history-core` | History core |
| #6 | `0586697` | `ws/ui-shell` | UI shell |
| #8 | `358b05c` | `ws/arch-store-concurrency` | Per-thread SQLite connections, WAL |
| #11 | `cc2da0d` | `ws/history-analysis` | History analysis |
| #7 | `8dd6fe5` | `ws/ui-overview` | Overview screen |
| #10 | `a0cc07c` | `ws/ui-graph` | Graph and evidence drawer |
| #12 | `7a34dea` | `ws/ui-trace` | Trace view |
| #13 | `a571299` | `ws/ui-explain` | Deterministic explain, Ask screen |
| #18 | `184dfd3` | `ws/lab-ci` | CI workflow active |
| #14 | `15a5f71` | `ws/ui-explain-tests` | Explain tests in `tests/explain` |
| #9 | `83f5731` | `ws/arch-ingest` | Ingest (D-021), migration 0002 |
| #15 | `80a6606` | `ws/arch-index` | Index jobs, sandboxed worker (D-022) |
| #16 | `a106d84` | `ws/history-runner` | History runner |
| #17 | `3309b83` | `ws/ui-history` | History screens |
| #19 | `f1f026b` | `ws/arch-explain` | Explain wired to the API (D-023) |
| #23 | `86e7b5a` | `ws/history-aliases` | Opt-in aliases (D-H14) |
| #20 | `fa78d58` | `ws/ui-chat` | BYOK chat |
| #22 | `01c5023` | `ws/lab-acceptance` | CI history, explain, vitest jobs; security suite |
| #24 | `525bc1d` | `ws/ui-explain-history` | Co-change is a pattern in explain |
| #25 | `e532644` | `ws/lab-acceptance` | Second repo, ACCEPTANCE.md, demo script |
| #28 | `83fd127` | `ws/lab-acceptance` | fsft e2e seed, real-snapshot checks, perf baseline |
| #27 | `b37eef2` | `ws/arch-security` | Isolation fails closed (D-026), F-1 to F-6, consent endpoint (D-027), D-028; migration 0003 |
| #29 | `0b9b920` | `ws/arch-ui-contract` | Route labels, gap counts, layer reasons, `library` layer (D-029) |
| #30 | `0c1fa0b` | `ws/lab-acceptance` | Express acceptance (G-4) |
| #32 | `adb835e` | `ws/history-lineage-breaks` | Lineage restart caveat (D-H15) |
| #31 | `b98ae5a` | `ws/lab-acceptance` | BYOK chat acceptance with a stub provider (G-5) |
| #26 | `1b10fe8` | `ws/ui-acceptance-fixes` | F-7 intent routing, F-8, G-3 pages, O-2, O-3, O-4 |
| #34 | `227310c` | `ws/ui-contract-wiring` | UI wiring for D-029 fields |
| #35 | `fc7e7b6` | `ws/ui-explain-format` | Format only |
| #33 | `a8b73a4` | `ws/arch-js-validator` | JS imports (D-030), F-9 trace completeness, process groups, F5, `/meta` isolation, O-9 (D-031) |
| #36 | `84d2eda` | `ws/ui-explain-fixes-2` | F-11, F-8 JS, O-12 |
| #37 | `320d4c9` | `ws/ui-manifest-hash` | Manifest rows hash the exact line (O-11) |
| #38 | `0f32d4d` | `ws/ui-trace-f9` | Trace UI for unresolved-call gaps (F-9) |
| #39 | `1313c41` | `ws/history-sandbox-doc` | History contract states real Git sandboxing (D-H16) |
| #40 | `99ae987` | `ws/lab-acceptance` | Lab final acceptance pass (`4289d1e`): ACCEPTANCE.md, demo walk 16 of 16, O-4 guard |
| #41 | `033e1f8` | `ws/ui-o13` | Runtime persistence questions cite the static persistence path (O-13) |

Open and not merged: #4 (integration tracking PR, do not merge), #21 (this review package, ready for review; Shailesh merges it into `build/traces-v1`).

## Not done in v1

- **H3**: the index job passes only the pinned SHA to history (one evidence set), so milestone SHAs are not re-indexed. Compare falls back to an identity diff of static claims (D-024).
- Private repositories. v1 never asks for credentials.
- No server-side LLM. Chat is browser-side BYOK only, with a stub-provider acceptance; a live provider is untested.
- JavaScript calls, references, instantiations and named import bindings are not validated (v1.1, D-030).

## Product limits (honest)

- A relationship the extractor missed is a gap or an absence, not a claim that the link does not exist.
- Co-change and hotspots are history patterns. They are not code dependencies and not causes.
- Library-contract hops (react-hook-form, TanStack Query on the Task 002 chain) stay inferred unless an independent check says otherwise.
- The persistence path on the Task 002 chain is a static path, not a runtime-observed database write.
- Rejected CodeGraph imports and the three injected negatives stay rejected, are flagged `injected_control`, and are hidden from the default graph.
- JavaScript (D-030): only `imports` edges have an independent check. Package, absolute, aliased and computed specifiers are not resolved, so those imports stay unvalidated.
- Express mounts (O-7): routers mounted through a computed `forEach` keep their local path without the prefix. Literal mounts are composed; middleware mounts show as method `USE` with flag `mount`.
- Persistence (O-8): only the FastAPI/SQLModel session path is recognised. Mongoose and other ODMs are not detected; trace and explain say no persistence path is recorded.
- README heading and frameworks on the overview are uncited interpretations, not verified claims.
- Graph p95 about 674 ms and trace `create_item` p95 about 938 ms on fsft (L-1, O-5, [acceptance/PERF.md](acceptance/PERF.md), local, at `0f32d4d`).
- The BYOK provider key is stored in the browser (sessionStorage, or localStorage with "Remember on this device"), by design.
- History Git runs in the index job with network transports refused and RLIMITs, not inside its own `unshare -rn` namespace (D-H16, `docs/contracts/history.md` section 11).
- Graph truncates at `limit` and reports cut edges by status; it does not page (L-6).
- Live-provider chat is untested (L-8).
