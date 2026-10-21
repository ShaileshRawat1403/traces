# traces
Trace the decisions. Link the relationships. Understand the system.

Traces maps a public GitHub repository at a pinned commit into evidence-backed claims: every relationship carries its source locations, the checks that ran, and a status (Verified, Observed, Inferred, Rejected). Static analysis only; no runtime behavior is observed.

This branch (`build/traces-v1`) is the v1 integration branch. Status: [docs/STATUS.md](docs/STATUS.md).

## Start

```
./scripts/start.sh      # or: make start  (API :8000, web :5173)
```

Setup, baseline and tests: [docs/SETUP.md](docs/SETUP.md).

## Layout

| Path | What |
| --- | --- |
| `backend/traces/evidence` | evidence schema (0.3 frozen, 0.4 current), migrations, SQLite store, verification pipeline |
| `backend/traces/adapter` | fail-closed CodeGraph 1.6.2 adapter |
| `backend/traces/validators` | Python (CPython 3.14 `ast`) and TypeScript (6.0.3 Compiler API) validators, frozen line checker |
| `backend/traces/ingest` | URL validation, hardened pinned checkouts |
| `backend/traces/api` | FastAPI app and models (`docs/contracts/openapi.json`) |
| `backend/traces/history` | history module (Traces History seat); hook points in `interface.py` |
| `backend/traces/explain` | explain and BYOK prompt bundles (Traces UI seat) |
| `workers/` | sandbox (no network, limits) and isolation probes |
| `toolchain/` | pinned CodeGraph and TypeScript |
| `web/` | Vite + React + TypeScript + Cytoscape.js |
| `tests/` | unit, API, contract (CT1-CT16), regression (RT1-RT8) |
| `research/` | Task 002 research record, unchanged |
| `docs/` | [CONTRACTS](docs/CONTRACTS.md), [DECISIONS](docs/DECISIONS.md), [STATUS](docs/STATUS.md), [TEST_MAPPING](docs/TEST_MAPPING.md), [FIXTURES](docs/FIXTURES.md), [THIRD_PARTY_LICENSES](docs/THIRD_PARTY_LICENSES.md) |

## License

MIT. See [LICENSE](LICENSE) and [docs/THIRD_PARTY_LICENSES.md](docs/THIRD_PARTY_LICENSES.md).
