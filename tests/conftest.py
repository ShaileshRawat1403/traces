"""Shared fixtures. The `baseline_run` fixture runs the Task 002 verification pipeline once per session against the
pinned target fastapi/full-stack-fastapi-template@b1125d8, which is fetched at setup into the gitignored cache
(.cache/targets/...). No target source text is committed. Set TRACES_BASELINE_RUN=<run dir> to reuse a finished run."""
from __future__ import annotations

import os
from pathlib import Path

import pytest


def _toolchain_ready() -> str | None:
    from traces.core.config import get_settings

    s = get_settings()
    if not s.codegraph_bin.exists() or not s.ts_module.exists():
        return f"toolchain not installed in {s.toolchain_dir} (run: make toolchain)"
    return None


@pytest.fixture(scope="session")
def baseline_run() -> Path:
    reuse = os.environ.get("TRACES_BASELINE_RUN")
    if reuse:
        p = Path(reuse).resolve()
        assert (p / "inside_result.json").exists(), f"TRACES_BASELINE_RUN={p} has no inside_result.json"
        return p
    why = _toolchain_ready()
    if why:
        pytest.fail(why)  # a missing toolchain is a failure, never a silent skip
    from traces.evidence.pipeline import run_baseline

    return run_baseline()


@pytest.fixture(scope="session")
def ct_results(baseline_run: Path) -> dict:
    from tests.contract._ct import evaluate

    return evaluate(baseline_run)


@pytest.fixture(scope="session")
def rt_results(baseline_run: Path) -> dict:
    from tests.regression._rt import evaluate

    return evaluate(baseline_run)
