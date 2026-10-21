"""Portable configuration. Every path comes from an environment variable or is derived from the repository root.
No absolute box paths. See docs/SETUP.md for the variables."""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]  # backend/traces/core/config.py -> repo root


def _path(env: str, default: Path) -> Path:
    v = os.environ.get(env)
    return Path(v).expanduser().resolve() if v else default


@dataclass(frozen=True)
class Settings:
    repo_root: Path
    data_dir: Path        # SQLite store, run directories (gitignored)
    cache_dir: Path       # pinned target checkouts (gitignored)
    toolchain_dir: Path   # npm project with CodeGraph 1.6.2 + TypeScript 6.0.3 (package-lock.json pinned)
    node: str             # Node.js for the TypeScript validator
    isolation: str        # "auto" | "unshare" | "none"

    @property
    def runs_dir(self) -> Path:
        return self.data_dir / "runs"

    @property
    def targets_dir(self) -> Path:
        return self.cache_dir / "targets"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "traces.sqlite3"

    @property
    def node_modules(self) -> Path:
        return self.toolchain_dir / "node_modules"

    @property
    def ts_module(self) -> Path:
        return self.node_modules / "typescript"

    @property
    def codegraph_package_dir(self) -> Path:
        return self.node_modules / "@colbymchenry" / "codegraph"

    @property
    def codegraph_bin(self) -> Path:
        return self.node_modules / ".bin" / "codegraph"

    @property
    def codegraph_bundled_node(self) -> Path:
        return self.node_modules / "@colbymchenry" / "codegraph-linux-x64" / "node"

    @property
    def lockfile(self) -> Path:
        return self.toolchain_dir / "package-lock.json"

    @property
    def registry_record(self) -> Path:
        return self.toolchain_dir / "registry_record.json"

    @property
    def workers_dir(self) -> Path:
        return self.repo_root / "workers"


def get_settings() -> Settings:
    root = _path("TRACES_REPO_ROOT", REPO_ROOT)
    return Settings(
        repo_root=root,
        data_dir=_path("TRACES_DATA_DIR", root / ".traces-data"),
        cache_dir=_path("TRACES_CACHE_DIR", root / ".cache"),
        toolchain_dir=_path("TRACES_TOOLCHAIN_DIR", root / "toolchain"),
        node=os.environ.get("TRACES_NODE") or shutil.which("node") or "node",
        isolation=os.environ.get("TRACES_ISOLATION", "auto"),
    )
