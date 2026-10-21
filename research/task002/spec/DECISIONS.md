# Decisions applied to the Task 002 specs

Recorded by Traces (lead investigator). Sources are relayed decisions; quoted wording is kept as given. Where two decisions overlap, the later one governs and the row says so.

## D-Q: answers to the six spec questions (ChatGPT, relayed by Shailesh via Architect1, received 2026-10-21 10:02 IST)

| Id | Decision | Spec effect |
|---|---|---|
| D-Q1 | Independent validator families are Python stdlib `ast` and the official TypeScript Compiler API, pinned to 6.0.x. CodeGraph uses tree-sitter, so a second tree-sitter is not an independent family. Validators must independently confirm locations, symbols, imports and the relevant structural relationships. Two parsers agreeing that a symbol exists does not verify a dependency or call. If independent structural verification is not available, the claim stays unverified. Never promote a guess because the referenced symbol exists. | Second-parser option removed. EVIDENCE_SCHEMA sections 5 and 6. |
| D-Q2 | TypeScript 6.0.x replaces 5.x everywhere. | Pinned 6.0.3 with Lab's evidence (section "Environment facts" below). |
| D-Q3 | CodeGraph's 616 name-only matches are unverified guesses unless independently validated. Keep them with provenance; never show them as confirmed. | EVIDENCE_SCHEMA section 8. |
| D-Q4 | L8 gets a separately documented write-operation rule set that verifies the static call path from handler to write call, records locations, and labels the result as a statically established write path, never runtime persistence. The parser alone only confirms the call is present. | FASTAPI_RULES R4. Label wording updated by D-002A.5. |
| D-Q5 | Network isolation: OS or container level only (`unshare -rn` accepted; env vars and app config do not count), proven by a logged, deliberately denied probe. If isolation cannot be shown, offline validation stops and is reported. | ADAPTER_CONTRACT section 9, CT15. Extended by D-002A.6. |
| D-Q6 | `openapi.json` and running the target app are out of scope for Task 002 and need separate authorization. | FASTAPI_RULES section 0, A-table. Confirmed by D-002A.7. |
| D-Q7 | Three labels across all specs: observed (what source contains), verified (independent evidence for a relationship), inferred (analyzer or AI belief). | EVIDENCE_SCHEMA section 3, JSON Schema `label`. |
| D-Q8 | N2 becomes a planted false handler-level dependency, injected as an inferred claim, ending rejected and visible. CodeGraph's true file-level import edges stay as separate, non-rejected records. | EXPECTED_CHAIN N2. Placement fixed by D-002A.8. |
| D-Q9 | Containment recovery result (1,891 of 1,893) is the expected outcome for that path. | EVIDENCE_SCHEMA section 7. |
| D-Q10 | Gates unchanged: `b1125d8`, CodeGraph 1.6.2, read-only checkout, L1 to L9 independently validated, N1 and N2 rejected and visible, 100% provenance classified. A failed criterion is reported, never relaxed. | All specs. |

## D-002A: Architecture Review Decision 002-A (ChatGPT, via Shailesh, received 2026-10-21 10:06 IST). Supersedes overlapping points above.

