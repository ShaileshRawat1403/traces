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
| Web UI shell | merged (#6) | Traces UI | working screens: repos list and register, repo page, claims, reviewer view, evidence page, job polling (ETag). Overview, components, routes, graph, trace, source, history and ask call their real endpoints and show the 501 state. Bundle: main 120 kB gzip, graph chunk 140 kB gzip (lazy-loaded). Playwright e2e in `web/e2e` (not yet in CI; Traces Lab owns the harness) |
| OpenAPI copy + generated TS types | done | Traces / Traces UI | checked in tests and `npm run check:api` |
| CI workflow | staged, waiting on Shailesh | Traces Lab | at `ci/github-actions-ci.yml`; the push token lacks `workflow` scope (D-018). Waiting on Shailesh to grant the token `workflow` scope, then move it to `.github/workflows/ci.yml`. No CI run yet. |
| Playwright e2e, security tests, second-repo acceptance | not started | Traces Lab | |
| History module | core merged (#5); analysis merged (#11) | Traces History | steps 1-11 done: gitcmd, ingest/cache, filters, records/verify, facts, lifecycle, churn, hotspots, co-change (#5); manifests, reverts and quick deletes, milestones, snapshot compare, evidence-set diff, history impact, PR context (#11). Test gaps HT4, HT12, HT21 closed (#11). Next: HistoryRunner (`run()`), so the INDEX history step can call it. Deferred: `alias_suggestions`, component-level snapshot compare, `component_removed` / `continues_as`. Deviations: see note below and the PR #11 body |

## History deviations (PR #5, PR #11)

PR #11 lists its own deviations under "Deviations for review" in [PR #11](https://github.com/ShaileshRawat1403/traces/pull/11); see also D-019 and D-020. PR #5's list:

Listed by Traces History in [PR #5](https://github.com/ShaileshRawat1403/traces/pull/5) ("Deviations from the contract"); the PR body is authoritative. In short:
1. Ingest uses `diff-tree --stdin` (raw and numstat) over a rev-list instead of one log stream; independent checks use separate plumbing.
2. Cache: corrupt or mismatched entries are discarded and recomputed; the E_CACHE recompute-and-compare path is not implemented.
3. Hotspots skip blobs over `max_blob_bytes` with a warning instead of raising E_LIMIT.
4. Component maps only at the pinned SHA; `component_removed` and `continues_as` deferred; component-level churn and co-change stay unvalidated in v1.
5. Recount mismatches give an inconclusive check; the record stays unvalidated with the reason; nothing is marked rejected.
6. Added `HistoryConfig.verify` (default True); with it off nothing reaches observed.
7. Hotspot records use node_kind `file_history_metrics` and differ from churn records by parameters, so their claim_ids differ.
8. Test gaps against section 18: HT4 separate id-recompute test, HT21 rename_limit synthetic test, HT12 combined synthetic repo. Closed in #11.

## Open items

1. CI activation: waiting on Shailesh to add the `workflow` scope to the push token (D-018); until then CI has not run.
2. Memory cap for the indexer: `ulimit -v` breaks CodeGraph's WebAssembly; choose cgroup v2 or container limits (D-006).
3. Bug (owner: Traces): concurrent API requests cause intermittent 500s, `sqlite3.InterfaceError: bad parameter or other API misuse` in `Store.get_repo` (`backend/traces/evidence/store.py`): one `sqlite3` connection opened with `check_same_thread=False` is shared across request threads without a lock. Reported by Traces UI in PR #6 (7 times in about 300 e2e page loads).
4. `starlette.testclient` warns that `httpx` is deprecated in favor of `httpx2`; switch when FastAPI's test client does.
5. Index worker, HEAD discovery and the GitHub client (with token, cache, rate limits) are not built (INGEST/INDEX).
