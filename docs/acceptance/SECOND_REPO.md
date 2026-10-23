# Second repository acceptance (charter section 7, "different public repository")

Owner: Traces Lab. Checked 2026-10-23 IST on the Traces Lab box. All results here are local, not CI.
Raw outputs: `.traces-data/acceptance/second-repo/` (gitignored scratch).

## Repositories

| Repo | Pinned SHA | License (file at SHA) | Why |
| --- | --- | --- | --- |
| `pallets/itsdangerous` | `672971d66a2ef9f85151e53283113f33d642dabd` (2025-06-14) | BSD-3-Clause (`LICENSE.txt`, "Copyright 2011 Pallets") | Accepted by Architect1 as the "different" case: a `src/`-layout Python library with no web framework, no frontend, no routes and no database, 50 files, 677 commits |
| `pallets/markupsafe` | `4e111271b1494995708a9e878a10829b5e10c7ba` (HEAD on 2026-10-23) | BSD-3-Clause (`LICENSE.txt`) | Third data point, used to diagnose the failed markupsafe job on the box app |

Gap: both are Python. The charter asks for a stack unlike FastAPI and React (for example Express or Django). Not yet run; Express was deferred by Architect1.

## 1. Box app result, verified independently

Box app: `/workspace/traces-review/traces`, API `http://127.0.0.1:8731`, job `j_d4c00e3c7141453898ef` (read only: API GETs and a copy of the store; nothing was written there).

| Check | Result |
| --- | --- |
| Job | `succeeded`, phases fetching to history, 06:39:57 to 06:40:28 UTC (12:09:57 to 12:10:28 IST) |
| Snapshot stats | CodeGraph edges 674 = 310 verified + 3 observed + 268 unvalidated + 46 missing_location + 47 rejected; 1,324 static records; history `done`, `complete=true`, 1,988 records. Matches docs/STATUS.md |
| Extractor pins | CodeGraph 1.6.2, TypeScript 6.0.3, CPython 3.14.8, isolation `unshare` |
| Reproduction | Fresh store and cache (`traces serve` on port 18800 from `ws/lab-acceptance`), `POST /repos` with the SHA, `POST /index-jobs`: succeeded in 6 s. Same stats. Export of both stores: 3,312 records each, identical `claim_id` sets, 0 status differences |
| Pinned SHA | `git rev-parse HEAD` of the cached checkout = `672971d...`; `ls-remote` HEAD on 2026-10-23 is the same commit |

### Spot-check against Git (`.traces-data/acceptance/second-repo/spotcheck.py`, stdlib `ast` + `git`, seed 20261023)

| Sample | Result |
| --- | --- |
| 30 random verified static relationships: site line in range and names the target, target declaration at the cited line | 30 of 30 correct (one first flagged by the script was a reference to a module-level assignment `_bytes_to_int = ...` at encoding.py:46, which the script only looked for as `def`/`class`; the claim is right) |
| 20 random commit nodes: commit exists, is an ancestor of the pin, parents match | 20 of 20 |
| 30 random file-change records (modifies, adds, deletes) against `git diff --name-status -M50%` with the cited parent | 30 of 30 |
| 25 file co-change records recounted with `git log --no-merges --follow`, bot authors excluded | support exact in 23 of 25; every difference is 1 commit, consistent with the recorded `commits_skipped_large: 1` filter |
| 47 rejected CodeGraph relationships | 46 are relative imports (`from .exc import ...`) that are present in the source exactly as claimed; 1 is `TimestampSigner.validate -> unsign` (timed.py:164), also correct. All 47 rejections are wrong (findings F-4, F-5) |

## 2. Explicit unknowns and what the product shows

| Question | itsdangerous result |
| --- | --- |
| Purpose | Overview marks it `unknown`, and quotes the README heading "ItsDangerous" as `interpretation`. Nothing invented |
| Entry points | `GET /routes` = `[]`; overview: "No route nodes or routes_to claims are stored. That is an absence of records, not proof the software has no HTTP routes." |
| Frameworks | `pytest` only (from `pyproject.toml`). No web framework invented |
| Graph default | 300 verified edges (truncated at the limit), `hidden_counts.rejected = 47`; no rejected edge drawn |
| Trace from `TimestampSigner::validate` | one `gap` hop, label `inferred`, reason "This symbol has no outgoing static relationship in the store." The real call to `unsign` exists but was rejected (F-5) and hidden, so the reason text is inaccurate (see O-2) |

