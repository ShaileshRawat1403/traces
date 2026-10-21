"""Explicit reverts and quick add-then-delete (contract sections 6.1 and 9.5).

Reverts: subject `Revert "<title>"` or body `This reverts commit <sha>`. The target is resolved to a full SHA in
the history (a full or uniquely abbreviated SHA from the body, else the most recent earlier commit whose subject
equals the quoted title). Records quote the message and stay history_inferred and unvalidated: that one commit
undoes another is not established in v1. Bot-authored commits are skipped by default (Lab C found a false revert
in a Dependabot body that quoted an upstream changelog).

Quick deletes: a path deleted within `quick_delete_days` of its add, following renames in between, over non-merge
commits, generated filter (and bot filter) applied. Records are history_pattern and may reach observed after an
independent git_recount: the path is absent before the add and present after it, present before the delete and
absent after it (tree lookups with cat-file), and the day count is recomputed from the raw commit objects.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping
from typing import Any

from .filters import Filters
from .ingest import open_runner
from .model import Change, Commit, HistoryLog, encode_path
from .records import RunContext, citation, ep_commit, ep_file, finalize, make_record
from .shapes import HistoryResult, Record, default_context
from .verify import read_objects, resolve_blobs

_SUBJECT = re.compile(r'^Revert "(.+)"\s*$')
_BODY = re.compile(r"This reverts commit ([0-9a-f]{7,40})\b")
DAY = 86_400


def _resolve_prefix(prefix: str, shas: list[str]) -> str | None:
    hits = [s for s in shas if s.startswith(prefix)]
    return hits[0] if len(hits) == 1 else None


def find_reverts(log: HistoryLog) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Structured revert matches (also used by milestone selection)."""
    flt = Filters(log.config.filters)
    order = [c.sha for c in log.commits]
    pos = {s: i for i, s in enumerate(order)}
    skipped: Counter[str] = Counter()
    unresolved: list[dict[str, str]] = []
    out: list[dict[str, Any]] = []
    for c in log.commits:
        m_sub = _SUBJECT.match(c.subject)
        m_body = _BODY.search(c.message)
        if not m_sub and not m_body:
            continue
        if log.config.filters.exclude_bots_from_patterns and flt.is_bot(c.author_name, c.author_email):
            skipped["bot"] += 1
            continue
        target: str | None = None
        how = ""
        quote = ""
        if m_body:
            quote = m_body.group(0)
            target = _resolve_prefix(m_body.group(1), order[:pos[c.sha]])
            how = "body sha"
        if target is None and m_sub:
            quote = quote or c.subject
            title = m_sub.group(1)
            for s in reversed(order[:pos[c.sha]]):
                if log.by_sha[s].subject == title:
                    target, how = s, "subject title"
                    break
        if target is None:
            unresolved.append({"commit": c.sha, "quote": quote})
            continue
        out.append({"commit": c.sha, "target": target, "match": how, "quote": quote})
    return out, {"skipped": dict(skipped), "unresolved": unresolved}


def reverts(log: HistoryLog, *, ctx: RunContext | None = None) -> HistoryResult:
    """Explicit reverts plus quick add-then-delete records."""
    ctx = ctx or default_context(log.repo.repo, log.repo.sha)
    flt = Filters(log.config.filters)
    by = log.by_sha
    matches, rrep = find_reverts(log)
    params = {**log.ingest_parameters(), "revert_patterns": [_SUBJECT.pattern, _BODY.pattern],
              "bot_commits_skipped": log.config.filters.exclude_bots_from_patterns, "filters": flt.criteria()}
    out: list[Record] = []
    for m in matches:
        c, t = by[m["commit"]], by[m["target"]]
        out.append(make_record(
            ctx, claim_kind="relationship", kind="reverts", granularity="commit", frm=ep_commit(c.sha),
            to=ep_commit(t.sha),
            statement=f'Commit {c.sha[:12]} message says: "{m["quote"]}". Suggested revert of {t.sha[:12]} '
                      f'("{t.subject}"); not established from the trees.',
            cls="history_inferred", provenance="history:revert-match",
            provenance_raw={"match": m["match"], "quote": m["quote"]},
            origin={"kind": "history_derived", "derived_from": sorted([c.sha, t.sha])}, qualifier=None,
            citations=sorted([citation(c), citation(t)], key=lambda x: (by[x["commit"]].committer_time, x["commit"])),
            anchor={"commit": c.sha}, params=params, max_status="unvalidated",
            flags=["bot_commit"] if flt.is_bot(c.author_name, c.author_email) else [],
            unvalidated_reason="message text is quoted; that one commit undoes another is not established in v1"))
    qd, qrep = _quick_deletes(log, flt, ctx)
    out += qd
    recs = finalize(out)
    report = {"stage": "reverts", "records": len(recs), "reverts": len(matches), **rrep,
              "quick_deletes": qrep, "parameters": params}
    return HistoryResult(recs, report)


