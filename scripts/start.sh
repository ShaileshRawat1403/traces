#!/usr/bin/env bash
# The one documented start path: ./scripts/start.sh  (or `make start`)
# Installs pinned dependencies from lockfiles (no install scripts run), then serves the API on :8000 and the web UI on :5173.
set -euo pipefail
cd "$(dirname "$0")/.."
command -v uv >/dev/null || { echo "uv is required: https://docs.astral.sh/uv/" >&2; exit 1; }
command -v npm >/dev/null || { echo "Node.js >= 20.19 with npm is required" >&2; exit 1; }

uv sync --frozen
(cd toolchain && npm ci --ignore-scripts --no-audit --no-fund)
(cd web && npm ci --ignore-scripts --no-audit --no-fund)

API_PORT="${TRACES_API_PORT:-8000}"
uv run --frozen traces serve --host 127.0.0.1 --port "$API_PORT" &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT INT TERM
for _ in $(seq 1 50); do
  curl -fsS "http://127.0.0.1:$API_PORT/api/v1/health" >/dev/null 2>&1 && break
  sleep 0.2
done
echo "API: http://127.0.0.1:$API_PORT/api/v1/health   docs: http://127.0.0.1:$API_PORT/docs"
cd web && TRACES_API_URL="http://127.0.0.1:$API_PORT" npx --no-install vite --host 127.0.0.1 --port "${TRACES_WEB_PORT:-5173}"
