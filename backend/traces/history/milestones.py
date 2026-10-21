"""Milestones, tree-level snapshot compare and evidence-set diff (contract sections 8.3, 9.7, 9.8; D-H9).

History selects milestone SHAs on the first-parent chain and hands them to the index worker (hook H3). The worker
runs the Evidence pipeline at each SHA and passes the EvidenceSets back. History never parses source: the
snapshot compare reads trees only, and the evidence-set diff compares records it is given.
"""

from __future__ import annotations

import datetime as _dt
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from traces.evidence.types import EvidenceSet

from .config import MAX_MILESTONES_DEFAULT, MAX_MILESTONES_ON_DEMAND, canon, digest
from .errors import E_CONFIG, E_EVIDENCE_SET, E_SHA, HistoryError
from .filters import Filters
from .gitcmd import SHA_RE
from .ingest import _diff_args, ls_tree_paths, open_runner, parse_raw
from .interface import Milestone
from .lifecycle import _bulk_groups, _dirs
from .manifests import manifest_events
from .model import Commit, HistoryLog, encode_path
from .records import RunContext, citation, ep_commit, ep_file, finalize, make_record
from .reverts import find_reverts
from .shapes import ComponentMap, HistoryResult, Record, default_context
from .verify import read_commit_parents, resolve_blobs

SCHEMA_04 = "traces-evidence/0.4"
STATUS_RANK = {"rejected": 0, "missing_location": 1, "unvalidated": 2, "observed": 3, "verified": 4}
TOP_DIR_DEPTH = 1


def _check_cap(max_milestones: int) -> None:
    if not isinstance(max_milestones, int) or max_milestones < 2 or max_milestones > MAX_MILESTONES_ON_DEMAND:
        raise HistoryError(E_CONFIG, f"max_milestones must be between 2 and {MAX_MILESTONES_ON_DEMAND} (D-H9)",
                           "milestones")


def fp_owner(log: HistoryLog) -> dict[str, str]:
    """Map every commit to the earliest first-parent commit that contains it (side-branch commits map to the merge
    that brought them in)."""
    by = log.by_sha
    owner: dict[str, str] = {}
    for s in log.first_parent:
        stack = [s]
        while stack:
            x = stack.pop()
            if x in owner:
                continue
            owner[x] = s
            stack.extend(p for p in by[x].parents if p not in owner and p in by)
    return owner


def _year(ts: int) -> int:
    return _dt.datetime.fromtimestamp(ts, _dt.UTC).year


def milestone_candidates(log: HistoryLog) -> dict[str, list[str]]:
    by = log.by_sha
    flt = Filters(log.config.filters)
    fp = list(log.first_parent)
    owner = fp_owner(log)
    t = log.config.thresholds
    reasons: dict[str, list[str]] = {s: [] for s in fp}
    dep_only: set[str] = set()

    def add(s: str, r: str) -> None:
        if r not in reasons[s]:
            reasons[s].append(r)

    def changes_of(c: Commit) -> Sequence[Any]:
        return log.merge_fp_diffs.get(c.sha, ()) if c.is_merge else c.changes

    count: Counter[str] = Counter()
    for s in fp:
        c = by[s]
        chs = changes_of(c)
        for (op, np_), g in sorted(_bulk_groups(tuple(chs), t.bulk_move_min_files).items()):
            add(s, f"bulk move {len(g)} files: {op} -> {np_}")
        before = {d for d, k in count.items() if k > 0}
        for ch in chs:
            if ch.status in "AC":
                count.update(_dirs(ch.path))
            elif ch.status == "D":
                count.subtract(_dirs(ch.path))
            elif ch.status == "R":
                count.subtract(_dirs(ch.old_path or ""))
                count.update(_dirs(ch.path))
        after = {d for d, k in count.items() if k > 0}
        top = lambda ds: sorted(d for d in ds if d.count("/") < TOP_DIR_DEPTH)  # noqa: E731
        born, died = top(after - before), top(before - after)
        if born:
            add(s, "top-level directories added: " + ", ".join(f"{d}/" for d in born[:5]))
        if died:
            add(s, "top-level directories removed: " + ", ".join(f"{d}/" for d in died[:5]))
    events, _ = manifest_events(log)
    dep: dict[str, list[str]] = {}
    for e in events:
        if e.kind in ("dependency_added", "dependency_removed"):
            dep.setdefault(owner[e.commit], []).append(("+" if e.kind == "dependency_added" else "-") + e.name)
    for s, names in dep.items():
        uniq = sorted(set(names))
        add(s, "dependency change: " + ", ".join(uniq[:5]) + (f" (+{len(uniq) - 5} more)" if len(uniq) > 5 else ""))
        dep_only.add(s)
    revs, _ = find_reverts(log)
    for r in revs:
        add(owner[r["commit"]], f"explicit revert of {r['target'][:12]}")
    last_of_year: dict[int, str] = {}
    for s in fp:
        last_of_year[_year(by[s].committer_time)] = s
    for y, s in last_of_year.items():
        add(s, f"last first-parent commit of {y}")
    # bot-authored commits are candidates only for dependency changes
    for s in fp:
        c = by[s]
        if flt.is_bot(c.author_name, c.author_email) and reasons[s]:
            reasons[s] = [r for r in reasons[s] if r.startswith("dependency change")] if s in dep_only else []
    add(fp[0], "first commit")
    add(log.repo.sha, "pinned commit")
    return {s: r for s, r in reasons.items() if r}


