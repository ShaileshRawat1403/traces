# Traces UI Playwright specs: handoff to Traces Lab

Traces Lab owns the harness and CI. These specs only need a running API with the Task 002 baseline and a web server that proxies `/api` to it.

## Prerequisites (from the repo root)

```
uv sync --frozen
(cd toolchain && npm ci --ignore-scripts)
uv run --frozen python -m traces.evidence.pipeline baseline --run-id lab1   # about 1 minute, fetches the pinned target
uv run --frozen traces import-run .traces-data/runs/lab1
uv run --frozen traces serve --host 127.0.0.1 --port 8000                   # API, leave running

cd web
npm ci --ignore-scripts
npx playwright install chromium
TRACES_API_URL=http://127.0.0.1:8000 npx vite --port 5173 --strictPort      # or: npm run build && TRACES_API_URL=... npx vite preview --port 5173
```

## Run

```
cd web
TRACES_WEB_URL=http://127.0.0.1:5173 TRACES_SHOTS_DIR=test-results/shots npx playwright test
```

Environment:
- `TRACES_WEB_URL`: the web app (default http://127.0.0.1:5173).
- `TRACES_API_URL`: read by Vite for the `/api` proxy (default http://127.0.0.1:8000).
- `TRACES_SHOTS_DIR`: where screenshots go (default `test-results/shots`).

Two projects run every spec: `desktop` (1280 x 800) and `android-360` (360 x 800, touch).

## Expected result

All tests pass. A few tests are skipped by design because they apply to one viewport only (for example, the phone bottom bar). Every screen runs axe with the WCAG 2.2 AA tags and must report no violations.

Specs:
- `shell.spec.ts`, `snapshot.spec.ts`: app shell, repos, claims, evidence, and the honest 501 states.
- `overview.spec.ts`, `graph.spec.ts`, `trace.spec.ts`, `ask.spec.ts`: each has a **live** test against the real API, plus **contract-shape** tests. A contract-shape test answers only the endpoints that return 501 today (overview, graph, components, source, trace, explain), using generic schema-typed samples from `src/testing/samples.ts`. Claims always come from the real store. Once an endpoint is implemented, its live test checks the real renderer, and the contract-shape test keeps checking the shape.

Known flake: the API shares one sqlite3 connection across threads. Under parallel workers it sometimes returns 500 (`sqlite3.InterfaceError`), which fails `firstSnapshot` in a `beforeAll`. This was reported to the Traces seat. Until it is fixed, run with `--workers=1` for a clean signal.
