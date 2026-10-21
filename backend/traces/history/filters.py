"""Bot and generated-file filters (docs/contracts/history.md section 12, decisions D-H7 and D-H8)."""

from __future__ import annotations

import fnmatch
import re
from functools import cached_property

from .config import FilterSpec


class Filters:
    def __init__(self, spec: FilterSpec) -> None:
        self.spec = spec

    @cached_property
    def _bot_res(self) -> list[re.Pattern[str]]:
        return [re.compile(p, re.I) for p in self.spec.bot_author_patterns]

    def is_bot(self, name: str, email: str) -> bool:
        return any(r.search(name) or r.search(email) for r in self._bot_res)

    def generated_rule(self, path: str) -> str | None:
        """Return the rule that marks `path` as generated, or None. Directory rules match whole segments only:
        `web/dist/app.js` matches `dist`, `distance/x.py` and `build.py` do not."""
        if path in self.spec.extra_generated_paths:
            return f"extra_generated_paths ({self.spec.extra_generated_source})"
        parts = path.split("/")
        base = parts[-1]
        if base in self.spec.generated_basenames:
            return f"basename {base}"
        for g in self.spec.generated_basename_globs:
            if fnmatch.fnmatchcase(base, g):
                return f"basename glob {g}"
        segs = set(parts[:-1])
        for d in self.spec.generated_dir_segments:
            if d in segs:
                return f"dir segment {d}/"
        for extra in self.spec.extra_generated_paths:
            if extra.endswith("/") and path.startswith(extra):
                return f"extra_generated_paths dir ({self.spec.extra_generated_source})"
        return None

    def is_generated(self, path: str) -> bool:
        return self.generated_rule(path) is not None

    def criteria(self) -> dict[str, object]:
        return self.spec.criteria()
