# Setup

Requirements: Linux (user namespaces for `unshare -rn`), git, [uv](https://docs.astral.sh/uv/), Node.js >= 20.19 with npm. uv installs CPython 3.14.8 from `.python-version`.

## Start (the one documented path)

```
./scripts/start.sh        # or: make start
```

Installs from lockfiles (`uv sync --frozen`; `npm ci --ignore-scripts` in `toolchain/` and `web/`), serves the API at http://127.0.0.1:8000 (OpenAPI UI at `/docs`) and the web app at http://127.0.0.1:5173.

## Load the baseline evidence

```
uv run --frozen python -m traces.evidence.pipeline baseline --run-id dev1   # about 1 minute; fetches the pinned target into .cache/
uv run --frozen traces import-run .traces-data/runs/dev1                     # migrate to 0.4 and load into the store
```

## Tests

```
make test-fast                                   # unit + API: uv run --frozen pytest -q tests/unit tests/api
make test                                        # everything incl. a fresh baseline run (CT1-16, RT1-8)
TRACES_BASELINE_RUN=.traces-data/runs/dev1 uv run --frozen pytest -q tests   # reuse a finished run
make lint typecheck                              # ruff, mypy, web tsc
cd web && npm run check:api                      # generated TS types match docs/contracts/openapi.json
```

## Configuration (environment)

| Variable | Default | Meaning |
| --- | --- | --- |
| `TRACES_DATA_DIR` | `.traces-data` | store (`traces.sqlite3`) and runs |
| `TRACES_CACHE_DIR` | `.cache` | pinned target checkouts |
| `TRACES_TOOLCHAIN_DIR` | `toolchain` | CodeGraph and TypeScript install |
| `TRACES_ISOLATION` | `auto` | `unshare` or `none` (fallback; CT15 then fails by design) |
| `TRACES_LIMIT_AS_KB` | unset | opt-in address-space limit (breaks CodeGraph today, D-006) |
| `TRACES_MAX_CLONE_MB` | 1024 | clone size cap, measured while `git clone` runs (D-021) |
| `TRACES_CLONE_TIMEOUT_S` | 900 | clone wall-clock cap |
| `TRACES_MAX_FILES`, `TRACES_MAX_TREE_MB` | 100000, 1024 | checkout caps, checked from Git objects before checkout |
| `TRACES_MAX_RSS_MB` | 6144 | index worker memory cap (RSS watchdog over the sandboxed process tree, D-022) |
| `TRACES_INDEX_TIMEOUT_S` | 1800 | wall-clock cap per sandboxed index step |
| `TRACES_INDEX_WORKERS` | 1 | concurrent index jobs |
| `TRACES_NETWORK_TESTS` | unset | `1` runs the live GitHub ingest checks in `tests/unit/test_ingest.py` |
| `TRACES_API_PORT`, `TRACES_WEB_PORT` | 8000, 5173 | start script ports |

If `unshare -rn true` fails on Ubuntu 24.04+, allow unprivileged user namespaces: `sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0`.