def select_milestones(log: HistoryLog, *, max_milestones: int = MAX_MILESTONES_DEFAULT,
                      components: ComponentMap | None = None) -> Sequence[Milestone]:
    """Up to `max_milestones` first-parent commits (default 8, hard cap 20 on demand, D-H9), always including the
    first commit and the pinned commit, ranked by number of distinct reasons then commit time, returned oldest
    first. `components` is accepted for the hook signature; v1 does not use it for ranking."""
    _check_cap(max_milestones)
    by = log.by_sha
    cands = milestone_candidates(log)
    fixed = [log.first_parent[0], log.repo.sha]
    rest = sorted((s for s in cands if s not in fixed),
                  key=lambda s: (-len(cands[s]), by[s].committer_time, s))
    chosen = set(fixed) | set(rest[: max_milestones - len(set(fixed))])
    order = {s: i for i, s in enumerate(log.first_parent)}
    return tuple(Milestone(s, tuple(cands[s])) for s in sorted(chosen, key=lambda s: order[s]))


def milestone_records(log: HistoryLog, milestones: Sequence[Milestone], *, max_milestones: int = MAX_MILESTONES_DEFAULT,
                      ctx: RunContext | None = None) -> HistoryResult:
    """Milestone nodes (history_pattern). Observed after a git_object_check: the commit object exists and lies on
    the first-parent chain of the pinned SHA, walked through raw commit objects (cat-file), not rev-list."""
    _check_cap(max_milestones)
    ctx = ctx or default_context(log.repo.repo, log.repo.sha)
    by = log.by_sha
    chain: set[str] = set()
    if log.config.verify:
        with open_runner(log.repo, log.config) as runner:
            parents = read_commit_parents(runner, [c.sha for c in log.commits])
        x: str | None = log.repo.sha
        while x is not None and x not in chain:
            chain.add(x)
            ps = parents.get(x)
            x = ps[0] if ps else None
    params = {**log.ingest_parameters(), "max_milestones": max_milestones,
              "criteria": ["first commit", "pinned commit", "bulk moves", "top-level directory births and deaths",
                           "dependency add or remove", "explicit reverts", "last first-parent commit of each UTC year"],
              "ranking": "distinct reasons, then commit time; first and pinned always kept",
              "bot_rule": "bot-authored commits only for dependency changes", "chain": "first-parent"}
    out: list[Record] = []
    for rank, m in enumerate(milestones):
        c = by[m.sha]
        chk = None
        if log.config.verify:
            ok = m.sha in chain
            chk = {"method": "git_object_check", "establishes": "presence", "result": "pass" if ok else "fail",
                   "detail": "commit object read with cat-file and found on the first-parent chain of the pinned SHA"
                   if ok else "not on the first-parent chain walked from the pinned SHA"}
        out.append(make_record(
            ctx, claim_kind="node", kind="milestone", granularity="commit", frm=ep_commit(m.sha), to=None,
            statement=f"Commit {m.sha[:12]} ({c.subject[:80]}) is a selected milestone: {'; '.join(m.reasons)}.",
            cls="history_pattern", provenance="history:milestone", provenance_raw={"reasons": list(m.reasons)},
            origin={"kind": "history_derived", "derived_from": [m.sha]},
            qualifier=f"selected milestone: {'; '.join(m.reasons)}", citations=[citation(c)],
            anchor={"range": [None, log.repo.sha], "first_parent": True}, params=params, max_status="observed",
            metrics={"reasons": len(m.reasons), "position": rank}, check=chk))
    recs = finalize(out)
    return HistoryResult(recs, {"stage": "milestones", "records": len(recs), "parameters": params,
                                "milestones": [{"sha": m.sha, "reasons": list(m.reasons)} for m in milestones]})


