# Status (Traces v1)

Updated 2026-10-21 IST, after integrating PRs #9, #15, #16, #17, #19 and #14 into `build/traces-v1`. Authority is the code and the tests, not earlier seat notes.

## Integrated

| PR | Branch | What landed |
| --- | --- | --- |
| #9 | `ws/arch-ingest` | Anonymous public check, pinned snapshot, HEAD discovery, capped clone (D-021) |
| #15 | `ws/arch-index` | Index jobs, sandboxed worker, generic validation, RSS cap, history hook H1 (D-022) |
| #16 | `ws/history-runner` | `run()` / `GitHistoryRunner` with budgets |
| #17 | `ws/ui-history` | History screens (timeline, hotspots, co-change, milestones, compare) |
| #14 | `ws/ui-explain-tests` | Explain tests moved to `tests/explain` so pytest collects them |
| #19 | `ws/arch-explain` | Explain and chat bundle wired to the deterministic engine (D-023) |
| #18 | `ws/lab-ci` | CI workflow active at `.github/workflows/ci.yml` (already merged before this pass) |

Earlier merges on the branch: history contract and core, history analysis, UI shell, overview, graph, trace, explain screen, store concurrency.

## What the API does now

| Area | State |
| --- | --- |
| Register a public GitHub URL, confirm it anonymously, pin a snapshot | done |
| Discover HEAD, show `behind` against the newest ready snapshot | done |
| Index job: capped clone, CodeGraph in the sandbox, adapter, validators, store, history hook | done |
| Overview, components, routes, graph, source, trace | done (D-024). Graph and trace are static evidence only |
| History timeline, lifecycle, hotspots, co-change, milestones, rationale | done, from stored history records |
| Compare | done, with a limit: rename-aware `snapshot_added` / `snapshot_removed` records are returned when history stored them. Otherwise the endpoint returns an identity diff of static claims that already exist. It does not invent records and it does not map renames |
| Explain (no LLM) and chat bundle | done. Provider keys never reach the backend |
| Task 002 CT1-CT16 and RT1-RT8 | still the baseline suite. The product index path is `tests/api/test_index_baseline.py` |

`/meta` capability flags for the rows above are true.

## Not done

- Hook H3: the index job does not re-index milestone SHAs, so history's evidence-set diff usually has only the pinned SHA. Compare then falls back to an identity diff of static claims (D-024).
- Private repositories. v1 never asks for credentials.
- No LLM is called by the server. Optional chat is a browser-side bundle after consent. There is no provider adapter in the backend.
- Playwright specs live in `web/e2e`. The CI `e2e` job stays opt-in (`workflow_dispatch`) and is still a placeholder. A browser pass was not part of the automated suite recorded below.
- Compare is not a full rename-aware architecture diff unless those records were stored by a history run that received two evidence sets.

## CI

GitHub Actions is active. Do not treat a mergeable PR as a tested integration. A green Actions run on `build/traces-v1` after this push is the CI result. The earlier green run `39593694100` predates the six integrated PRs and this checkpoint.

## Verified locally (2026-10-21, this checkpoint)

Not a CI result. Commands used git 2.47.3, CPython 3.14.8, Node 22.23.3, and the pinned CodeGraph 1.6.2.

| Check | Result |
| --- | --- |
| `pytest tests/unit tests/api tests/explain tests/history` except `test_index_baseline` | 254 passed, 17 skipped (2 live-network tests were not in this command; the fsft history regression skips without `TRACES_HISTORY_FSFT_REPO`) |
| `TRACES_NETWORK_TESTS=1 pytest tests/unit/test_ingest.py -k live` | 2 passed (public HEAD, missing/private refused) |
| `pytest tests/contract tests/regression tests/api/test_index_baseline.py` | 33 passed. Product index of `fastapi/full-stack-fastapi-template@b1125d8`: 4,642 edges = 4,538 verified + 36 observed + 59 unvalidated + 9 rejected; 12 rejected overall, 3 injected; adapter `45600280...`; validation `73db432b...`. History on that index: `done`, `complete=true`, 8,464 records |
| `mypy`, `ruff` on the Python diff, `npm run check:api`, web `tsc` | clean |
| Second public repo `pallets/itsdangerous@672971d66a2e` | index succeeded in one run. 674 CodeGraph edges (310 verified, 3 observed, 268 unvalidated, 46 missing_location, 47 rejected). History `done`, 1,988 records. Overview quotes the README heading "ItsDangerous" as interpretation, not as a verified purpose. Graph and explain both answered |

## Open product limits (honest)

- A relationship the extractor missed is a gap or an absence, not a claim that the link does not exist.
- Co-change and hotspots are history patterns. They are not code dependencies and not causes.
- Library-contract hops (react-hook-form, TanStack Query on the Task 002 chain) stay inferred unless an independent check says otherwise.
- The persistence path on the Task 002 chain is a static path, not a runtime-observed database write.
- Rejected CodeGraph imports and the three injected negatives stay rejected and are hidden from the default graph.
