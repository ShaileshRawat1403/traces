#!/usr/bin/env bash
# Real browser pass: seed a local snapshot, serve API + web, run Playwright.
# Requires the pinned toolchain (`make toolchain`) and web dependencies (`cd web && npm ci`).
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

cleanup() {
  if [ -n "${API_PID:-}" ]; then kill "$API_PID" 2>/dev/null || true; fi
  if [ -n "${WEB_PID:-}" ]; then kill "$WEB_PID" 2>/dev/null || true; fi
  rm -rf "$DATA"
}
trap cleanup EXIT

uv run --frozen python scripts/e2e_seed.py "$DATA"
uv run --frozen traces serve --host 127.0.0.1 --port "$API_PORT" >/tmp/traces-e2e-api.log 2>&1 &
API_PID=$!
for _ in $(seq 1 50); do
  curl -fsS "http://127.0.0.1:$API_PORT/api/v1/health" >/dev/null 2>&1 && break
  sleep 0.2
done
curl -fsS "http://127.0.0.1:$API_PORT/api/v1/repos" | grep -q octo

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
TRACES_WEB_URL="http://127.0.0.1:$WEB_PORT" npx --no-install playwright test