def _known(log: HistoryLog, sha: object, what: str) -> str:
    if not isinstance(sha, str) or not SHA_RE.match(sha) or sha not in log.by_sha:
        raise HistoryError(E_SHA, f"{what} is not a full SHA in this history", "snapshot")
    return sha


def snapshot_compare(log: HistoryLog, base: str, head: str, *, components: ComponentMap | None = None,
                     ctx: RunContext | None = None) -> HistoryResult:
    """Tree-level compare: files added and removed between two commits (renames between them are reported, not
    counted as add plus remove). No parsing. Each record is observed after an independent tree lookup."""
    _known(log, base, "base")
    _known(log, head, "head")
    ctx = ctx or default_context(log.repo.repo, log.repo.sha)
    by = log.by_sha
    with open_runner(log.repo, log.config) as runner:
        raw = runner.run("diff-tree", ["-z", "-r", "--raw", "--no-abbrev", *_diff_args(log.config, copies=False),
                                       base, head])
        changes, _ = parse_raw(raw.split(b"\0"), 0)
        base_n = len(ls_tree_paths(runner, base))
        head_n = len(ls_tree_paths(runner, head))
        items = [(sha, encode_path(ch.path, ch.non_utf8)) for ch in changes if ch.status in "AD" for sha in (base, head)]
        blobs = resolve_blobs(runner, items) if log.config.verify else {}
    params = {**log.ingest_parameters(), "base": base, "head": head, "level": "file",
              "rename_mapping": "diff-tree -M between base and head"}
    out: list[Record] = []
    renamed = [(ch.old_path, ch.path) for ch in changes if ch.status == "R"]
    for ch in changes:
        if ch.status not in "AD":
            continue
        added = ch.status == "A"
        present, absent = (head, base) if added else (base, head)
        chk = None
        if log.config.verify:
            p = encode_path(ch.path, ch.non_utf8)
            ok = blobs.get((present, p)) is not None and blobs.get((absent, p)) is None
            chk = {"method": "git_object_check", "establishes": "presence", "result": "pass" if ok else "fail",
                   "detail": f"cat-file tree lookup: present at {present[:12]}, absent at {absent[:12]}"
                   if ok else "tree lookup does not reproduce the difference"}
        out.append(make_record(
            ctx, claim_kind="relationship", kind="snapshot_added" if added else "snapshot_removed", granularity="file",
            frm=ep_commit(base), to=ep_file(ch.path),
            statement=f"{ch.path} is present at {present[:12]} and absent at {absent[:12]} (tree compare).",
            cls="snapshot_diff", provenance="git:diff-tree", provenance_raw={"status": ch.status},
            origin={"kind": "git_object", "commit": head, "paths": [ch.path]},
            qualifier=f"present at {present[:12]}, absent at {absent[:12]}",
            citations=[citation(by[base]), citation(by[head])], anchor={"range": [base, head], "first_parent": False},
            params=params, max_status="observed", flags=["non_utf8_path"] if ch.non_utf8 else [], check=chk))
    recs = finalize(out)
    report = {"stage": "snapshot_compare", "base": base, "head": head, "files_at_base": base_n,
              "files_at_head": head_n, "added": sum(1 for c in changes if c.status == "A"),
              "removed": sum(1 for c in changes if c.status == "D"), "renamed": len(renamed),
              "modified": sum(1 for c in changes if c.status in "MT"), "records": len(recs), "parameters": params,
              "components": "component-level snapshot compare is deferred in v1" if components else "not requested"}
    return HistoryResult(recs, report)


