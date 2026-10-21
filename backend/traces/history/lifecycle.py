"""File lifecycles, rename-aware identities and bulk moves (contract section 9.2, decision D-H5).

- Replay: the file set along the first-parent chain (merges diffed against their first parent) must equal
  `git ls-tree -r` at the pinned SHA, else E_REPLAY.
- Identities: every non-merge change is attributed to the HEAD path it became, walking commits newest to oldest and
  following renames backwards. Copies start a new identity. A path reused after a delete is a new identity.
- Bulk moves: renames in one commit grouped by common-suffix stripping into old_prefix -> new_prefix.
"""

from __future__ import annotations

import datetime as _dt
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .errors import E_REPLAY, HistoryError
from .ingest import ls_tree_paths, open_runner, parse_raw
from .model import Change, Commit, HistoryLog
from .records import RunContext, citation, ep_commit, ep_component, ep_path, finalize, make_record
from .shapes import ComponentMap, HistoryResult, Record, default_context, validate_component_map

DIR_DEPTH = 3


@dataclass(frozen=True)
class Identities:
    """attribution[(commit sha, path after change)] = HEAD path or None (identity does not survive)."""

    attribution: Mapping[tuple[str, str], str | None]
    alive: frozenset[str]

    def head_path(self, sha: str, path: str) -> str | None:
        return self.attribution.get((sha, path))


def replay(log: HistoryLog, head_files: list[str]) -> dict[str, Any]:
    by = log.by_sha
    files: set[str] = set()

    def apply(changes: tuple[Change, ...]) -> None:
        for ch in changes:
            if ch.status in "AC":
                files.add(ch.path)
            elif ch.status == "D":
                files.discard(ch.path)
            elif ch.status == "R":
                files.discard(ch.old_path or "")
                files.add(ch.path)

    for s in log.first_parent:
        c = by[s]
        apply(log.merge_fp_diffs.get(s, ()) if c.is_merge else c.changes)
    head = set(head_files)
    check = {"replayed_files": len(files), "ls_tree_files": len(head),
             "missing_in_replay": sorted(head - files)[:20], "extra_in_replay": sorted(files - head)[:20],
             "method": "first-parent replay, merges diffed against first parent, compared with ls-tree -r"}
    if files != head:
        raise HistoryError(E_REPLAY, f"replay {len(files)} files differs from ls-tree {len(head)}", "lifecycle")
    return check


def identities(log: HistoryLog, alive: set[str] | frozenset[str]) -> Identities:
    mapping: dict[str, str] = {p: p for p in alive}
    attr: dict[tuple[str, str], str | None] = {}
    for c in reversed(log.commits):
        if c.is_merge:
            continue
        # Process deletes/modifies before adds within a commit is irrelevant: one change per path per commit.
        renames = [ch for ch in c.changes if ch.status == "R"]
        others = [ch for ch in c.changes if ch.status != "R"]
        for ch in others:
            if ch.status in "AC":
                attr[(c.sha, ch.path)] = mapping.pop(ch.path, None)
            elif ch.status == "D":
                attr[(c.sha, ch.path)] = None
            else:
                attr[(c.sha, ch.path)] = mapping.get(ch.path)
        moved: dict[str, str] = {}
        for ch in renames:
            hp = mapping.pop(ch.path, None)
            attr[(c.sha, ch.path)] = hp
            if hp is not None and ch.old_path is not None:
                moved[ch.old_path] = hp
        mapping.update(moved)
    return Identities(attr, frozenset(alive))


def _dirs(path: str) -> set[str]:
    parts = path.split("/")[:-1]
    return {"/".join(parts[:i]) for i in range(1, min(len(parts), DIR_DEPTH) + 1)}


def _common_move(old: str, new: str) -> tuple[str, str]:
    o, n = old.split("/"), new.split("/")
    while o and n and o[-1] == n[-1]:
        o.pop()
        n.pop()
    return "/".join(o) or ".", "/".join(n) or "."


def dir_events(log: HistoryLog) -> list[dict[str, Any]]:
    """Directory births and deaths (depth <= 3) along the first-parent chain. Report data for milestone selection."""
    by = log.by_sha
    count: Counter[str] = Counter()
    events = []
    for s in log.first_parent:
        c = by[s]
        before = {d for d, k in count.items() if k > 0}
        for ch in log.merge_fp_diffs.get(s, ()) if c.is_merge else c.changes:
            if ch.status in "AC":
                count.update(_dirs(ch.path))
            elif ch.status == "D":
                count.subtract(_dirs(ch.path))
            elif ch.status == "R":
                count.subtract(_dirs(ch.old_path or ""))
                count.update(_dirs(ch.path))
        after = {d for d, k in count.items() if k > 0}
        born, died = sorted(after - before), sorted(before - after)
        if born or died:
            events.append({"commit": s, "dirs_added": born, "dirs_removed": died})
    return events


