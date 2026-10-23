#!/usr/bin/env bash
# Real browser pass: seed a local snapshot, serve API + web, run Playwright.
# Requires the pinned toolchain (`make toolchain`) and web dependencies (`cd web && npm ci`).
# TRACES_E2E_SEED=synthetic (default, fast) or fsft (the pinned target from the cached full-history
# clone at TRACES_E2E_FSFT_REPO; CI uses fsft). See scripts/e2e_seed.py.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
DATA=$(mktemp -d)
API_PORT="${TRACES_API_PORT:-8000}"
WEB_PORT="${TRACES_WEB_PORT:-5173}"
export TRACES_DATA_DIR="$DATA"
export TRACES_ISOLATION="${TRACES_ISOLATION:-unshare}"
export PATH="/usr/local/bin:${PATH}"
if [ -w /proc/sys/net/core/fb_tunnels_only_for_init_net ]; then
  echo 1 > /proc/sys/net/core/fb_tunnels_only_for_init_net || true
fi

# shellcheck disable=SC2329  # invoked by the EXIT trap below
cleanup() {
  if [ -n "${API_PID:-}" ]; then kill "$API_PID" 2>/dev/null || true; fi
  # npx does not forward the signal to vite (a grandchild); stop this run's dev server by its port so none outlives the run.
  if [ -n "${WEB_PID:-}" ]; then kill "$WEB_PID" 2>/dev/null || true; pkill -f "vite --host 127.0.0.1 --port $WEB_PORT\$" 2>/dev/null || true; fi
  rm -rf "$DATA"
}
trap cleanup EXIT

SEED="${TRACES_E2E_SEED:-synthetic}"
uv run --frozen python scripts/e2e_seed.py "$DATA" --seed "$SEED" | tee "$DATA/seeded.txt"
REPO_ID=$(cut -d' ' -f1 "$DATA/seeded.txt")
uv run --frozen traces serve --host 127.0.0.1 --port "$API_PORT" >/tmp/traces-e2e-api.log 2>&1 &
API_PID=$!
for _ in $(seq 1 50); do
  curl -fsS "http://127.0.0.1:$API_PORT/api/v1/health" >/dev/null 2>&1 && break
  sleep 0.2
done
curl -fsS "http://127.0.0.1:$API_PORT/api/v1/repos" | grep -q "$REPO_ID"
echo "e2e seed: $SEED ($(cat "$DATA/seeded.txt"))"

cd web
if ! npx --no-install playwright test --list >/dev/null 2>&1; then
  npx --no-install playwright install chromium
fi
TRACES_API_URL="http://127.0.0.1:$API_PORT" npx --no-install vite --host 127.0.0.1 --port "$WEB_PORT" >/tmp/traces-e2e-web.log 2>&1 &
WEB_PID=$!
cd "$ROOT"
for _ in $(seq 1 50); do
  curl -fsS "http://127.0.0.1:$WEB_PORT/" >/dev/null 2>&1 && break
  sleep 0.2
done
cd web
rc=0
TRACES_WEB_URL="http://127.0.0.1:$WEB_PORT" npx --no-install playwright test || rc=$?
if [ "$SEED" = "fsft" ]; then
  # Real-snapshot content, axe (WCAG 2.2 AA) and 360 px touch checks; fsft-specific, so only on the fsft seed.
  WEB="http://127.0.0.1:$WEB_PORT" SHOTS="${TRACES_SHOTS_DIR:-test-results/shots}/real-snapshot" node "$ROOT/tests/e2e/real_snapshot.cjs" || rc=$?
fi
exit "$rc"
