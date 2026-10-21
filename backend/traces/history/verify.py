"""Independent Git plumbing checks (decision D-H2). These never read the ingest parse: they ask Git again through
other call paths (`cat-file`, `ls-tree`, `diff-tree` per commit, `log --follow`, `log --name-only`) and compare."""

from __future__ import annotations

import os
import threading
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from .filters import Filters
from .gitcmd import GitRunner
from .model import HistoryLog, decode_path, encode_path


def _decode(p: bytes) -> str:
    return decode_path(p)[0]


def resolve_blobs(runner: GitRunner, items: Sequence[tuple[str, bytes]]) -> dict[tuple[str, bytes], str | None]:
    """Map (commit, path bytes) to the blob id at that path in that commit's tree, or None when absent."""
    out: dict[tuple[str, bytes], str | None] = {}
    uniq = sorted(set(items))
    if not uniq:
        return out
    stdin = b"".join(c.encode() + b":" + p + b"\0" for c, p in uniq)
    res = runner.run("cat-file", ["--batch-check=%(objectname) %(objecttype)", "-Z"], stdin=stdin).split(b"\0")
    for (c, p), line in zip(uniq, res, strict=False):
        if line.endswith(b" missing") or b" " not in line:
            out[(c, p)] = None
        else:
            oid, typ = line.split(b" ", 1)
            out[(c, p)] = oid.decode() if typ in (b"blob", b"commit") else None  # commit = gitlink
    return out


def read_objects(runner: GitRunner, names: Sequence[bytes], *, want: bytes = b"blob") -> dict[bytes, bytes | None]:
    """Read object contents with `cat-file --batch -Z`. Names are object ids or `<rev>:<path>` (path bytes). A name
    that is missing or not of type `want` maps to None."""
    out: dict[bytes, bytes | None] = {}
    uniq = sorted(set(names))
    if not uniq:
        return out
    data = runner.run("cat-file", ["--batch", "-Z"], stdin=b"".join(n + b"\0" for n in uniq))
    i = 0
    for n in uniq:
        j = data.index(b"\0", i)
        head = data[i:j]
        if head.endswith(b" missing") or head.endswith(b" ambiguous") or head.count(b" ") != 2:
            out[n] = None
            i = j + 1
            continue
        _, typ, size = head.split(b" ")
        k = int(size)
        out[n] = data[j + 1:j + 1 + k] if typ == want else None
        i = j + 1 + k + 1
    return out


def read_commit_parents(runner: GitRunner, shas: Sequence[str]) -> dict[str, tuple[str, ...] | None]:
    """Parents read from the raw commit objects (`cat-file --batch -Z`), independent of log/rev-list."""
    out: dict[str, tuple[str, ...] | None] = {}
    if not shas:
        return out
    data = runner.run("cat-file", ["--batch", "-Z"], stdin=b"".join(s.encode() + b"\0" for s in shas))
    i = 0
    for s in shas:
        j = data.index(b"\0", i)
        head = data[i:j].split(b" ")
        if len(head) != 3 or head[1] != b"commit":
            out[s] = None
            i = j + 1
            continue
        size = int(head[2])
        body = data[j + 1:j + 1 + size]
        i = j + 1 + size + 1
        hdr = body.split(b"\n\n", 1)[0]
        out[s] = tuple(line[7:].decode() for line in hdr.split(b"\n") if line.startswith(b"parent "))
    return out


@dataclass(frozen=True)
class FollowEntry:
    commit: str
    author_name: str
    author_email: str
    added: int
    deleted: int


class Recounter:
    """Memoized independent recounts for one log. Thread-safe; Git calls run in a small pool."""

    def __init__(self, log: HistoryLog, runner: GitRunner, filters: Filters) -> None:
        self.log = log
        self.runner = runner
        self.filters = filters
        self._follow: dict[str, list[FollowEntry]] = {}
        self._sizes: dict[str, tuple[str, str, int]] | None = None
        self._lock = threading.Lock()

    def follow(self, path: str, non_utf8: bool = False) -> list[FollowEntry]:
        with self._lock:
            if path in self._follow:
                return self._follow[path]
        t = self.log.config.thresholds
        arg = os.fsdecode(encode_path(path, non_utf8))
        out = self.runner.run("log", ["--follow", "--no-merges", f"-M{t.rename_threshold}%", "--numstat",
                                      "--format=%x01%H%x09%aN%x09%aE", self.log.repo.sha, "--", arg])
        entries: list[FollowEntry] = []
        cur: list[object] | None = None
        for line in out.split(b"\n"):
            if line.startswith(b"\x01"):
                if cur is not None:
                    entries.append(FollowEntry(*cur))  # type: ignore[arg-type]
                h, an, ae = line[1:].split(b"\t", 2)
                cur = [h.decode(), an.decode("utf-8", "replace"), ae.decode("utf-8", "replace"), 0, 0]
            elif cur is not None and b"\t" in line:
                a, d, _ = line.split(b"\t", 2)
                cur[3] = int(cur[3]) + (0 if a == b"-" else int(a))  # type: ignore[call-overload]
                cur[4] = int(cur[4]) + (0 if d == b"-" else int(d))  # type: ignore[call-overload]
        if cur is not None:
            entries.append(FollowEntry(*cur))  # type: ignore[arg-type]
        with self._lock:
            self._follow[path] = entries
        return entries

    def prefetch(self, paths: Iterable[tuple[str, bool]]) -> None:
        todo = [p for p in paths if p[0] not in self._follow]
        if not todo:
            return
        with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 2)) as ex:
            list(ex.map(lambda p: self.follow(*p), todo))

    def changeset_sizes(self) -> dict[str, tuple[str, str, int]]:
        """commit -> (author name, author email, number of non-generated changed paths), from an independent
        `log --name-only -M -C` stream over non-merge commits."""
        if self._sizes is not None:
            return self._sizes
        t = self.log.config.thresholds
        out = self.runner.run("log", ["--no-merges", "-z", f"-M{t.rename_threshold}%", f"-C{t.copy_threshold}%",
                                      f"-l{t.rename_limit}", "--name-only", "--format=%x01%H%x00%aN%x00%aE",
                                      self.log.repo.sha])
        sizes: dict[str, tuple[str, str, int]] = {}
        toks = out.split(b"\0")
        i, n = 0, len(toks)
        while i < n:
            t0 = toks[i]
            if t0.startswith(b"\x01") or t0.startswith(b"\n\x01"):
                sha = t0.lstrip(b"\n")[1:].decode()
                an = toks[i + 1].decode("utf-8", "replace")
                ae = toks[i + 2].decode("utf-8", "replace")
                i += 3
                count = 0
                first = True
                while i < n and not (toks[i].startswith(b"\x01") or toks[i].startswith(b"\n\x01")):
                    p = toks[i]
                    if first and p.startswith(b"\n"):
                        p = p[1:]
                    first = False
                    i += 1
                    if p == b"":
                        continue
                    if not self.filters.is_generated(_decode(p)):
                        count += 1
                sizes[sha] = (an, ae, count)
            else:
                i += 1
        self._sizes = sizes
        return sizes