## 3. Overfitting to the FastAPI fixture

| Signal | Detail | Owner |
| --- | --- | --- |
| F-4 relative imports rejected | The import check compares `ImportFrom.module` (`exc`) with CodeGraph's name (`.exc`) and ignores `level`. fsft uses absolute imports, so the baseline never hit it. itsdangerous: 46 of 46 rejected imports are true; markupsafe: 2 of 2. Repro: `tests/e2e/test_python_package_patterns.py::test_relative_imports_not_rejected` (xfail strict) | Traces (validators) |
| F-5 `@typing.overload` | `self.unsign(...)` is resolved to the first overload stub instead of the last (runtime) definition, so a correct call edge is rejected. Repro: `...::test_overload_call_to_implementation_not_rejected` (xfail strict) | Traces (validators) |
| Layer label | `src/itsdangerous` is labelled layer `backend` by `layer-v1:path-and-extension`. A library has no backend; "backend" is a FastAPI-template word | Traces (components) |
| O-2 gap reason | A trace gap says "no outgoing static relationship in the store" when the only outgoing relationship is rejected and hidden. Suggest "no outgoing relationship that is not rejected (N hidden)" | Traces (views) |

## 4. The failed markupsafe snapshot on the box app (root cause)

Read from the box store copy and API (read only):

- Job `j_26a08a94da4e467dbba0`, created 06:40:26 UTC (12:10:26 IST), for snapshot `github.com__pallets__markupsafe@0000000000000000000000000000000000000001`. Events: queued, fetching, then `failed` with `sha_not_found`: "commit 0000000000000000000000000000000000000001 is not in pallets/markupsafe".
- The repository's real HEAD, recorded by the same registration, is `4e111271b1494995708a9e878a10829b5e10c7ba`.
- Root cause: the job was submitted with a SHA that does not exist. This is not F-1: markupsafe has no non-ASCII paths (`git ls-tree -r --name-only` at `4e11127` shows none), and the failure happened in `fetching`, before the adapter runs.
- Control: indexing markupsafe at its real HEAD `4e11127` through the same API path on a fresh store succeeded in 8.5 s: 361 CodeGraph edges (231 verified, 5 observed, 101 unvalidated, 22 missing_location, 2 rejected), history `done`, 2,326 records. The 2 rejected are relative imports (F-4).
- The failure itself is safe and visible (job `failed`, code `sha_not_found`, partial clone removed). Side effects recorded as F-6.

F-6 (low, Traces seat, API/ingest): `POST /repos/{id}/index-jobs` accepts any well-formed SHA. A nonexistent SHA costs a full clone before `sha_not_found`, leaves a `failed` snapshot row at that SHA in `GET /repos/{id}/snapshots`, and leaves an empty `.cache/targets/<repo>/<sha>/` directory. Repro: `POST /api/v1/repos/github.com__pallets__markupsafe/index-jobs {"sha":"0000000000000000000000000000000000000001"}`.

## Commands (exact)

```
TRACES_DATA_DIR=$A/data TRACES_CACHE_DIR=$A/cache TRACES_ISOLATION=unshare uv run --frozen traces serve --host 127.0.0.1 --port 18800
curl -H 'content-type: application/json' -d '{"url":"https://github.com/pallets/itsdangerous","sha":"672971d66a2ef9f85151e53283113f33d642dabd"}' 127.0.0.1:18800/api/v1/repos
curl -H 'content-type: application/json' -d '{"sha":"672971d66a2ef9f85151e53283113f33d642dabd"}' 127.0.0.1:18800/api/v1/repos/github.com__pallets__itsdangerous/index-jobs
curl 127.0.0.1:8731/api/v1/repos/github.com__pallets__itsdangerous/snapshots/672971d66a2ef9f85151e53283113f33d642dabd/export   # box app, read only
python3 spotcheck.py box/itsd_export.ndjson <cached checkout> 672971d66a2ef9f85151e53283113f33d642dabd
```