def _quick_deletes(log: HistoryLog, flt: Filters, ctx: RunContext) -> tuple[list[Record], dict[str, Any]]:
    spec = log.config.filters
    window = log.config.thresholds.quick_delete_days
    live: dict[str, tuple[Commit, Change]] = {}
    found: list[tuple[Commit, Change, Commit, Change]] = []
    skipped: Counter[str] = Counter()
    for c in log.commits:
        if c.is_merge:
            continue
        if spec.exclude_bots_from_patterns and flt.is_bot(c.author_name, c.author_email):
            skipped["bot_commits"] += 1
            continue
        for ch in c.changes:
            if ch.status == "R" and ch.old_path in live:
                live[ch.path] = live.pop(ch.old_path)
            elif ch.status in ("A", "C"):
                live[ch.path] = (c, ch)
            elif ch.status == "D" and ch.path in live:
                ac, ach = live.pop(ch.path)
                if c.committer_time - ac.committer_time <= window * DAY and c.committer_time >= ac.committer_time:
                    if spec.exclude_generated_from_patterns and (flt.is_generated(ch.path) or flt.is_generated(ach.path)):
                        skipped["generated_paths"] += 1
                        continue
                    found.append((ac, ach, c, ch))
    checks: Mapping[tuple[str, str], tuple[bool, str]] = {}
    if log.config.verify and found:
        checks = _recount(log, found, window)
    params = {**log.ingest_parameters(), "quick_delete_days": window, "time": "committer time",
              "commits": "non-merge commits only", "filters": flt.criteria()}
    by_time = {c.sha: c.committer_time for c in log.commits}
    out: list[Record] = []
    for ac, ach, dc, dch in found:
        days = (dc.committer_time - ac.committer_time) / DAY
        d = int(days)
        chk = None
        if log.config.verify:
            ok, detail = checks[(dc.sha, dch.path)]
            chk = {"method": "git_recount", "establishes": "presence", "result": "pass" if ok else "fail",
                   "detail": detail}
        flags = []
        if flt.is_generated(dch.path):
            flags.append("generated_path")
        if dch.non_utf8 or ach.non_utf8:
            flags.append("non_utf8_path")
        out.append(make_record(
            ctx, claim_kind="relationship", kind="deleted_soon_after_add", granularity="file", frm=ep_file(ach.path),
            to=ep_file(dch.path),
            statement=f"{dch.path} was added in commit {ac.sha[:12]} and deleted in commit {dc.sha[:12]}, "
                      f"{d} days later. History pattern.",
            cls="history_pattern", provenance="history:lifecycle",
            provenance_raw={"added_in": ac.sha, "deleted_in": dc.sha, "added_path": ach.path, "deleted_path": dch.path},
            origin={"kind": "history_derived", "derived_from": sorted([ac.sha, dc.sha])},
            qualifier=f"deleted {d} days after add",
            citations=sorted([citation(ac, [ach]), citation(dc, [dch])], key=lambda x: (by_time[x["commit"]], x["commit"])),
            anchor={"range": [ac.sha, dc.sha], "first_parent": False}, params=params, max_status="observed",
            metrics={"days": round(days, 4)}, flags=flags, check=chk))
    return out, {"found": len(found), "skipped": dict(skipped), "window_days": window}


def _committer_time(raw: bytes | None) -> int | None:
    if raw is None:
        return None
    for line in raw.split(b"\n\n", 1)[0].split(b"\n"):
        if line.startswith(b"committer "):
            return int(line.rsplit(b" ", 2)[1])
    return None


def _recount(log: HistoryLog, found: list[tuple[Commit, Change, Commit, Change]], window: int) -> Mapping[tuple[str, str], tuple[bool, str]]:
    items: list[tuple[str, bytes]] = []
    for ac, ach, dc, dch in found:
        ap, dp = encode_path(ach.path, ach.non_utf8), encode_path(dch.path, dch.non_utf8)
        items.append((ac.sha, ap))
        if ac.parents:
            items.append((ac.parents[0], ap))
        items.append((dc.sha, dp))
        if dc.parents:
            items.append((dc.parents[0], dp))
    with open_runner(log.repo, log.config) as runner:
        blobs = resolve_blobs(runner, items)
        raws = read_objects(runner, sorted({c.sha.encode() for f in found for c in (f[0], f[2])}), want=b"commit")
    out = {}
    for ac, ach, dc, dch in found:
        ap, dp = encode_path(ach.path, ach.non_utf8), encode_path(dch.path, dch.non_utf8)
        added = blobs.get((ac.sha, ap)) is not None and (not ac.parents or blobs.get((ac.parents[0], ap)) is None)
        deleted = blobs.get((dc.sha, dp)) is None and bool(dc.parents) and blobs.get((dc.parents[0], dp)) is not None
        ta, td = _committer_time(raws.get(ac.sha.encode())), _committer_time(raws.get(dc.sha.encode()))
        in_window = ta is not None and td is not None and 0 <= td - ta <= window * DAY
        ok = added and deleted and in_window
        out[(dc.sha, dch.path)] = (ok, f"tree lookups: added {added}, deleted {deleted}; raw commit times "
                                       f"{'within' if in_window else 'outside'} {window} days")
    return out


__all__ = ["find_reverts", "reverts"]
