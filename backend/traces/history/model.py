"""Immutable parsed history (docs/contracts/history.md section 8). Local shapes until traces-evidence 0.4 lands."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .config import HistoryConfig
from .interface import HistoryRepoRef


def decode_path(raw: bytes) -> tuple[str, bool]:
    """UTF-8 path, or a percent-encoded form for non-UTF-8 bytes (flag `non_utf8_path`). `%` itself is encoded
    only in the non-UTF-8 form, so valid UTF-8 paths round-trip unchanged."""
    try:
        return raw.decode("utf-8"), False
    except UnicodeDecodeError:
        out = []
        for ch in raw.decode("utf-8", "surrogateescape"):
            o = ord(ch)
            if 0xDC80 <= o <= 0xDCFF:
                out.append(f"%{o - 0xDC00:02X}")
            elif ch == "%":
                out.append("%25")
            else:
                out.append(ch)
        return "".join(out), True


def encode_path(path: str, non_utf8: bool) -> bytes:
    """Inverse of decode_path, for passing a path back to git."""
    if not non_utf8:
        return path.encode("utf-8")
    out = bytearray()
    i = 0
    while i < len(path):
        if path[i] == "%" and i + 3 <= len(path):
            out += bytes([int(path[i + 1:i + 3], 16)])
            i += 3
        else:
            out += path[i].encode("utf-8")
            i += 1
    return bytes(out)


RepoRef = HistoryRepoRef  # hook H1 shape (path, repo, sha), pinned in interface.py


@dataclass(frozen=True)
class Change:
    status: str               # A M D R C T (single letter)
    path: str                 # path after (for D: the deleted path)
    old_path: str | None      # for R and C
    similarity: int | None    # for R and C
    blob_before: str | None
    blob_after: str | None
    mode_before: str
    mode_after: str
    added: int | None = None  # None until numstat known; binary changes have 0 and binary=True
    deleted: int | None = None
    binary: bool = False
    non_utf8: bool = False

    def to_json(self) -> dict[str, Any]:
        return {"status": self.status, "path": self.path, "old_path": self.old_path, "similarity": self.similarity,
                "blob_before": self.blob_before, "blob_after": self.blob_after, "mode_before": self.mode_before,
                "mode_after": self.mode_after, "added": self.added, "deleted": self.deleted, "binary": self.binary,
                "non_utf8": self.non_utf8}

    @staticmethod
    def from_json(d: Mapping[str, Any]) -> Change:
        return Change(**d)


@dataclass(frozen=True)
class Commit:
    sha: str
    parents: tuple[str, ...]
    author_name: str
    author_email: str
    author_time: int
    committer_time: int
    message: str
    changes: tuple[Change, ...]
    rename_limited: bool = False

    @property
    def is_merge(self) -> bool:
        return len(self.parents) > 1

    @property
    def subject(self) -> str:
        return self.message.split("\n", 1)[0]

    def to_json(self) -> dict[str, Any]:
        return {"sha": self.sha, "parents": list(self.parents), "author_name": self.author_name,
                "author_email": self.author_email, "author_time": self.author_time,
                "committer_time": self.committer_time, "message": self.message,
                "changes": [c.to_json() for c in self.changes], "rename_limited": self.rename_limited}

    @staticmethod
    def from_json(d: Mapping[str, Any]) -> Commit:
        return Commit(sha=d["sha"], parents=tuple(d["parents"]), author_name=d["author_name"],
                      author_email=d["author_email"], author_time=d["author_time"],
                      committer_time=d["committer_time"], message=d["message"],
                      changes=tuple(Change.from_json(c) for c in d["changes"]), rename_limited=d["rename_limited"])


@dataclass(frozen=True)
class HistoryLog:
    repo: RepoRef
    config: HistoryConfig
    commits: tuple[Commit, ...]                       # topo order, oldest first, all commits reachable from repo.sha
    first_parent: tuple[str, ...]                     # first-parent chain, oldest first
    merge_fp_diffs: Mapping[str, tuple[Change, ...]]  # merge on first-parent chain -> diff against its first parent
    git_version: str
    mailmap_blob: str | None
    warnings: tuple[str, ...] = ()
    cache_stats: Mapping[str, int] = field(default_factory=dict)

    @property
    def by_sha(self) -> dict[str, Commit]:
        return {c.sha: c for c in self.commits}

    def ingest_parameters(self) -> dict[str, Any]:
        p = dict(self.config.ingest_params())
        p["mailmap_blob"] = self.mailmap_blob
        p["merge_policy"] = "events and churn: non-merge commits; replay: first-parent, merges diffed against first parent"
        return p
