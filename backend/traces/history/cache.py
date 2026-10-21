"""Per-commit parse cache (docs/contracts/history.md section 15). Content-addressed, atomic writes, never inside
the analyzed repository. A corrupt entry is discarded and recomputed."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .config import PACKAGE_VERSION, canon, digest
from .model import Commit


class CommitCache:
    def __init__(self, cache_dir: Path | None, key_params: dict[str, object]) -> None:
        self.dir: Path | None = None
        self.key = digest({"params": key_params, "package": PACKAGE_VERSION})
        self.hits = 0
        self.misses = 0
        self.discarded = 0
        if cache_dir is not None:
            self.dir = Path(cache_dir) / self.key[:16]
            self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, sha: str) -> Path:
        assert self.dir is not None
        return self.dir / sha[:2] / f"{sha}.json"

    def get(self, sha: str) -> Commit | None:
        if self.dir is None:
            return None
        p = self._path(sha)
        if not p.exists():
            self.misses += 1
            return None
        try:
            doc = json.loads(p.read_text("utf-8"))
            body = doc["commit"]
            if doc.get("key") != self.key or body.get("sha") != sha or doc.get("sha256") != digest(body):
                raise ValueError("cache entry does not match its key or digest")
            self.hits += 1
            return Commit.from_json(body)
        except (ValueError, KeyError, TypeError, OSError):
            self.discarded += 1
            self.misses += 1
            try:
                p.unlink()
            except OSError:
                pass
            return None

    def put(self, c: Commit) -> None:
        if self.dir is None:
            return
        p = self._path(c.sha)
        p.parent.mkdir(parents=True, exist_ok=True)
        body = c.to_json()
        data = canon({"key": self.key, "sha256": digest(body), "commit": body})
        fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=".tmp-")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp, p)

    def stats(self) -> dict[str, int]:
        return {"hits": self.hits, "misses": self.misses, "discarded": self.discarded}