# ---- evidence-set diff ------------------------------------------------------------------------------------------

def _check_set(es: EvidenceSet, log: HistoryLog, what: str) -> None:
    if es.schema_version != SCHEMA_04:
        raise HistoryError(E_EVIDENCE_SET, f"{what} evidence set is {es.schema_version}, not {SCHEMA_04}", "evidence_diff")
    if es.sha not in log.by_sha:
        raise HistoryError(E_EVIDENCE_SET, f"{what} evidence set SHA is not in this history", "evidence_diff")
    if es.repo != log.repo.repo:
        raise HistoryError(E_EVIDENCE_SET, f"{what} evidence set is for another repo", "evidence_diff")
    for r in es.records:
        if r.get("repo_sha") != es.sha or r.get("schema_version") != SCHEMA_04:
            raise HistoryError(E_EVIDENCE_SET, f"{what} evidence set has a record for another SHA or schema",
                               "evidence_diff")


def _map_endpoint(ep: Mapping[str, Any] | None, pmap: Mapping[str, str]) -> dict[str, Any] | None:
    if ep is None:
        return None
    out = {k: ep[k] for k in ("entity", "symbol", "file") if k in ep}  # line numbers never take part in matching
    f = out.get("file")
    if isinstance(f, str) and f in pmap:
        nf = pmap[f]
        sym = out["symbol"]
        for pre in (f"{f}::", f"file::{f}"):
            if sym.startswith(pre):
                out["symbol"] = pre.replace(f, nf, 1) + sym[len(pre):]
                break
        out["file"] = nf
    return out


def _identity(rec: Mapping[str, Any], pmap: Mapping[str, str]) -> tuple[str, dict[str, Any]]:
    kind = rec.get("relationship_kind") or rec.get("node_kind")
    ident = {"claim_kind": rec["claim_kind"], "kind": kind, "granularity": rec["granularity"],
             "from": _map_endpoint(rec.get("from"), pmap), "to": _map_endpoint(rec.get("to"), pmap)}
    return canon({k: (v["symbol"] if isinstance(v, dict) else v) for k, v in ident.items()}), ident


def _index(es: EvidenceSet, pmap: Mapping[str, str]) -> tuple[dict[str, list[Mapping[str, Any]]], list[str]]:
    out: dict[str, list[Mapping[str, Any]]] = {}
    rejected: list[str] = []
    for r in es.records:
        if r.get("status") == "rejected":  # a rejected claim never counts as present architecture
            rejected.append(r["claim_id"])
            continue
        out.setdefault(_identity(r, pmap)[0], []).append(r)
    return out, rejected


def _recount(base_ids: Sequence[str], head_ids: Sequence[str]) -> tuple[list[str], list[str]]:
    """Second, independent pass: merge two sorted lists instead of dict lookups."""
    a, b = sorted(set(base_ids)), sorted(set(head_ids))
    i = j = 0
    only_a: list[str] = []
    only_b: list[str] = []
    while i < len(a) or j < len(b):
        if j >= len(b) or (i < len(a) and a[i] < b[j]):
            only_a.append(a[i])
            i += 1
        elif i >= len(a) or b[j] < a[i]:
            only_b.append(b[j])
            j += 1
        else:
            i += 1
            j += 1
    return only_a, only_b


