"""Fixtures for the history tests. The fsft regression fixture is a local full-history clone of
fastapi/full-stack-fastapi-template; set TRACES_HISTORY_FSFT_REPO to its path. Tests skip with a clear reason when it
is absent. Nothing from that repository is ever executed: the history module only reads Git objects."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from traces.history import HistoryConfig, RepoRef
from traces.history.config import FilterSpec

from ._repo import SynthRepo

FSFT_SHA = "b1125d8839482cb7bbae603ddc6d0081bf87532e"
FSFT_CANDIDATES = (
    "/workspace/traces-research/_src/full-stack-fastapi-template",
    ".cache/targets/github.com__fastapi__full-stack-fastapi-template",
)


def _fsft_path() -> tuple[Path | None, str]:
    from traces.history import GitRunner, HistoryError

    env = os.environ.get("TRACES_HISTORY_FSFT_REPO")
    root = Path(__file__).resolve().parents[2]
    cands = [Path(env)] if env else [root / c if not os.path.isabs(c) else Path(c) for c in FSFT_CANDIDATES]
    tried: list[str] = []
    for p in cands:
        for q in (p, p / FSFT_SHA):
            if not q.is_dir():
                continue
            try:
                with GitRunner(q) as r:
                    r.verify_commit(FSFT_SHA)
                return q, ""
            except HistoryError as e:
                tried.append(f"{q}: {e.code}")
    why = f"fsft fixture clone not found; set TRACES_HISTORY_FSFT_REPO to a full clone containing {FSFT_SHA}"
    return None, why + (f" (tried {'; '.join(tried)})" if tried else "")


@pytest.fixture(scope="session")
def fsft_repo() -> RepoRef:
    p, why = _fsft_path()
    if p is None:
        pytest.skip(why)
    return RepoRef(p, "fastapi/full-stack-fastapi-template", FSFT_SHA)


@pytest.fixture
def synth(tmp_path: Path) -> SynthRepo:
    return SynthRepo(tmp_path / "repo")


def ref(r: SynthRepo, sha: str | None = None) -> RepoRef:
    return RepoRef(r.path, "synthetic/repo", sha or r.head())


NO_FILTERS = HistoryConfig(filters=FilterSpec(exclude_bots_from_patterns=False, exclude_generated_from_patterns=False))
