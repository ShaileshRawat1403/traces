# Status (Traces v1)

Updated 2026-10-21 IST. Milestone: FOUNDATION.

## Seat assignments

Seats push their own `ws/<seat>-<topic>` branches and open PRs into `build/traces-v1`. A seat does not modify another seat's owned paths.

| Seat | Owns |
| --- | --- |
| Traces | evidence, ingest, index, views and API (`backend/traces/{evidence,adapter,validators,ingest,core,api}`, `workers/`, `toolchain/`) |
| Traces Lab | CI, e2e harness, security, second repo, acceptance (`ci/` and `.github/workflows/`, `tests/e2e`, security tests) |
| Traces History | `backend/traces/history`, `tests/history/` (and `docs/contracts/history.md`) |
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
| History module | core merged (#5); steps 7-11 in progress | Traces History | steps 1-6 (gitcmd, ingest/cache, filters, records/verify, facts, lifecycle, churn, hotspots, co-change); 7-11 (milestones, snapshot diffs, reverts, manifests, aliases, impact, PR context, HistoryRunner) pending. Deviations: see note below |

## History core deviations (PR #5)

Listed by Traces History in [PR #5](https://github.com/ShaileshRawat1403/traces/pull/5) ("Deviations from the contract"); the PR body is authoritative. In short:
1. Ingest uses `diff-tree --stdin` (raw and numstat) over a rev-list instead of one log stream; independent checks use separate plumbing.
2. Cache: corrupt or mismatched entries are discarded and recomputed; the E_CACHE recompute-and-compare path is not implemented.
3. Hotspots skip blobs over `max_blob_bytes` with a warning instead of raising E_LIMIT.
4. Component maps only at the pinned SHA; `component_removed` and `continues_as` deferred; component-level churn and co-change stay unvalidated in v1.
5. Recount mismatches give an inconclusive check; the record stays unvalidated with the reason; nothing is marked rejected.
6. Added `HistoryConfig.verify` (default True); with it off nothing reaches observed.
7. Hotspot records use node_kind `file_history_metrics` and differ from churn records by parameters, so their claim_ids differ.
8. Test gaps against section 18: HT4 separate id-recompute test, HT21 rename_limit synthetic test, HT12 combined synthetic repo.

## Open items

1. CI activation: waiting on Shailesh to add the `workflow` scope to the push token (D-018); until then CI has not run.
2. Memory cap for the indexer: `ulimit -v` breaks CodeGraph's WebAssembly; choose cgroup v2 or container limits (D-006).
3. Web bundle is one 600+ kB chunk (Cytoscape); code-split the graph view when it lands.
4. `starlette.testclient` warns that `httpx` is deprecated in favor of `httpx2`; switch when FastAPI's test client does.
5. Index worker, HEAD discovery and the GitHub client (with token, cache, rate limits) are not built (INGEST/INDEX).