def evidence_set_diff(base: EvidenceSet, head: EvidenceSet, *, log: HistoryLog,
                      aliases: Sequence[Mapping[str, Any]] = (), ctx: RunContext | None = None) -> HistoryResult:
    """snapshot_added / snapshot_removed between two Evidence seat outputs. Claims match by identity (claim_kind,
    kind, granularity, endpoint symbols) with base-side file paths mapped to head paths through Git renames between
    the two SHAs and through confirmed alias_of records. Line numbers are excluded, so a moved but unchanged claim
    gives no record. Rejected claims never count as present."""
    _check_set(base, log, "base")
    _check_set(head, log, "head")
    ctx = ctx or default_context(log.repo.repo, log.repo.sha)
    by = log.by_sha
    pmap: dict[str, str] = {}
    with open_runner(log.repo, log.config) as runner:
        raw = runner.run("diff-tree", ["-z", "-r", "--raw", "--no-abbrev", *_diff_args(log.config, copies=False),
                                       base.sha, head.sha])
    for ch in parse_raw(raw.split(b"\0"), 0)[0]:
        if ch.status == "R" and ch.old_path:
            pmap[ch.old_path] = ch.path
    confirmed = 0
    for a in aliases:
        if a.get("relationship_kind") == "alias_of" and (a.get("review_state") or {}).get("state") == "confirmed":
            f, t = (a.get("from") or {}).get("file"), (a.get("to") or {}).get("file")
            if f and t:
                pmap.setdefault(f, t)
                confirmed += 1
    bidx, brej = _index(base, pmap)
    hidx, hrej = _index(head, {})
    only_b_ids = sorted(set(bidx) - set(hidx))
    only_h_ids = sorted(set(hidx) - set(bidx))
    re_b, re_h = _recount(list(bidx), list(hidx))
    agree = (re_b, re_h) == (only_b_ids, only_h_ids)
    params_base = {"base": base.sha, "head": head.sha, "rename_mapping": "diff-tree -M base head",
                   "aliases": "confirmed alias_of only", "line_numbers": "excluded from matching",
                   "rejected": "never counted as present", "rename_threshold": log.config.thresholds.rename_threshold}
    out: list[Record] = []
    for added, ids, idx in ((False, only_b_ids, bidx), (True, only_h_ids, hidx)):
        present, absent = (head.sha, base.sha) if added else (base.sha, head.sha)
        for key in ids:
            under = idx[key]
            best = max(under, key=lambda r: (STATUS_RANK.get(r.get("status", ""), 0), r["claim_id"]))
            u_status = best.get("status")
            _, ident = _identity(best, pmap if not added else {})
            params = {**params_base, "underlying": {"claim_kind": ident["claim_kind"], "kind": ident["kind"],
                                                    "granularity": ident["granularity"]}}
            capped = "observed" if u_status in ("observed", "verified") else "unvalidated"
            chk = {"method": "git_recount", "establishes": "presence", "result": "pass" if agree else "fail",
                   "family": "text",
                   "detail": "set difference recomputed by an independent sorted merge of both evidence sets"}
            frm = ident["from"] or {"entity": "commit", "symbol": f"commit::{present}"}
            out.append(make_record(
                ctx, claim_kind="relationship", kind="snapshot_added" if added else "snapshot_removed",
                granularity=ident["granularity"], frm=frm, to=ident["to"],
                statement=f"The claim \"{best.get('statement', '')}\" is present at {present[:12]} and absent at "
                          f"{absent[:12]}.",
                cls="snapshot_diff", provenance="history:snapshot-diff",
                provenance_raw={"underlying_claim_ids": sorted(r["claim_id"] for r in under)},
                origin={"kind": "history_derived", "derived_from": sorted(r["claim_id"] for r in under)},
                qualifier=f"present at {present[:12]}, absent at {absent[:12]}",
                citations=sorted([citation(by[base.sha]), citation(by[head.sha])],
                                 key=lambda c: (by[c["commit"]].committer_time, c["commit"])),
                anchor={"range": [base.sha, head.sha], "first_parent": False}, params=params, max_status=capped,
                metrics={"underlying_status_a": u_status if not added else None,
                         "underlying_status_b": u_status if added else None},
                check=chk, unvalidated_reason=None if capped == "observed" else
                f"underlying claim is {u_status}; a snapshot difference is never stronger than its claim"))
    recs = finalize(out)
    report = {"stage": "evidence_set_diff", "base": base.sha, "head": head.sha, "records": len(recs),
              "added": len(only_h_ids), "removed": len(only_b_ids), "matched": len(set(bidx) & set(hidx)),
              "renames_mapped": len(pmap) - confirmed, "aliases_applied": confirmed,
              "rejected_ignored": {"base": len(brej), "head": len(hrej)}, "recount_agrees": agree,
              "parameters_digest": digest(params_base)}
    return HistoryResult(recs, report)


__all__ = ["evidence_set_diff", "fp_owner", "milestone_candidates", "milestone_records", "select_milestones",
           "snapshot_compare"]
