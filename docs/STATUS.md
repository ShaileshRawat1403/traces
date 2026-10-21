# Status (Traces v1)

Updated 2026-10-21 IST. Milestone: FOUNDATION.

## Seat assignments

Seats push their own `ws/<seat>-<topic>` branches and open PRs into `build/traces-v1`. A seat does not modify another seat's owned paths.

| Seat | Owns |
| --- | --- |
| Traces | evidence, ingest, index, views and API (`backend/traces/{evidence,adapter,validators,ingest,core,api}`, `workers/`, `toolchain/`) |
| Traces Lab | CI, e2e harness, security, second repo, acceptance (`ci/` and `.github/workflows/`, `tests/e2e`, security tests) |
| Traces History | `backend/traces/history` (and `docs/contracts/history.md`) |
| Traces UI | `web/` and explain (`backend/traces/explain`) |
| Architect | `docs/CONTRACTS.md`, `docs/DECISIONS.md`, `docs/STATUS.md`, integration merges |

## Progress

| Area | State | Owner | Notes |
| --- | --- | --- | --- |
| Integration branch, draft PR | done | Architect | `build/traces-v1`; draft PR "Traces v1 (integration, do not merge)" |
| Task 002 pipeline port | done | Traces | `backend/traces/{adapter,validators,evidence/pipeline.py,fixtures}`, `workers/`; reproduces the closeout hashes |
| CT1-CT16, RT1-RT8 | done | Traces | pytest; [TEST_MAPPING.md](TEST_MAPPING.md) |
| Schema 0.4 + migration from 0.3 | done | Traces | includes the approved History requests |
| SQLite store, migrations, export | done | Traces | migration 0001 |
| Job state machine, ETag polling | done | Traces | worker that drives it: INDEX |
| API: health, meta, repos, snapshots, claims, export, jobs | done | Traces | |
| API: head, index jobs | 501 | Traces | INGEST, INDEX |
| API: overview, components, routes, graph, source, trace | 501 | Traces | VIEWS |
| History contract | done | Traces History | [docs/contracts/history.md](contracts/history.md), merged from PR #3 |
| API: history endpoints, compare | 501 | Traces History | HISTORY |
| API: explain, chat bundle | 501 | Traces UI | EXPLAIN |
| Web scaffold | done | Traces UI | repos, snapshots, claims, reviewer view; other views show explicit not-implemented |
| OpenAPI copy + generated TS types | done | Traces / Traces UI | checked in tests and `npm run check:api` |
| CI workflow | staged, waiting on Shailesh | Traces Lab | at `ci/github-actions-ci.yml`; the push token lacks `workflow` scope (D-018). Waiting on Shailesh to grant the token `workflow` scope, then move it to `.github/workflows/ci.yml`. No CI run yet. |
| Playwright e2e, security tests, second-repo acceptance | not started | Traces Lab | |
| History module | not started | Traces History | `backend/traces/history/interface.py` holds the hook points |

## Open items

1. CI activation: waiting on Shailesh to add the `workflow` scope to the push token (D-018); until then CI has not run.
2. Memory cap for the indexer: `ulimit -v` breaks CodeGraph's WebAssembly; choose cgroup v2 or container limits (D-006).
3. Web bundle is one 600+ kB chunk (Cytoscape); code-split the graph view when it lands.
4. `starlette.testclient` warns that `httpx` is deprecated in favor of `httpx2`; switch when FastAPI's test client does.
5. Index worker, HEAD discovery and the GitHub client (with token, cache, rate limits) are not built (INGEST/INDEX).