| Id | Decision | Spec effect |
|---|---|---|
| D-002A.1 | Step 1 accepted. **S1 PASS**: no wrong relationship in Q3 or Q4; this does not guarantee every edge. **S2 PASS with a documented checker correction**: the parser measure, 378 of 379 (99.7%), is authoritative; 320 of 379 (84.4%) is kept for audit. The corrected checker (Python and TS declaration recognition plus route definitions) is frozen and documented; accuracy is never silently redefined. The `sidebar.tsx` `setOpen` mismatch stays on record. The spec must distinguish declaration location from body location. | EVIDENCE_SCHEMA section 4 (`declaration` vs `body` range); ADAPTER_CONTRACT CT7 uses the frozen checker; section "Frozen line checker" below. |
| D-002A.2 | CodeGraph 1.6.2 is accepted as the pinned **structural extractor only**. It is not a validator, reasoning engine or source of truth. Its output never goes straight to verified. | CodeGraph has no validator role anywhere; all its claims start `inferred`. |
| D-002A.3 | Verified requires the relationship to be established through syntax, binding resolution, or a documented deterministic rule. Otherwise it stays unverified. | EVIDENCE_SCHEMA rule V3 (`establishes` field on checks). |
| D-002A.4 | JSX render relationships are a distinct relationship type from function calls, with locations checked before they can become verified. | `renders` kind; CodeGraph `jsx-render` `calls` edges map to `renders`. |
| D-002A.5 | The L8 rule set distinguishes `Item.model_validate` (validation), `session.add` (staging), `session.commit` (commit attempt), `session.refresh` (reload). It validates the receiver (that `session` is the `SessionDep`-bound `Session`) and the static call path, not method names. Output label: **statically established persistence path**, never runtime persistence. | FASTAPI_RULES R4. |
| D-002A.6 | `unshare -rn` approved. Denial proof must cover the indexer and all child processes. Probe and output logs are kept; telemetry stays off. If isolation fails, stop that run. The npm cache at `lab/tools/gitnexus/home/.npm` is recorded as an environment-hygiene issue; nothing shared or unrelated is deleted without authorization. | ADAPTER_CONTRACT section 9, CT15; "Environment hygiene" below. |
| D-002A.7 | `openapi.json` stays deferred. Static analysis only; the target app is never started. | FASTAPI_RULES section 0. |
| D-002A.8 | N1 and N2 are both injected false claims, placed into validator test inputs only, never into the target repo or CodeGraph output. N1: GitDiagram's items-use-crud claim, injected as inferred. N2: "`private.py:create_user` depends on `CurrentUser`/`get_current_user`". Each ends rejected with an explanation and stays visible. | EXPECTED_CHAIN N1, N2; ADAPTER_CONTRACT CT16 guard. |
| D-002A.9 | Acceptance principles: every surfaced claim has classified provenance; observed, verified and inferred stay distinct and inferences stay visibly unverified; no invented links; no static evidence presented as runtime; no motives inferred from git history as fact; the checkout stays read-only and pinned; the app is never executed; nothing unreviewed goes to main. | EVIDENCE_SCHEMA section 1; all specs. |
| D-002A.10 | Next review package is the step 11 report: updated verification results, L1 to L9 evidence classifications, N1/N2 rejection evidence, remaining limitations. Then stop for architectural approval. | EXPECTED_CHAIN "Step 11 package". |

## Environment facts supplied by Lab (cited, not re-run by Traces)

| Item | Value | Evidence |
|---|---|---|
| CodeGraph | `@colbymchenry/codegraph@1.6.2`, integrity `sha512-hODH/mGnCf3IUMs6rzktv/zbecJIKJfdZAYHZ9mqecb0G7ZkHaA8CZafDVnswANFEL1YFcG+lfAwc5SIXzUH6Q==`, shasum `372b7b4f0190197b07d444116d6692240883a2d5`, schema 11, extraction version 27 | `task002/ENV.md` |
| TypeScript | `typescript@6.0.3` (Apache-2.0), integrity `sha512-y2TvuxSZPDyQakkFRPZHKFm+KKVqIisdg9/CZwm9ftvKXLP8NRWj38/ODjNbr43SsoXqNuAisEf1GdCxqWcdBw==`, shasum `90251dc007916e972786cb94d74d15b185577d21` | lockfile `task002/tools/ts6/package-lock.json`, log `task002/logs/setup_ts6.log` |
| Python | CPython 3.14.8 `ast` | `task002/step1/RECHECK_TS6.md` |
| Node for the TS compiler API | v20.19.2 | `task002/step1/RECHECK_TS6.md` |
| Target checkout | `task002/src/fsft`, clean at `b1125d8839482cb7bbae603ddc6d0081bf87532e`; only `.codegraph/` untracked | Lab report, 2026-10-21 |
| HOME | pinned to `task002/tools/home` (the wrapper text in `logs/netprobe.log` shows `task002/tools/cghome`; see open item O1) | Lab report; `logs/netprobe.log` header |
| Isolation | `task002/tools/offline.sh`: sandboxed HOME, `CODEGRAPH_TELEMETRY=0 DO_NOT_TRACK=1 NO_UPDATE_NOTIFIER=1 CODEGRAPH_NO_DOWNLOAD=1`, `exec unshare -rn -- "$@"` | `task002/logs/netprobe.log` |
| TS 6.0.3 recheck, network off | 0 of 109 TS parse errors; 43 of 43 Python files; 378 of 379 start lines; 341 of 348 end lines; 1,891 of 1,893 containment. Every number equal to the 5.9.3 run. | `task002/step1/RECHECK_TS6.md`, `step1/logs/15` to `20` |

