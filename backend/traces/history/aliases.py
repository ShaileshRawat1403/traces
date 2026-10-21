"""Alias suggestions for semantic renames (docs/contracts/history.md sections 6.1, 8.8, 12, 17; D-H4; HT13, HT24).

Git records a delete plus an add when content moves with too many edits, or when several files merge into one
(Lab C: `crud/*.py` became `crud.py` in 2d0f774, #622, and `git log --follow` stops there). Within one non-merge
commit, each deleted text file is compared with each added text file by normalized line-set overlap. A pair whose
containment (share of the deleted file's distinct lines found in the added file) reaches `alias_min_similarity`
is a candidate; each deleted file keeps its best candidate (highest containment, then Jaccard, then path bytes)
and becomes an `alias_of` suggestion: class history_inferred, status unvalidated, no check that could promote it.
A reviewer annotates it through `set_review_state`, which never changes status, label, class or claim_id (D-H4).

v1 scope: same-commit pairs only, file granularity only (component aliases need component maps at old SHAs).
"""

from __future__ import annotations

import datetime as _dt
from collections import Counter
from collections.abc import Mapping
from typing import Any

from .errors import E_CONFIG, HistoryError
from .filters import Filters
from .ingest import ls_tree_paths, open_runner
from .lifecycle import identities
from .model import Change, HistoryLog
from .records import RunContext, citation, ep_file, finalize, make_record
from .shapes import ComponentMap, HistoryResult, Record, default_context

MIN_LINE_CHARS = 4             # normalized lines shorter than this carry no signal ("}", "pass")
MIN_LINES = 3                  # both sides need this many distinct normalized lines
MAX_PAIRS_PER_COMMIT = 400     # delete x add pairs compared per commit; larger commits are skipped and counted
REVIEW_STATES = ("none", "confirmed", "disputed")
UNVALIDATED_REASON = "suggestion from content similarity; identity not established by Git"


def normalized_lines(data: bytes) -> frozenset[str]:
    """Distinct lines after stripping surrounding whitespace and collapsing inner runs; short lines dropped."""
    out = set()
    for raw in data.decode("utf-8", "replace").splitlines():
        s = " ".join(raw.split())
        if len(s) >= MIN_LINE_CHARS:
            out.add(s)
    return frozenset(out)


def overlap(a: frozenset[str], b: frozenset[str]) -> dict[str, Any]:
    inter = len(a & b)
    union = len(a | b)
    return {"line_containment": round(inter / len(a), 4) if a else 0.0,
            "line_set_jaccard": round(inter / union, 4) if union else 0.0,
            "lines_moved": inter, "lines_from": len(a), "lines_to": len(b),
            "method": "normalized line-set overlap"}


def _text_change(ch: Change) -> bool:
    return not ch.binary and not ch.non_utf8 and ch.mode_before != "120000" and ch.mode_after != "120000"


