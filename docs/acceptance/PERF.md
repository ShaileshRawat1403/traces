# Performance baseline (local)

Local numbers from the Traces Lab box, not CI. The charter sets no performance targets; this is a baseline to compare later builds against.

- Run: 2026-10-23 12:50 IST, commit `17c4335` (the measured code equals `build/traces-v1` @ `e532644` except for PR #24, which only changes explain), 8 CPUs, Linux-6.12.94+-x86_64-with-glibc2.41, CPython 3.14.8, CodeGraph 1.6.2, `TRACES_ISOLATION=unshare`.
- Command: `uv run --frozen python tests/perf/bench.py OUT --repo pallets/itsdangerous=<local clone>@672971d...` (fsft is always included).
- Index: `IndexRun` on a fresh data dir, from a local full-history clone, so `fetching` is a local clone, not a GitHub download. 3 runs each, median reported.
- API: scratch `traces serve` on loopback with the last index run's store, 3 warm-up requests, then 100 sequential requests per endpoint.

## Index wall time

| Repository | Runs (s) | Median (s) | fetching | checking_out | indexing | adapting | validating | storing | history |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fastapi/full-stack-fastapi-template@b1125d8 | 19.38, 19.0, 19.28 | 19.28 | 0.0 | 0.03 | 1.27 | 1.01 | 5.07 | 2.34 | 9.55 |
| pallets/itsdangerous@672971d | 5.59, 4.59, 4.93 | 4.93 | 0.0 | 0.01 | 0.76 | 0.51 | 0.76 | 0.28 | 2.6 |

Phase columns are from the last run. History (native Git over all commits) is about half the time on both repositories.
For reference, the box app's own jobs, which include the GitHub fetch: fsft about 23 s, itsdangerous 31 s including queue wait.

## API latency (ms)

### fastapi/full-stack-fastapi-template@b1125d8

| Endpoint | p50 | p95 | max |
| --- | --- | --- | --- |
| repos | 0.8 | 1.3 | 1.9 |
| overview | 66.0 | 106.0 | 152.7 |
| components | 34.9 | 46.1 | 63.0 |
| graph | 543.2 | 635.7 | 679.9 |
| claims page 1 | 4.8 | 11.8 | 16.4 |
| history timeline | 51.7 | 75.3 | 106.7 |
| history milestones | 15.2 | 16.7 | 17.0 |
| explain (no key) | 8.5 | 10.5 | 19.9 |
| trace create_item | 540.8 | 624.9 | 706.9 |
| source items.py | 4.3 | 6.1 | 7.3 |
| history cochange crud.py | 22.8 | 31.5 | 73.2 |

### pallets/itsdangerous@672971d

| Endpoint | p50 | p95 | max |
| --- | --- | --- | --- |
| repos | 0.7 | 1.1 | 1.5 |
| overview | 14.7 | 16.4 | 17.5 |
| components | 7.4 | 8.2 | 9.1 |
| graph | 55.3 | 74.8 | 83.3 |
| claims page 1 | 3.1 | 3.6 | 4.1 |
| history timeline | 15.0 | 30.1 | 34.3 |
| history milestones | 4.5 | 5.3 | 5.5 |
| explain (no key) | 2.1 | 2.7 | 3.6 |

Endpoints: `repos` = `GET /api/v1/repos`; the rest are under `/api/v1/repos/{id}/snapshots/{sha}`: `overview`, `components`, `graph` (default view), `claims?limit=50`, `history/timeline?limit=50`, `history/milestones`, `POST explain` (no key, "Where is the persistence path?"), `trace?from=backend/app/api/routes/items.py::create_item`, `source?path=backend/app/api/routes/items.py&start=60&end=66`, `history/cochange?target=backend/app/crud.py`.

## Reading

- Every read endpoint except `graph` and `trace` answers under 110 ms at p95 on fsft (18,468 records with history).
- `graph` and `trace` sit near 0.55 s p50 and 0.63 s p95 on fsft (O-5 in ACCEPTANCE.md). They stay well under a second, and on itsdangerous `graph` is 55 ms p50.
- Raw output: `.traces-data/acceptance/perf/perf.json` and `bench.out` (gitignored scratch).