**Limit (recorded):** the 6.0.3 recheck was parse-only (`createSourceFile`, syntax kinds, positions). Type checking and binding resolution under 6.0.3 were not tested. Binding resolution is now required for verification (D-002A.3), so it is an untested capability until step 7 shows it works on this repo.

## Frozen line checker (D-002A.1)

Lab's frozen checker, cited as written by Lab (Traces confirmed the two sha256 values by reading the files; nothing re-run):

| Item | Value |
|---|---|
| Location | `task002/checker/` (`README.md`, `SHA256SUMS`) |
| Version | `line_checker_v1.0.0` |
| `line_checker_v1.py` | sha256 `1bf633c025797af2f0566d60c4653d62d71f818e07f8cde63df9d9e8d4aed58d` |
| `ts_decls_v1.js` | sha256 `1a6a9711b483d464315adb1d209b5399a47d2262fdc8d3f13c0c30cbe44b2445` |
| `--mode parser` | **authoritative**: 378 of 379 (99.7%). Python 3.14.8 `ast` and TypeScript 6.0.3 declaration recognition, plus route definitions (FastAPI decorator line holding method and path literal; TanStack `createFileRoute` line). |
| `--mode lab_route` | audit: 351 of 379 (92.6%) |
| Original `lab/B/scripts/check_lines.py` | unchanged (sha256 `0421b5b8...6856`), audit: 320 of 379 (84.4%) |
| Run log | `task002/logs/checker/run_v1_20261021T100725.log`; results `task002/logs/checker/result_parser.json`, `result_lab_route.json` |

The one recorded mismatch: `frontend/src/components/ui/sidebar.tsx` `setOpen`. Declaration at line 86 (`const setOpen`), body at 87 to 97 (the arrow function inside `React.useCallback(`). CodeGraph reports 87 to 97, so CodeGraph points at the body, not the declaration. It stays on record. EVIDENCE_SCHEMA section 4.1 says which range kind each claim and relationship type uses.

The checker is frozen for Task 002. A change gets a new version id and is reported with old and new numbers side by side. Accuracy is never silently redefined.

## Environment hygiene

- **H-001** (`task002/ENV.md`): npm cache and debug logs written to the Task 001 GitNexus sandbox HOME, `lab/tools/gitnexus/home/.npm` (about 82 MB). Recorded as an environment-hygiene issue, retained, not deleted. Deletion of anything shared or unrelated needs Shailesh's authorization (D-002A.6).

## Isolation evidence (D-Q5, D-002A.6)

- Mechanism: `task002/tools/offline.sh`, `exec unshare -rn -- "$@"` with sandboxed HOME and `CODEGRAPH_TELEMETRY=0 DO_NOT_TRACK=1 NO_UPDATE_NOTIFIER=1 CODEGRAPH_NO_DOWNLOAD=1`. Wrapper sha256 `81042fecf68704913ba73359291e9b658f481e1d1853065fd7b845b0cb9d6466` as logged.
- Basic probe (`task002/logs/netprobe.log`, 10:04 IST): inside, only `lo` and it is DOWN; `curl https://registry.npmjs.org/` exits 6 (no DNS); `curl https://1.1.1.1/` exits 7 (no connect); the control outside the wrapper reaches the network.
- Child-process probe (same log, section `CHILD-PROCESS ISOLATION PROBES`, 10:08 IST): each wrapper run gets a fresh net namespace that its children share (for example parent and `sh` child both `net:[4026532230]`; outer shell `net:[4026531840]`). Probes from `sh -c curl` and from the bundled Node 24.16.0 (`child_process`, direct `https` and `net` calls) were all denied inside; the control outside connects. This covers the indexer and its child processes (D-002A.6).
- Logs 00 and 01 in `task002/step1/logs/` predate `CODEGRAPH_NO_DOWNLOAD=1`; they used the same `unshare` line.

## Open items created by these decisions

