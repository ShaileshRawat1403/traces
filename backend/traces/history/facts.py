"""Commit facts: commit nodes and per-change relationships (contract section 6.1, class git_object_fact)."""

from __future__ import annotations

import datetime as _dt
from typing import Any

from .filters import Filters
from .ingest import open_runner
from .model import Change, Commit, HistoryLog, encode_path
from .records import RunContext, citation, ep_commit, ep_file, finalize, make_record
from .shapes import HistoryResult, Record, default_context
from .verify import read_commit_parents, resolve_blobs

KIND = {"A": "commit_adds", "D": "commit_deletes", "M": "commit_modifies", "T": "commit_type_changes",
        "R": "renamed_to", "C": "copied_to"}
VERB = {"A": "added", "D": "deleted", "M": "modified", "T": "changed the file type of"}


def _date(ts: int) -> str:
    return _dt.datetime.fromtimestamp(ts, _dt.UTC).strftime("%Y-%m-%d")


def _qualifier(ch: Change) -> str:
    if ch.status == "R":
        return "exact rename (identical blob)" if ch.similarity == 100 else f"similarity rename, score {ch.similarity}%"
    if ch.status == "C":
        return f"copy detected, score {ch.similarity}%"
    return "git tree change"


def _statement(c: Commit, ch: Change) -> str:
    s = c.sha[:12]
    if ch.status == "R":
        return f"Commit {s} renamed {ch.old_path} to {ch.path} (Git similarity {ch.similarity}%)."
    if ch.status == "C":
        return f"Commit {s} copied {ch.old_path} to {ch.path} (Git similarity {ch.similarity}%)."
    lines = "" if ch.added is None else (" (binary)" if ch.binary else f" (+{ch.added} -{ch.deleted})")
    return f"Commit {s} {VERB[ch.status]} {ch.path}{lines}."


def commit_facts(log: HistoryLog, *, ctx: RunContext | None = None) -> HistoryResult:
    ctx = ctx or default_context(log.repo.repo, log.repo.sha)
    flt = Filters(log.config.filters)
    params = log.ingest_parameters()
    verify = log.config.verify
    parents: dict[str, tuple[str, ...] | None] = {}
    blobs: dict[tuple[str, bytes], str | None] = {}
    if verify:
        with open_runner(log.repo, log.config) as runner:
            parents = read_commit_parents(runner, [c.sha for c in log.commits])
            items: list[tuple[str, bytes]] = []
            for c in log.commits:
                for ch in c.changes:
                    if ch.status != "D":
                        items.append((c.sha, encode_path(ch.path, ch.non_utf8)))
                    if c.parents:
                        items.append((c.parents[0], encode_path(ch.old_path or ch.path, ch.non_utf8)))
            blobs = resolve_blobs(runner, items)
    out: list[Record] = []
    for c in log.commits:
        bot = flt.is_bot(c.author_name, c.author_email)
        cflags = (["bot_commit"] if bot else []) + (["merge_commit"] if c.is_merge else []) + \
            (["rename_detection_limited"] if c.rename_limited else [])
        chk: dict[str, Any] | None = None
        if verify:
            ok = parents.get(c.sha) == c.parents
            chk = {"method": "git_object_check", "establishes": "presence", "result": "pass" if ok else "fail",
                   "detail": "cat-file commit object: type commit, parents match" if ok else "parents differ from commit object"}
        out.append(make_record(
            ctx, claim_kind="node", kind="commit", granularity="commit", frm=ep_commit(c.sha), to=None,
            statement=f"Commit {c.sha[:12]} ({_date(c.committer_time)}, {len(c.parents)} parent(s)).",
            cls="git_object_fact", provenance="git:log",
            provenance_raw={"subject": c.subject, "parents": list(c.parents), "author_time": c.author_time,
                            "committer_time": c.committer_time},
            origin={"kind": "git_object", "commit": c.sha, "paths": []}, qualifier="git commit object",
            citations=[citation(c)], anchor={"commit": c.sha}, params=params, max_status="observed",
            flags=cflags, check=chk))
        for ch in c.changes:
            kind = KIND[ch.status]
            flags = list(cflags)
            if ch.status == "R" and ch.similarity != 100:
                flags.append("similarity_rename")
            if flt.is_generated(ch.path):
                flags.append("generated_path")
            if ch.non_utf8:
                flags.append("non_utf8_path")
            if ch.status in "RC":
                frm, to = ep_file(ch.old_path or ""), ep_file(ch.path)
            else:
                frm, to = ep_commit(c.sha), ep_file(ch.path)
            chk = None
            if verify:
                after = blobs.get((c.sha, encode_path(ch.path, ch.non_utf8))) if ch.status != "D" else None
                before = blobs.get((c.parents[0], encode_path(ch.old_path or ch.path, ch.non_utf8))) if c.parents else None
                ok = after == ch.blob_after and before == ch.blob_before
                if ch.status == "R" and ch.similarity == 100:
                    ok = ok and ch.blob_before == ch.blob_after
                if ch.status == "A" and c.parents:
                    ok = ok and before is None
                chk = {"method": "git_object_check", "establishes": "presence", "result": "pass" if ok else "fail",
                       "detail": ("cat-file resolves the cited paths to the cited blobs in the commit and its first parent"
                                  if ok else "cited blobs do not match cat-file resolution")}
            out.append(make_record(
                ctx, claim_kind="relationship", kind=kind, granularity="file", frm=frm, to=to,
                statement=_statement(c, ch), cls="git_object_fact", provenance="git:diff-tree",
                provenance_raw={"status": ch.status, "similarity": ch.similarity, "added": ch.added,
                                "deleted": ch.deleted, "binary": ch.binary, "mode_before": ch.mode_before,
                                "mode_after": ch.mode_after},
                origin={"kind": "git_object", "commit": c.sha, "paths": sorted({ch.path, ch.old_path or ch.path})},
                qualifier=_qualifier(ch), citations=[citation(c, [ch])], anchor={"commit": c.sha},
                params=params, max_status="observed", flags=flags, check=chk))
    recs = finalize(out)
    report = {"stage": "commit_facts", "records": len(recs), "commits": len(log.commits),
              "observed": sum(1 for r in recs if r["status"] == "observed"),
              "unvalidated": sum(1 for r in recs if r["status"] == "unvalidated"),
              "parameters": params, "filters": flt.criteria(), "warnings": list(log.warnings)}
    return HistoryResult(recs, report)
