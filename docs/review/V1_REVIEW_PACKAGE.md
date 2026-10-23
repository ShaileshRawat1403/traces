# Traces v1 review package (DRAFT, v1 candidate)

> **Draft.** The section 7 checklist is marked **pending Lab final pass at `0f32d4d`**. Lab is refreshing [docs/ACCEPTANCE.md](../ACCEPTANCE.md) now, and its results will be folded into section 4. Do not treat this file as a v1 sign-off until that is done.

| | |
| --- | --- |
| Candidate head | `build/traces-v1` at **`0f32d4d`** (merge of PR #38). All seat PRs #20 and #22-#38 merged |
| CI on the head | push [39930532720](https://github.com/ShaileshRawat1403/traces/actions/runs/39930532720) and pull_request [39930539272](https://github.com/ShaileshRawat1403/traces/actions/runs/39930539272): **success, 11 of 11 jobs** |
| Package updated | 2026-10-23, about 15:00 IST |
| Earlier audit | Architect audit of `35499bc` (12:00-12:20 IST). Results and its findings are kept in sections 9 and 10 |
| Charter | Issue #2, section 7 (acceptance checklist) |
| Companion docs | [ARCHITECTURE.md](ARCHITECTURE.md), [ROLLBACK.md](ROLLBACK.md), [STATUS.md](../STATUS.md), [ACCEPTANCE.md](../ACCEPTANCE.md), [REVIEW_V1_EVIDENCE.md](REVIEW_V1_EVIDENCE.md), [REVIEW_V1_ADDENDUM_b37eef2.md](REVIEW_V1_ADDENDUM_b37eef2.md) |

## 1. How to run it yourself

From the README and [SETUP.md](../SETUP.md). You need `uv` and Node 20.19 or newer, on Linux with unprivileged user namespaces (`unshare -rn true` must succeed; indexing fails closed otherwise).

```bash
git clone https://github.com/ShaileshRawat1403/traces && cd traces
git checkout 0f32d4d
./scripts/start.sh        # or: make start. API http://127.0.0.1:8000, web http://127.0.0.1:5173
# other ports:
TRACES_API_PORT=8731 TRACES_WEB_PORT=5731 ./scripts/start.sh
```

`start.sh` installs from lockfiles (`uv sync --frozen`, `npm ci --ignore-scripts`), starts the API, waits for `/api/v1/health`, then serves the web UI. Open the web UI, paste a public GitHub URL, and follow the index job. Data goes to `.traces-data/`, pinned checkouts to `.cache/`.

Baseline and tests:

```bash
uv run --frozen python -m traces.evidence.pipeline baseline --run-id dev1   # about 1 minute; fetches fsft@b1125d8
uv run --frozen traces import-run .traces-data/runs/dev1                     # load it into the store
make test-fast                       # unit + API
make test                            # everything incl. a fresh baseline (CT1-16, RT1-8)
make lint typecheck                  # ruff, mypy, web tsc
cd web && npm test && npm run check:api && npm run build
TRACES_E2E_SEED=fsft TRACES_E2E_FSFT_REPO=<full-history fsft clone> bash scripts/e2e_ui.sh   # what CI runs
```

## 2. Architecture

Full diagram and module table: [ARCHITECTURE.md](ARCHITECTURE.md).

```mermaid
flowchart LR
  U["Browser: React, Cytoscape.js"] -->|"OpenAPI /api/v1"| API["FastAPI"]
  U -. "BYOK chat after consent; key stays in the browser" .-> LLM[("User's LLM provider")]
  API --> ING["ingest: ls-remote, SHA check, capped clone"]
  ING -->|"anonymous HTTPS"| GH[("github.com public repo")]
  API --> JOB["index job: isolation fails closed"]
  JOB --> SB["workers/sandbox.sh: unshare -rn"]
  SB --> CG["CodeGraph 1.6.2"] --> AD["adapter"] --> VAL["validators: Python ast, TS Compiler API, JS imports only"]
  VAL --> ST[("SQLite store, migrations 0001-0003")]
  JOB --> HIS["history: hardened git, no transports"] --> ST
  API --> VW["views: overview, graph, trace, source"] --> ST
  API --> EX["explain: no-key, cited or unknown; chat bundle + manifest"] --> ST
```

## 3. Seat-to-module map

From [CONTRACTS.md section 6](../CONTRACTS.md).

| Seat | Modules |
| --- | --- |
| Traces | `backend/traces/{evidence,adapter,validators,ingest,core,api}`, `workers/`, `toolchain/` |
| Traces History | `backend/traces/history`, `docs/contracts/history.md`, `docs/history/`, migrations 0100-0199 (none yet) |
| Traces UI | `web/`, `backend/traces/explain`, migrations 0200-0299 (none yet) |
| Traces Lab | `tests/e2e`, `tests/security`, `tests/perf`, CI workflow, `docs/ACCEPTANCE.md`, `docs/acceptance/` |
| Architect | `docs/CONTRACTS.md`, `docs/DECISIONS.md`, `docs/STATUS.md`, `docs/review/`, merges into `build/traces-v1` |

## 4. Section 7 checklist

**All rows: pending Lab final pass at `0f32d4d`.** The "earlier evidence" column is what was established before the final pass; Lab's ACCEPTANCE.md will replace it.

| # | Charter item | State at `0f32d4d` | Earlier evidence (not the final pass) |
| --- | --- | --- | --- |
| 1 | Index a public URL pinned to a SHA; overview | pending Lab final pass at `0f32d4d` | Architect audit PASS at `35499bc` (fsft job, 4,642 edges). CI `api` includes `test_index_baseline` |
| 2 | Graph, focus, cross-file edges, evidence drawer, source | pending Lab final pass at `0f32d4d` | CI `e2e` on the real fsft seed (Playwright 94 passed, 4 skipped); Lab demo walk 15 of 15 on the box app |
| 3 | Nine Task 002 links; persistence static only; H1/H2 inferred | pending Lab final pass at `0f32d4d` | Traces seat review and addendum: exact reproduction; CI `regression` 16 passed |
| 4 | Nine wrong imports never verified; three injected rejected and hidden; 16+8 | pending Lab final pass at `0f32d4d` | CI `contract` 17 and `regression` 16 passed; injected flagged `injected_control` (F3) |
| 5 | Git-backed change explanation; co-change is not causality | pending Lab final pass at `0f32d4d` | Architect finding at `35499bc` fixed by #24; CI `history` 176 passed; `tests/e2e/test_cochange_explain.py` in CI `security` |
| 6 | No-key mode; provider (BYOK) mode with consent and citations | pending Lab final pass at `0f32d4d` | BYOK chat merged (#20); `chat_g5.cjs` 13 of 13 in CI with a **stub** provider. Live provider untested |
| 7 | Second, different public repo | pending Lab final pass at `0f32d4d` | itsdangerous@672971d (Python library) and node-express-boilerplate@179ae84 (Express) run end to end by Lab; JS imports verifiable since #33 |
| 8 | Safe failures | pending Lab final pass at `0f32d4d` | CI `security` 136 passed, 0 xfailed (F-1 to F-3 fixed) |
| 9 | Desktop, mobile, touch, accessibility | pending Lab final pass at `0f32d4d` | CI `e2e`: `real_snapshot.cjs` 21 of 21 (axe WCAG 2.2 AA, 1280 px and 360 px touch) |
| 10 | CI scope, no unintended outbound calls, no secrets | pending Lab final pass at `0f32d4d` | 11 of 11 CI jobs green on `0f32d4d`; `test_outbound.py` in CI |
| 11 | Docs: setup, architecture, licenses, limits, rollback, screenshots, demo | pending Lab final pass at `0f32d4d` | G-2 (STATUS) and G-6 (architecture, rollback) closed by this PR; [DEMO_SCRIPT.md](../acceptance/DEMO_SCRIPT.md), [WALKTHROUGH.md](../acceptance/WALKTHROUGH.md) |
| 12 | Discrepancy table | pending Lab final pass at `0f32d4d` | [ACCEPTANCE.md section 2](../ACCEPTANCE.md) (Lab, being refreshed) |

## 5. Test totals on `0f32d4d` (CI)

From the job logs of push run [39930532720](https://github.com/ShaileshRawat1403/traces/actions/runs/39930532720). The pull_request run [39930539272](https://github.com/ShaileshRawat1403/traces/actions/runs/39930539272) also succeeded.

| Job | Result |
| --- | --- |
| lint (ruff), types (mypy, web tsc) | pass |
| unit (`tests/unit`) | 87 passed, 3 skipped (live GitHub) |
| explain (`tests/explain`, in the unit job) | 96 passed |
| api (`tests/api`) | 95 passed |
| web-build (vitest, `check:api`, vite build) | vitest 16 files, 125 tests passed; build pass |
| target (pinned fsft cache) | pass |
| contract (CT1-CT16) | 17 passed |
| regression (RT1-RT8, migration, report) | 16 passed |
| security (`tests/security`, `tests/e2e/*.py`) | 136 passed, 0 xfailed |
| history (full-history fsft, any skip fails) | 176 passed |
| e2e (fsft@b1125d8 seed) | Playwright 94 passed, 4 skipped by design; `real_snapshot.cjs` 21 of 21; `chat_g5.cjs` 13 of 13 |

`tests/e2e/demo_walk.cjs` runs against the box app only (not CI). `tests/perf/bench.py` is a local baseline ([PERF.md](../acceptance/PERF.md)).

## 6. Discrepancy table

Lab owns it: [ACCEPTANCE.md section 2](../ACCEPTANCE.md). It is being refreshed at `0f32d4d` and will be linked here, not copied.

## 7. Decision index

Full text in [DECISIONS.md](../DECISIONS.md) and, for D-H, [contracts/history.md](../contracts/history.md).

| Id | Decision |
| --- | --- |
| D-019 | Evidence-set diff keeps the `git_recount` check family in v1 |
| D-020 | `PrContextProvider` gains optional `artifact_bytes` |
| D-021 | Ingest: anonymous visibility check, pinned snapshot on registration, fetch caps |
| D-022 | Index worker, job runner, generic validation, RSS memory cap (closes D-006) |
| D-023 | Explain and chat bundle call the deterministic engine |
| D-024 | Views and history queries read the store; compare is an identity diff without H3 |
| D-025 | TypeScript resolution stops at the checkout |
| D-026 | Isolation fails closed; `TRACES_ISOLATION=off` is the only unisolated mode, recorded on the snapshot (F2) |
| D-027 | Repo-level AI consent endpoint |
| D-028 | Hardening from the security suite and the evidence review (F-1 to F-6, F1, F3, F4, F7, F8, ingest cleanup) |
| D-029 | Component layer reasons, `library` layer, route labels, per-step trace gaps |
| D-030 | Minimal JavaScript import check; JavaScript calls are v1.1 |
| D-031 | Trace completeness, Express mounts, git process groups, focused hidden counts (F5), `/meta` isolation, O-9 cleanup |
| D-032 | A3 naming is a qualified, documented claim (Task 002 ruling 4) — added by this PR (F6) |
| D-H1 | Co-change, churn and hotspot counts may reach `observed` after a recount; class stays `history_pattern`, never `verified` |
| D-H2 | Git plumbing checks count as independent for git-object facts; `quote_match` proves only that a quote exists |
| D-H3 | `citations` field; history records need `locations` or `citations` |
| D-H4 | `review_state` is separate from `status` and never promotes it |
| D-H5 | "All commits" means non-merge commits; file-set replay along first-parent |
| D-H6 | Git-object fact `claim_id`s anchor to their commit |
| D-H7 | Generated filter matches `dist/` and `build/` directory segments at any depth |
| D-H8 | The Evidence seat supplies `generated_paths` |
| D-H9 | Milestone cap 8 for the index worker, 20 on demand |
| D-H10 | Optional `artifact_bytes` in `PrContextProvider` |
| D-H11 | No new check method in v1; dedicated method deferred to schema 0.5 |
| D-H12 | `run()` signature, budgets, stage order and report layout frozen |
| D-H13 | Runner config and budget, RLIMITs on git children, finalize validation option C |
| D-H14 | Alias suggestions are opt-in (`HistoryConfig.aliases=False`) |
| D-H15 | Lineage restart caveat on delete and re-add; fsft default digest `402d3d34eff4` to `2fb288167ebf`, same claim_ids |

## 8. Security posture at `0f32d4d`

| Area | What the code does | Evidence |
| --- | --- | --- |
| No target code execution | The target is cloned and parsed. No install, hook, build or test of the target runs. Clone has hooks, LFS and submodules off | `tests/security/test_hostile_repo.py`; CT15 |
| Isolation | CodeGraph, adapter and validators run under `unshare -rn` in `workers/sandbox.sh`. If isolation cannot be shown the job fails closed (`E_ISOLATION`), nothing is fetched, no claims stored (D-026). `TRACES_ISOLATION=off` is recorded as `isolation=off`, `unisolated=true`, never acceptance evidence | `tests/unit/test_isolation.py`; addendum F2 PASS |
| History git | Runs in the job thread with transports refused (`protocol.allow=never`) and RLIMITs, on a local clone; not inside `unshare -rn` (see limits) | `history/gitcmd.py` |
| Ingest | Public github.com HTTPS only; 28 malformed URL classes refused before any network call; caps on size, time, files, tree; git in its own process group, cleanup on every failure | `test_repo_urls.py`, `test_fetch_limits.py` |
| BYOK | Key held in the browser only, sent only in the provider's `Authorization` header after consent. Manifest rows hash the exact line sent (O-11). Rejected claims stripped. The API forbids key fields, and 422 bodies no longer echo input (F-3) | `chat_g5.cjs` 13 of 13 (stub provider), `test_no_key_and_caps.py` |
| Outbound | Read, explain and chat-bundle endpoints make no off-loopback connection; the worker's only network-capable process is the clone | `test_outbound.py` |
| Secrets | Lab scanned `git log -p --all` for GitHub, OpenAI, AWS, Slack and private-key patterns: only a fake test token | ACCEPTANCE row 10 |

## 9. Findings: final status

### 9a. Independent evidence review (Traces seat)

Full reports: [REVIEW_V1_EVIDENCE.md](REVIEW_V1_EVIDENCE.md) (at `35499bc`) and [REVIEW_V1_ADDENDUM_b37eef2.md](REVIEW_V1_ADDENDUM_b37eef2.md) (recheck at `b37eef2`). Absolute box paths are replaced with placeholders.

At `35499bc`: the reproduction is exact (4,538 verified, 36 observed, 59 unvalidated, 9 rejected of 4,642 edges; validation hash `73db432b`; identical `claim_id` sets of 10,016). It found 0 `claim_id` collisions and 0 EOF violations, the 9 wrong imports stay rejected, and `missing_location` is never verified without recovered locations.

**Addendum at `b37eef2`:**

| Recheck | Verdict |
| --- | --- |
| F2 isolation | PASS: `auto`, `unshare` and `none` fail closed with `E_ISOLATION` and create no run; `off` gives an `unisolated` snapshot; `tests/unit/test_isolation.py` 12 passed |
| F1 CT4 clause | PASS: mutation proof, the new clause fails a broken run |
| F3 injected marker | PASS: the 3 injected carry `injected=true` and `injected_control` in claims and graph edges |
| F4 truncation | PARTIAL: rejected edges are counted in `truncated_counts`, not kept (accepted, D-028) |
| F5 focused counts | PARTIAL at `b37eef2` (counted either-end, shown both-ends); fixed in #33 (D-031) |
| F7 report | PASS: `chain.json` and `coverage.json` written; only `run_id` differs from Task 002 |
| F8 test | PASS: the test now asserts that missing_location is never verified |
| Re-run on fsft@b1125d8 | Validation hash `73db432be3ba...` equal to Task 002; 4,642 = 4,538/36/59/9; 10,016 distinct ids; 0 EOF violations |
| Full suite (namespace with loopback up) | 524 passed, 3 skipped, 0 real failures |
| New items A1-A6 | A1 (F5 scope) fixed in #33; A2 accepted (D-028); A3 `/meta` isolation fixed in #33; A4 config comment fixed; A5 `test_index_baseline` network rule fixed in #33; A6 research file outside the repo, no action |

| ID | Severity | Summary | Owner | Blocks v1 | Final status |
| --- | --- | --- | --- | --- | --- |
| F1 | medium | CT4 negative clause was commented out | Traces | no | **Fixed** in #27 (`b37eef2`), verified by addendum |
| F2 | medium | `auto` fell back to no isolation and stored a ready snapshot | Traces (API lane) | was **yes** | **Fixed** in #27 (D-026), verified by addendum |
| F3 | low | Injected controls not marked in lists and graph | Traces | no | **Fixed** in #27 (D-028), verified by addendum |
| F4 | low | Unfocused graph truncates rejected edges | Traces | no | **Accepted** under D-028: reported in `truncated_counts`, not kept |
| F5 | low | Focused `hidden_counts` was snapshot-wide, then either-end | Traces | no | **Fixed** in #33 (D-031): counted under the shown-edge rule |
| F6 | low | A3 ruling-4 wording missing from docs | Architect | no | **Fixed in this PR** (#21, D-032), not merged yet |
| F7 | low | `report.py` not ported | Traces | no | **Fixed** in #27, verified by addendum |
| F8 | low | Worker test asserted less than its comment | Traces | no | **Fixed** in #27, verified by addendum |
| F9 | info | R-contains recovered locations have `recovered_by` null | Traces | no | Noted, inherited from Task 002 |
| F10 | info | D-011 said "never verified" without the recovery caveat | Architect | no | **Fixed in this PR** (#21), not merged yet |
| F11 | info | fsft store holds fixture and injected records by design | none | no | Noted |
| F12 | info | `test_store_concurrency` fails in a namespace without loopback | Lab / Traces | no | Noted; passes with loopback up (addendum) |

### 9b. Lab findings (ACCEPTANCE.md section 3)

Severities are Lab's.

| ID | Severity | Summary | Owner | Blocks v1 | Final status |
| --- | --- | --- | --- | --- | --- |
| F-1 | High | Non-ASCII file name failed the whole index (`E_PATH`) | Traces (adapter) | no | **Fixed** in #27 (`git ls-tree -z`, D-028) |
| F-2 | Low | Source view refused names starting with `-` | Traces (views) | no | **Fixed** in #27 (D-028) |
| F-3 | Medium | 422 body echoed rejected input, including a key | Traces (API) | was **yes** | **Fixed** in #27 (D-028); CI `security` 0 xfailed |
| F-4 | High | Relative Python imports rejected | Traces (validators) | no | **Fixed** in #27 (D-028) |
| F-5 | Medium | `@overload` call resolved to the stub | Traces (validators) | no | **Fixed** in #27 (D-028) |
| F-6 | Low | Unknown SHA left a failed snapshot row and empty cache | Traces (ingest) | no | **Fixed** in #27 (422 `sha_not_found`); old rows cleaned by O-9 in #33 |
| F-7 | Medium | No-key explain matched keywords | Traces UI (explain) | no | **Fixed** in #26 (intent routing, `intents.py`) |
| F-8 | Medium | History questions ignored the named file | Traces UI (explain) | no | **Fixed** in #26; JavaScript paths in #36 |
| F-9 | Medium | Trace claimed "complete" despite unresolved calls | Traces (views), UI | no | **Fixed** in #33 (D-031) and #38 (UI) |
| F-10 | High (JS repos) | No JavaScript validator; `require` failed L3 | Traces (validators) | no | **Fixed** in #33 (D-030): 107 of 107 imports verified on node-express-boilerplate; calls deferred to v1.1 |
| F-11 | Low | Route question answered "no README or manifest" | Traces UI (explain) | no | **Fixed** in #36 |

All fixes are pending Lab's final pass at `0f32d4d`.

### 9c. Architect audit findings at `35499bc`

| Finding | Final status |
| --- | --- |
| Explain filed co-change as code structure without the caveat | Fixed in #24 |
| Partial clone left after a fetch timeout | Fixed in #27 (process group kill, cleanup in `finally`, D-028) |
| Unknown SHA accepted at registration | Fixed in #27 (F-6) |
| Rate limit and missing-key UI not live-tested | Covered by `tests/security` in CI |

## 10. Known limits and deferrals (v1)

| Limit | Detail |
| --- | --- |
| O-5 latency | Graph and trace p95 about 630 ms on fsft (graph 635.7 ms, trace 624.9 ms; local baseline, [PERF.md](../acceptance/PERF.md)). No performance target in the charter |
| JavaScript calls and references | Deferred to v1.1 (D-030). Only JS `imports` can be verified; calls, references, instantiations and named bindings stay unvalidated or observed |
| O-7 Express mounts | Routers mounted through a computed `forEach` are shown without the mount prefix. Literal mounts compose; middleware mounts show as `USE` with flag `mount` |
| O-8 persistence | Mongoose and other ODMs are not detected; trace and explain say no persistence path is recorded |
| Overview interpretations | README heading and frameworks are shown as uncited interpretations, not verified claims |
| Live-provider chat | Untested. Only a stub provider is tested (`chat_g5.cjs`); no paid key or local model was approved |
| Provider key storage | By design the key is in browser sessionStorage, or localStorage with "Remember on this device" and a warning (Lab L-1). It never reaches the Traces API, logs, store or sent record |
| H3 milestone re-indexing | Still absent at `0f32d4d`: the index job passes only the pinned SHA to history, so compare uses an identity diff of static claims (D-024) |
| History isolation | History git runs with transports refused and RLIMITs, not inside `unshare -rn`, while `docs/contracts/history.md` says it does. Doc or code to align (History, Traces) |
| Private repositories, server-side LLM | Out of scope for v1 |
| Static evidence only | A missed relationship is a gap, not proof of absence. Library-contract hops stay inferred. The Task 002 persistence path is static |
| Snapshots indexed before migration 0003 | `isolation` is null (unknown); re-index to record it. The box app's two snapshots are in this state |

## 11. Box app and demo

The box app serves `0f32d4d` from a clean clone: API `http://127.0.0.1:8731` (health `store_migration` 3, `/meta` isolation `unshare`, JavaScript validator listed), web `http://127.0.0.1:5731`. Ready snapshots: fastapi/full-stack-fastapi-template@b1125d8 and pallets/itsdangerous@672971d.

The guided demo is Lab's [DEMO_SCRIPT.md](../acceptance/DEMO_SCRIPT.md) (`tests/e2e/demo_walk.cjs`, 15 steps). Short version, 10 minutes:

| Time | Step |
| --- | --- |
| 0:00 | Home: both repos and their snapshots |
| 1:00 | fsft overview at `b1125d8`: components with layer reasons, README heading as interpretation |
| 2:30 | Graph: rejected and injected hidden, with counts; open an edge's evidence drawer |
| 4:00 | Trace Items page to `get_db`: verified hops, library steps inferred, static persistence path |
| 5:00 | Claims with rejected shown: 9 imports and 3 `injected_control` |
| 6:00 | History: timeline, co-change with the "not a dependency" caveat, milestones |
| 7:30 | Ask without a key: a cited answer, then a question it must answer `unknown` |
| 8:30 | itsdangerous: `library` layer with its reason, purpose unknown |
| 9:15 | Phone width (360 px) |
| 9:45 | Limits (section 10) |

## 12. Licenses

MIT ([LICENSE](../../LICENSE)). Third-party list: [THIRD_PARTY_LICENSES.md](../THIRD_PARTY_LICENSES.md), including shiki and `@shikijs/*`, `@tanstack/react-query`, `@radix-ui/*` and the bundled grammars and theme. No GPL or AGPL dependency, no GitNexus or Code Maat code. No dependency was added between `35499bc` and `0f32d4d`: `uv.lock`, `web/package.json`, `web/package-lock.json` and the toolchain locks are unchanged (only `pyproject.toml` lint and mypy settings changed). The JavaScript import check (D-030) reuses the pinned TypeScript 6.0.3 parser already in `toolchain/`.
