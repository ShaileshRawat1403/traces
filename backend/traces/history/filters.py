"""Bot and generated-file filters (docs/contracts/history.md section 12, decisions D-H7 and D-H8)."""

from __future__ import annotations

import fnmatch
import re
from collections import Counter
from collections.abc import Iterable
from functools import cached_property
from typing import Any

from .config import FilterSpec


class Filters:
    def __init__(self, spec: FilterSpec) -> None:
        self.spec = spec

    @cached_property
    def _bot_res(self) -> list[re.Pattern[str]]:
        return [re.compile(p, re.I) for p in self.spec.bot_author_patterns]

    def is_bot(self, name: str, email: str) -> bool:
        return any(r.search(name) or r.search(email) for r in self._bot_res)

    def bot_rule(self, name: str, email: str) -> str | None:
        """The first bot pattern that matches the author, or None."""
        for p, r in zip(self.spec.bot_author_patterns, self._bot_res, strict=True):
            if r.search(name) or r.search(email):
                return p
        return None

    def removals(self, commits: Iterable[Any]) -> dict[str, Any]:
        """Per-rule removal counts over non-merge commits, for reports (contract section 12: every filtered view
        states what was removed and how much, by rule). Counts are reported even when a filter is switched off,
        with `applied` telling whether the pattern stages used it."""
        bots: Counter[str] = Counter()
        gen: Counter[str] = Counter()
        gen_paths: set[str] = set()
        for c in commits:
            if len(c.parents) > 1:
                continue
            rule = self.bot_rule(c.author_name, c.author_email)
            if rule is not None:
                bots[rule] += 1
            for ch in c.changes:
                g = self.generated_rule(ch.path)
                if g is not None:
                    gen[g] += 1
                    gen_paths.add(ch.path)
        return {"bot_commits_by_pattern": dict(sorted(bots.items())), "bot_commits": sum(bots.values()),
                "bot_filter_applied": self.spec.exclude_bots_from_patterns,
                "generated_changes_by_rule": dict(sorted(gen.items())), "generated_paths": len(gen_paths),
                "generated_filter_applied": self.spec.exclude_generated_from_patterns}

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
