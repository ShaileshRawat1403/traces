# Traces developer commands. The single start path is `make start` (= ./scripts/start.sh).
.PHONY: start bootstrap toolchain lint typecheck test test-fast baseline openapi api-types web-build check

start:
	./scripts/start.sh

bootstrap:
	uv sync --frozen
	cd toolchain && npm ci --ignore-scripts --no-audit --no-fund
	cd web && npm ci --ignore-scripts --no-audit --no-fund

toolchain:
	cd toolchain && npm ci --ignore-scripts --no-audit --no-fund

lint:
	uv run --frozen ruff check backend tests

typecheck:
	uv run --frozen mypy
	cd web && npm run -s typecheck

# Unit + API tests (no network, no toolchain).
test-fast:
	uv run --frozen pytest -q tests/unit tests/api

# Everything, including the Task 002 baseline (fetches the pinned target into .cache/, runs CodeGraph in the sandbox).
test:
	uv run --frozen pytest -q tests

baseline:
	uv run --frozen python -m traces.evidence.pipeline baseline

openapi:
	uv run --frozen traces openapi --out docs/contracts/openapi.json
	cd web && npm run -s gen:api

web-build:
	cd web && npm run -s build

check: lint typecheck test-fast
	cd web && npm run -s check:api