def _bulk_groups(changes: tuple[Change, ...] | list[Change], min_files: int) -> dict[tuple[str, str], list[Change]]:
    grp: dict[tuple[str, str], list[Change]] = defaultdict(list)
    for ch in changes:
        if ch.status == "R" and ch.old_path is not None:
            grp[_common_move(ch.old_path, ch.path)].append(ch)
    return {k: v for k, v in grp.items() if len(v) >= min_files}


def lifecycle(log: HistoryLog, *, components: ComponentMap | None = None, ctx: RunContext | None = None) -> HistoryResult:
    ctx = ctx or default_context(log.repo.repo, log.repo.sha)
    t = log.config.thresholds
    with open_runner(log.repo, log.config) as runner:
        head_files = ls_tree_paths(runner, log.repo.sha)
        check = replay(log, head_files)
        ids = identities(log, set(head_files))
        out: list[Record] = []
        params = {**log.ingest_parameters(), "bulk_move_min_files": t.bulk_move_min_files}
        for c in log.commits:
            if c.is_merge:
                continue
            for (op, np_), chs in sorted(_bulk_groups(c.changes, t.bulk_move_min_files).items()):
                chk = None
                if log.config.verify and c.parents:
                    raw = runner.run("diff-tree", ["-z", "-r", "--raw", "--no-abbrev", f"-M{t.rename_threshold}%",
                                                   f"-C{t.copy_threshold}%", f"-l{t.rename_limit}", c.parents[0], c.sha])
                    re_ch, _ = parse_raw(raw.split(b"\0"), 0)
                    n2 = len(_bulk_groups(re_ch, 1).get((op, np_), []))
                    ok = n2 == len(chs)
                    chk = {"method": "git_recount", "establishes": "presence", "result": "pass" if ok else "inconclusive",
                           "detail": f"diff-tree {c.parents[0][:12]}..{c.sha[:12]} recount: {n2} renames {op} -> {np_}"}
                out.append(make_record(
                    ctx, claim_kind="relationship", kind="prefix_moved", granularity="path", frm=ep_path(op),
                    to=ep_path(np_), statement=f"Commit {c.sha[:12]} moved {len(chs)} files from {op}/ to {np_}/.",
                    cls="history_pattern", provenance="history:lifecycle",
                    provenance_raw={"rule": "common-suffix stripping of rename pairs", "files": len(chs)},
                    origin={"kind": "history_derived", "derived_from": [c.sha]},
                    qualifier=f"grouped renames, {len(chs)} files", citations=[citation(c, chs)],
                    anchor={"commit": c.sha}, params=params, max_status="observed",
                    metrics={"files": len(chs)}, check=chk))
        if components is not None:
            out += _component_records(log, ids, validate_component_map(components, log.repo.sha, "lifecycle"), ctx, params)
    recs = finalize(out)
    report = {"stage": "lifecycle", "replay_check": check, "records": len(recs), "bulk_moves": len(recs),
              "dir_events": dir_events(log), "parameters": params,
              "components": "used" if components else "component map not supplied: component lifecycles skipped",
              "identity_rule": "newest-to-oldest walk over non-merge commits; renames carry identity, copies start a new one"}
    if components is not None:
        report["bulk_moves"] = sum(1 for r in recs if r.get("relationship_kind") == "prefix_moved")
    return HistoryResult(recs, report)


def _component_records(log: HistoryLog, ids: Identities, cmap: ComponentMap, ctx: RunContext,
                       params: Mapping[str, Any]) -> list[Record]:
    first: dict[str, tuple[Commit, Change]] = {}
    for c in log.commits:
        if c.is_merge:
            continue
        for ch in c.changes:
            hp = ids.head_path(c.sha, ch.path)
            if hp is None:
                continue
            cid = cmap.component_of(hp)
            if cid is not None and cid not in first:
                first[cid] = (c, ch)
    out = []
    p = {**params, "component_map_digest": cmap.digest, "component_map_sha": cmap.sha}
    for cid, (c, ch) in sorted(first.items()):
        out.append(make_record(
            ctx, claim_kind="relationship", kind="component_added", granularity="component", frm=ep_commit(c.sha),
            to=ep_component(cid), statement=f"Component {cid} has its earliest tracked file change in commit {c.sha[:12]} ({_dt.datetime.fromtimestamp(c.committer_time, _dt.UTC).date()}).",
            cls="history_inferred", provenance="history:lifecycle", provenance_raw={"first_path": ch.path},
            origin={"kind": "history_derived", "derived_from": [c.sha]}, qualifier=None, citations=[citation(c, [ch])],
            anchor={"commit": c.sha}, params=p, max_status="unvalidated",
            unvalidated_reason="component identity is carried back through rename chains; not established by Git"))
    return out
