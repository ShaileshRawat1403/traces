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

## Re-run at `0f32d4d` (final acceptance pass)

- Run: 2026-10-23 15:03 IST (`when_utc` 2026-10-23T09:32:57Z), `git_head` 0f32d4d, same machine, command and method as above. One bench run; other seats' processes were running on the box.
- Raw output: `.traces-data/acceptance/final/perf/perf.json` and `.traces-data/acceptance/final/perf.txt` (gitignored scratch).

| Repository | Runs (s) | Median (s) | fetching | checking_out | indexing | adapting | validating | storing | history |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| fastapi/full-stack-fastapi-template@b1125d8 | 19.86, 19.11, 19.33 | 19.33 | 0.0 | 0.03 | 1.28 | 1.01 | 5.57 | 2.5 | 8.93 |
| pallets/itsdangerous@672971d | 4.73, 4.74, 5.28 | 4.74 | 0.0 | 0.01 | 1.04 | 0.51 | 0.76 | 0.3 | 2.65 |

Phase columns are from the last run.

API latency (ms), fastapi/full-stack-fastapi-template@b1125d8:

| Endpoint | p50 | p95 | max |
| --- | --- | --- | --- |
| repos | 0.7 | 1.2 | 1.6 |
| overview | 68.1 | 75.4 | 87.9 |
| components | 36.2 | 40.9 | 45.3 |
| graph | 581.2 | 673.6 | 2004.2 |
| claims page 1 | 5.1 | 5.8 | 7.1 |
| history timeline | 53.8 | 77.8 | 170.3 |
| history milestones | 15.6 | 17.1 | 29.8 |
| explain (no key) | 15.1 | 16.8 | 39.8 |
| trace create_item | 796.9 | 937.6 | 1071.1 |
| source items.py | 3.9 | 4.5 | 4.9 |
| history cochange crud.py | 23.1 | 26.2 | 68.0 |

API latency (ms), pallets/itsdangerous@672971d:

| Endpoint | p50 | p95 | max |
| --- | --- | --- | --- |
| repos | 0.7 | 1.1 | 1.4 |
| overview | 14.6 | 16.3 | 20.8 |
| components | 7.5 | 8.5 | 8.8 |
| graph | 59.2 | 84.8 | 133.0 |
| claims page 1 | 3.2 | 3.9 | 4.2 |
| history timeline | 15.6 | 31.4 | 38.4 |
| history milestones | 4.5 | 5.6 | 6.1 |
| explain (no key) | 4.9 | 5.5 | 6.0 |

Changes against the `17c4335` baseline:
- `trace create_item` p50 went from 540.8 ms to 796.9 ms (+47 %), and p95 from 624.9 ms to 937.6 ms. The likely cause is the F-9 unresolved-call gaps, which add work per traced step. It is still under 1 s at p95.
- `graph` p50 went from 543.2 ms to 581.2 ms, and p95 from 635.7 ms to 673.6 ms. Its max was 2,004 ms (one outlier).
- fsft explain (no key) p50 went from 8.5 ms to 15.1 ms. Index medians are unchanged within noise: fsft 19.33 s against 19.28 s, itsdangerous 4.74 s against 4.93 s.
- O-5 is now v1 limit L-1 in ACCEPTANCE.md.
