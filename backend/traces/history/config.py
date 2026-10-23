"""History configuration, defaults and digests (docs/contracts/history.md section 12)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

from .errors import E_CONFIG, HistoryError

PACKAGE_VERSION = "0.1.0"
EXTRACTOR = {"name": "traces-history", "version": PACKAGE_VERSION}
MAX_MILESTONES_DEFAULT = 8
MAX_MILESTONES_ON_DEMAND = 20

DEFAULT_BOT_PATTERNS: tuple[str, ...] = (r"\[bot\]", r"dependabot", r"renovate", r"github-actions", r"pre-commit-ci")
DEFAULT_LOCKFILES: tuple[str, ...] = (
    "package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml", "bun.lock", "bun.lockb", "uv.lock",
    "poetry.lock", "Pipfile.lock", "Cargo.lock", "go.sum", "composer.lock", "Gemfile.lock",
)
DEFAULT_BASENAME_GLOBS: tuple[str, ...] = ("*.gen.*", "*.min.js", "*.min.css")
DEFAULT_DIR_SEGMENTS: tuple[str, ...] = ("__generated__", "generated", "vendor", "dist", "build")
DEFAULT_CODE_EXTENSIONS: tuple[str, ...] = (
    ".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte", ".go", ".rs", ".java", ".kt",
    ".kts", ".scala", ".rb", ".php", ".cs", ".c", ".h", ".cc", ".cpp", ".hpp", ".swift", ".m", ".mm", ".sh",
)


def canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(obj: Any) -> str:
    return hashlib.sha256(canon(obj).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Thresholds:
    min_revs: int = 5
    min_shared_revs: int = 5
    min_coupling: float = 0.30
    max_changeset_size: int = 30
    rename_threshold: int = 50
    copy_threshold: int = 50
    rename_limit: int = 10000
    quick_delete_days: int = 30
    bulk_move_min_files: int = 3
    alias_min_similarity: float = 0.5

    def validate(self) -> None:
        for name in ("min_revs", "min_shared_revs", "max_changeset_size", "rename_limit", "bulk_move_min_files"):
            if getattr(self, name) < 1:
                raise HistoryError(E_CONFIG, f"threshold {name} must be >= 1", "config")
        for name in ("rename_threshold", "copy_threshold"):
            if not 1 <= getattr(self, name) <= 100:
                raise HistoryError(E_CONFIG, f"{name} must be between 1 and 100", "config")
        for name in ("min_coupling", "alias_min_similarity"):
            if not 0.0 <= getattr(self, name) <= 1.0:
                raise HistoryError(E_CONFIG, f"{name} must be between 0 and 1", "config")
        if self.quick_delete_days < 0:
            raise HistoryError(E_CONFIG, "quick_delete_days must be >= 0", "config")


@dataclass(frozen=True)
class FilterSpec:
    """Bot and generated-file criteria. Every field is echoed in report.json and in record parameters."""

    bot_author_patterns: tuple[str, ...] = DEFAULT_BOT_PATTERNS
    generated_basenames: tuple[str, ...] = DEFAULT_LOCKFILES
    generated_basename_globs: tuple[str, ...] = DEFAULT_BASENAME_GLOBS
    generated_dir_segments: tuple[str, ...] = DEFAULT_DIR_SEGMENTS
    extra_generated_paths: frozenset[str] = frozenset()
    extra_generated_source: str = "none"
    exclude_bots_from_patterns: bool = True
    exclude_generated_from_patterns: bool = True

    def criteria(self) -> dict[str, Any]:
        return {
            "bot_author_patterns": list(self.bot_author_patterns),
            "bot_match": "case-insensitive regex search on mailmapped author name (%aN) and email (%aE)",
            "generated_basenames": list(self.generated_basenames),
            "generated_basename_globs": list(self.generated_basename_globs),
            "generated_dir_segments": list(self.generated_dir_segments),
            "generated_dir_rule": "a directory segment of the path equals one listed name, at any depth (whole segments only)",
            "extra_generated_paths_count": len(self.extra_generated_paths),
            "extra_generated_paths_digest": digest(sorted(self.extra_generated_paths)),
            "extra_generated_source": self.extra_generated_source,
            "exclude_bots_from_patterns": self.exclude_bots_from_patterns,
            "exclude_generated_from_patterns": self.exclude_generated_from_patterns,
        }


@dataclass(frozen=True)
class Limits:
    max_commits: int = 200_000
    max_paths_per_commit: int = 50_000
    max_blob_bytes: int = 2_000_000
    git_call_timeout_s: float = 120.0
    max_git_output_bytes: int = 1 << 30


@dataclass(frozen=True)
class HistoryConfig:
    thresholds: Thresholds = field(default_factory=Thresholds)
    filters: FilterSpec = field(default_factory=FilterSpec)
    mailmap: str = "pinned_blob"  # or "none"
    limits: Limits = field(default_factory=Limits)
    code_extensions: tuple[str, ...] = DEFAULT_CODE_EXTENSIONS
    verify: bool = True  # run independent git plumbing checks and recounts (needed for observed status)
    aliases: bool = False  # opt in to the run() aliases stage (D-H14); off keeps it skipped with not_in_v1_default

    def validate(self) -> HistoryConfig:
        self.thresholds.validate()
        if not isinstance(self.aliases, bool):
            raise HistoryError(E_CONFIG, "aliases must be a bool", "config")
        if self.mailmap not in ("pinned_blob", "none"):
            raise HistoryError(E_CONFIG, "mailmap must be 'pinned_blob' or 'none'", "config")
        import re

        for pat in self.filters.bot_author_patterns:
            try:
                re.compile(pat)
            except re.error as e:
                raise HistoryError(E_CONFIG, f"invalid bot pattern {pat!r}: {e}", "config") from e
        return self

    def ingest_params(self) -> dict[str, Any]:
        t = self.thresholds
        return {"rename_threshold": t.rename_threshold, "copy_threshold": t.copy_threshold,
                "rename_limit": t.rename_limit, "mailmap": self.mailmap}

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["filters"]["extra_generated_paths"] = sorted(self.filters.extra_generated_paths)
        return d

    def digest(self) -> str:
        return digest(self.as_dict())