- **O1.** HOME path: Lab reports HOME pinned to `task002/tools/home`; the wrapper text captured in `logs/netprobe.log` (sha256 `81042fec...`) exports `task002/tools/cghome`. Lab confirms which is current and re-runs both probes if the wrapper changed after 10:08 IST.
- **O2.** The two library hops in the frontend chain (react-hook-form `handleSubmit` calling `onSubmit`; TanStack Query `mutate` calling `mutationFn`) cannot be established by syntax, binding resolution or a documented rule without reading library source, which is not installed and not in scope. See EXPECTED_CHAIN "Library hops".

## D-002B: Decision 002-B, review of REVIEW_PACKAGE_002.md (ChatGPT, via Shailesh and Architect1, received 2026-10-21 13:34 IST, dated 2026-10-21). Outcome: ACCEPTED WITH CORRECTIONS. Supersedes overlapping points above.

Scope of the review: REVIEW_PACKAGE_002.md only. RULINGS.md and review/audit/ were not reviewed, so these are rulings on the five summarized questions, not approval of every implementation detail. CodeGraph 1.6.2 stays the pinned extractor; no redesign; Task 003 is not opened.

| Id | Decision | Spec effect |
|---|---|---|
| D-002B.1 | EOF: conditionally approved. The line after the final newline is allowed only as an exclusive end boundary for whole-file ranges, never as an addressable source line or evidence location. Keep the original coordinates (store original plus normalized). Add tests for files with and without terminal newlines. | EVIDENCE_SCHEMA 4 and 11.1; JSON Schema location `original`, `end_exclusive_line`, `terminal_newline`; strict L2; regression RT4 to RT6. |
| D-002B.2 | claim_id: approved. Include the normalized source location, relationship identity, unresolved target name and extractor identity, and regenerate deterministically. Consolidate exact duplicates without losing evidence history (keep all contributing raw records and provenance attached). Collisions between distinct claims must be zero. | EVIDENCE_SCHEMA 11.2; `consolidation` field; adapter `E_COLLISION`; CT10 amended; regression RT1 to RT3. |
| D-002B.3 | H1 and H2 stay inferred, unvalidated library-contract assumptions. Do not download library source. | EXPECTED_CHAIN library hops; no change to records. |
| D-002B.4 | A1 to A3 approved with qualification. A1 and A2 are source-backed framework rules. A3 is pinned to hey-api 0.97.3 and its config, with generated output corroborating; the version pin alone is not independent proof of naming behavior. | FASTAPI_RULES assumption table; EXPECTED_CHAIN L4. |
| D-002B.5 | Rename `unverified_inference` to `analyzer_inference`. Keep origin/classification separate from verification status in the schema. | EVIDENCE_SCHEMA 3 and 11.3; JSON Schema `class` enum and status rules; CT4 amended. |
| D-002B.A | Correction A: reclassify the 36 library/CSS import edges from verified to observed. Target: verified 4,538; observed import statements 36; unvalidated 59; rejected 9; total 4,642. If the recount differs, report the real numbers and why; do not force them. | Validators: target that is the file's own import node is `parser_presence`; status `observed`, qualifier `observed import statement` (EVIDENCE_SCHEMA V3i). Recount met the target exactly. |
| D-002B.B | Correction B: use this exact conclusion: "Traces has verified the nine defined source-level architecture links and statically established the persistence path. Two third-party library behavior transitions remain inferred, and no runtime database write has been observed." | review/CLOSEOUT_002.md. |

Execution instructions recorded with the decision: apply the corrections in `task002/` without Lab; do not rerun CodeGraph extraction unless strictly needed; reuse the raw output of run `t002-20261021T1049-3` under a new run id; one corrected canonical export in `task002/out/`, with the previous `out/` archived to `out/_superseded_v1/`; rerun the 16 contract tests plus regression tests; keep all 12 rejected records; write `review/CLOSEOUT_002.md`. Constraints unchanged: offline via `tools/offline.sh` (`unshare -rn`), read-only pinned checkout, no target app execution, no `openapi.json` generation, no AI, GitNexus or GitHub API calls, no pushes, nothing deleted.

Applied in run `t002-20261021T1356-002b-2` (no extraction). Results: `review/CLOSEOUT_002.md`.