def alias_suggestions(log: HistoryLog, *, components: ComponentMap | None = None,
                      ctx: RunContext | None = None) -> HistoryResult:
    ctx = ctx or default_context(log.repo.repo, log.repo.sha)
    t = log.config.thresholds
    if not 0 < t.alias_min_similarity <= 1:
        raise HistoryError(E_CONFIG, "alias_min_similarity must be in (0, 1]", "aliases")
    flt = Filters(log.config.filters)
    spec = log.config.filters
    max_blob = log.config.limits.max_blob_bytes
    skipped: Counter[str] = Counter()
    plan: list[tuple[Any, list[Change], list[Change]]] = []
    for c in log.commits:
        if c.is_merge:
            continue
        dels = [ch for ch in c.changes if ch.status == "D" and ch.blob_before and _text_change(ch)]
        adds = [ch for ch in c.changes if ch.status == "A" and ch.blob_after and _text_change(ch)]
        if spec.exclude_generated_from_patterns:
            dels = [ch for ch in dels if not flt.is_generated(ch.path)]
            adds = [ch for ch in adds if not flt.is_generated(ch.path)]
        if not dels or not adds:
            continue
        if len(dels) * len(adds) > MAX_PAIRS_PER_COMMIT:
            skipped["pairs_over_cap"] += 1
            continue
        plan.append((c, dels, adds))
    params = {"alias_min_similarity": t.alias_min_similarity, "min_line_chars": MIN_LINE_CHARS,
              "min_lines": MIN_LINES, "max_pairs_per_commit": MAX_PAIRS_PER_COMMIT, "scope": "same commit",
              "measure": "containment = |lines(from) & lines(to)| / |lines(from)| over normalized distinct lines",
              "filters": flt.criteria(), "rename_threshold": t.rename_threshold}
    out: list[Record] = []
    with open_runner(log.repo, log.config) as runner:
        ids = identities(log, set(ls_tree_paths(runner, log.repo.sha)))
        oids = sorted({ch.blob_before for _, d, _ in plan for ch in d if ch.blob_before}
                      | {ch.blob_after for _, _, a in plan for ch in a if ch.blob_after})
        sizes: dict[str, int] = {}
        if oids:
            res = runner.run("cat-file", ["--batch-check=%(objectname) %(objecttype) %(objectsize)", "-Z"],
                             stdin=b"".join(o.encode() + b"\0" for o in oids))
            for ent in res.split(b"\0"):
                parts = ent.split()
                if len(parts) == 3 and parts[1] == b"blob":
                    sizes[parts[0].decode()] = int(parts[2])
        lines: dict[str, frozenset[str]] = {}
        want = [o for o in oids if 0 <= sizes.get(o, -1) <= max_blob]
        skipped["blob_over_max_bytes"] += sum(1 for o in oids if sizes.get(o, 0) > max_blob)
        for i in range(0, len(want), 500):
            chunk = want[i:i + 500]
            data = runner.run("cat-file", ["--batch", "-Z"], stdin=b"".join(o.encode() + b"\0" for o in chunk))
            pos = 0
            for o in chunk:
                j = data.index(b"\0", pos)
                head = data[pos:j].split()
                if len(head) != 3 or head[1] != b"blob":
                    pos = j + 1
                    continue
                n = int(head[2])
                lines[o] = normalized_lines(data[j + 1:j + 1 + n])
                pos = j + 1 + n + 1
    for c, dels, adds in plan:
        bot = flt.is_bot(c.author_name, c.author_email)
        for d in sorted(dels, key=lambda x: x.path.encode()):
            a_lines = lines.get(d.blob_before or "")
            if a_lines is None or len(a_lines) < MIN_LINES:
                continue
            best: tuple[Change, dict[str, Any]] | None = None
            for ad in sorted(adds, key=lambda x: x.path.encode()):
                b_lines = lines.get(ad.blob_after or "")
                if b_lines is None or len(b_lines) < MIN_LINES:
                    continue
                m = overlap(a_lines, b_lines)
                if m["line_containment"] < t.alias_min_similarity or m["lines_moved"] < MIN_LINES:
                    continue
                if best is None or (m["line_containment"], m["line_set_jaccard"]) > \
                        (best[1]["line_containment"], best[1]["line_set_jaccard"]):
                    best = (ad, m)  # ties keep the earlier path in byte order
            if best is not None:
                ad, m = best
                pct = round(m["line_containment"] * 100)
                flags = ["bot_commit"] if bot else []
                out.append(make_record(
                    ctx, claim_kind="relationship", kind="alias_of", granularity="file", frm=ep_file(d.path),
                    to=ep_file(ad.path),
                    statement=(f"Suggested alias: content of {d.path} appears to continue in {ad.path} after commit "
                               f"{c.sha[:7]} ({pct}% of its distinct lines). Git recorded a delete and an add, "
                               f"not a rename."),
                    cls="history_inferred", provenance="history:alias-suggest",
                    provenance_raw={"commit": c.sha, "head_to": ids.head_path(c.sha, ad.path)},
                    origin={"kind": "history_derived", "derived_from": [c.sha]}, qualifier=None,
                    citations=[citation(c, [d, ad])], anchor={"commit": c.sha}, params=params,
                    max_status="unvalidated", metrics=m, flags=flags, unvalidated_reason=UNVALIDATED_REASON))
    recs = finalize(out)
    report = {"stage": "aliases", "records": len(recs), "commits_compared": len(plan),
              "skipped": dict(skipped), "parameters": params,
              "components": "deferred: component aliases need component maps at old SHAs" if components else None,
              "wording": "suggested, not confirmed; label stays inferred"}
    return HistoryResult(recs, report)


def set_review_state(record: Mapping[str, Any], state: str, *, reviewer: str | None, at: str | None,
                     note: str | None = None) -> dict[str, Any]:
    """Return a copy of `record` with review_state set (D-H4). Status, label, class, claim_id and status_history are
    untouched; `confirmed` or `disputed` needs a reviewer and an ISO 8601 time with offset."""
    if state not in REVIEW_STATES:
        raise HistoryError(E_CONFIG, f"review state must be one of {REVIEW_STATES}", "review")
    if state == "none":
        rs: dict[str, Any] = {"state": "none", "reviewer": None, "at": None}
    else:
        if not reviewer or not at:
            raise HistoryError(E_CONFIG, "confirmed or disputed needs reviewer and at", "review")
        try:
            when = _dt.datetime.fromisoformat(at)
        except ValueError as e:
            raise HistoryError(E_CONFIG, "review time must be ISO 8601", "review") from e
        if when.tzinfo is None:
            raise HistoryError(E_CONFIG, "review time needs a UTC offset", "review")
        rs = {"state": state, "reviewer": reviewer, "at": at}
    if note:
        rs["note"] = note
    out = dict(record)
    out["review_state"] = rs
    return out


def review_wording(record: Mapping[str, Any]) -> str:
    """User-facing wording rule of section 17."""
    rs = record.get("review_state") or {}
    st = rs.get("state", "none")
    if st == "confirmed":
        return f"confirmed by {rs.get('reviewer')}"
    if st == "disputed":
        return f"disputed by {rs.get('reviewer')}"
    return "suggested, not confirmed"
