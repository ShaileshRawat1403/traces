"""Churn and hotspots (contract section 9.3, decision D-H1). Class history_pattern; the metric values may reach
observed after an independent `log --follow` recount; nothing here is ever verified. The hotspot complexity is an
indentation proxy and is labeled as one."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .filters import Filters
from .ingest import ls_tree_paths, open_runner
from .lifecycle import LINEAGE_FLAG, identities, lineage_breaks, lineage_caveat
from .model import Commit, HistoryLog, decode_path
from .records import RunContext, citation, ep_component, ep_file, finalize, make_record
from .shapes import ComponentMap, HistoryResult, Record, default_context, validate_component_map
from .verify import Recounter

JS_LIKE = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte", ".json", ".yml", ".yaml", ".html", ".css", ".scss")


@dataclass
class FileStats:
    revisions: set[str] = field(default_factory=set)
    revisions_small: set[str] = field(default_factory=set)
    added: int = 0
    deleted: int = 0
    authors: Counter[str] = field(default_factory=Counter)
    first: int | None = None
    last: int | None = None
    cites: dict[str, tuple[Commit, list[Any]]] = field(default_factory=dict)


def _params(log: HistoryLog, flt: Filters, metric_set: str, extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    t = log.config.thresholds
    p = {**log.ingest_parameters(), "metric_set": metric_set, "filters": flt.criteria(),
         "max_changeset_size": t.max_changeset_size, "rename_normalization": "head_paths",
         "commits": "non-merge commits only"}
    if extra:
        p.update(extra)
    return p


def collect(log: HistoryLog, flt: Filters, alive: set[str]) -> tuple[dict[str, FileStats], dict[str, int], dict[str, int]]:
    """Per HEAD path stats, skipped commit counts, and lineage breaks per HEAD path (D-H15)."""
    ids = identities(log, alive)
    spec = log.config.filters
    t = log.config.thresholds
    stats: dict[str, FileStats] = defaultdict(FileStats)
    skipped = Counter[str]()
    for c in log.commits:
        if c.is_merge:
            skipped["merge"] += 1
            continue
        if spec.exclude_bots_from_patterns and flt.is_bot(c.author_name, c.author_email):
            skipped["bot"] += 1
            continue
        size = sum(1 for ch in c.changes if not flt.is_generated(ch.path))
        small = size <= t.max_changeset_size
        who = f"{c.author_name} <{c.author_email}>"
        for ch in c.changes:
            hp = ids.head_path(c.sha, ch.path)
            if hp is None:
                continue
            if spec.exclude_generated_from_patterns and flt.is_generated(hp):
                continue
            s = stats[hp]
            s.revisions.add(c.sha)
            if small:
                s.revisions_small.add(c.sha)
            a, d = ch.added or 0, ch.deleted or 0
            s.added += a
            s.deleted += d
            s.authors[who] += a + d
            s.first = c.committer_time if s.first is None else min(s.first, c.committer_time)
            s.last = c.committer_time if s.last is None else max(s.last, c.committer_time)
            s.cites.setdefault(c.sha, (c, []))[1].append(ch)
    return stats, dict(skipped), lineage_breaks(log, ids)


def _with_breaks(path: str, n: int, statement: str, metrics: dict[str, Any], prov: dict[str, Any],
                 flags: list[str]) -> str:
    """D-H15: decorate only records whose path has a delete then re-add gap; others stay byte-identical."""
    if not n:
        return statement
    metrics["lineage_breaks"] = n
    prov["caveat"] = lineage_caveat(path, n)
    flags.append(LINEAGE_FLAG)
    return f"{statement} {prov['caveat']}"


def _recount(rc: Recounter, flt: Filters, path: str, spec_bots: bool, sizes: Mapping[str, tuple[str, str, int]] | None,
             max_cs: int) -> tuple[int, int, int | None]:
    revs, churn, small = 0, 0, 0
    for e in rc.follow(path):
        if spec_bots and flt.is_bot(e.author_name, e.author_email):
            continue
        revs += 1
        churn += e.added + e.deleted
        if sizes is not None and sizes.get(e.commit, ("", "", 0))[2] <= max_cs:
            small += 1
    return revs, churn, small if sizes is not None else None


def _check(ok: bool, detail: str) -> dict[str, Any]:
    return {"method": "git_recount", "establishes": "presence", "result": "pass" if ok else "inconclusive", "detail": detail}


def _times(log: HistoryLog) -> dict[str, int]:
    return {c.sha: c.committer_time for c in log.commits}


def churn(log: HistoryLog, *, components: ComponentMap | None = None, ctx: RunContext | None = None,
          recounter: Recounter | None = None) -> HistoryResult:
    ctx = ctx or default_context(log.repo.repo, log.repo.sha)
    flt = Filters(log.config.filters)
    with open_runner(log.repo, log.config) as runner:
        alive = set(ls_tree_paths(runner, log.repo.sha))
        stats, skipped, breaks = collect(log, flt, alive)
        now = log.by_sha[log.repo.sha].committer_time
        params = _params(log, flt, "churn")
        rc = recounter or Recounter(log, runner, flt)
        if log.config.verify:
            rc.prefetch((p, False) for p in stats)
        out: list[Record] = []
        times = _times(log)
        for path in sorted(stats):
            s = stats[path]
            tot = sum(s.authors.values()) or 1
            main = s.authors.most_common(1)[0][1] if s.authors else 0
            m = {"revisions": len(s.revisions), "added": s.added, "deleted": s.deleted, "churn": s.added + s.deleted,
                 "authors": len(s.authors), "main_author_share": round(main / tot, 4),
                 "first_seen": s.first, "last_changed": s.last,
                 "age_days": round((now - (s.last or now)) / 86400, 4)}
            chk = None
            if log.config.verify:
                r_revs, r_churn, _ = _recount(rc, flt, path, log.config.filters.exclude_bots_from_patterns, None, 0)
                ok = (r_revs, r_churn) == (m["revisions"], m["churn"])
                chk = _check(ok, f"git log --follow --no-merges --numstat recount: {r_revs} revisions, {r_churn} churn")
            cits = [citation(c, chs) for c, chs in s.cites.values()]
            prov: dict[str, Any] = {"formula": "revisions = non-merge commits touching the file's identity; churn = added + deleted"}
            flags: list[str] = []
            stmt = _with_breaks(path, breaks.get(path, 0),
                                f"{path}: {m['revisions']} revisions and {m['churn']} lines of churn (+{s.added} -{s.deleted}) "
                                f"in non-merge commits, {m['authors']} author(s). History pattern.", m, prov, flags)
            out.append(make_record(
                ctx, claim_kind="node", kind="file_history_metrics", granularity="file", frm=ep_file(path), to=None,
                statement=stmt, cls="history_pattern", provenance="history:churn", provenance_raw=prov,
                origin={"kind": "history_derived", "derived_from": sorted(s.revisions)}, qualifier="history pattern",
                citations=_sorted(cits, times), anchor={"range": [None, log.repo.sha], "first_parent": False},
                params=params, max_status="observed", metrics=m, check=chk, flags=flags))
        if components is not None:
            out += _component_metrics(log, validate_component_map(components, log.repo.sha, "churn"), stats, ctx, params, times)
    recs = finalize(out)
    report = {"stage": "churn", "records": len(recs), "files": len(stats), "skipped_commits": skipped,
              "filter_removals": flt.removals(log.commits),
              "parameters": params, "filters": flt.criteria(),
              "observed": sum(1 for r in recs if r["status"] == "observed")}
    return HistoryResult(recs, report)


def _sorted(cits: list[dict[str, Any]], times: Mapping[str, int]) -> list[dict[str, Any]]:
    return sorted(cits, key=lambda c: (times.get(c["commit"], 0), c["commit"]))


def _component_metrics(log: HistoryLog, cmap: ComponentMap, stats: Mapping[str, FileStats], ctx: RunContext,
                       params: Mapping[str, Any], times: Mapping[str, int]) -> list[Record]:
    agg: dict[str, dict[str, Any]] = {}
    for path, s in stats.items():
        cid = cmap.component_of(path)
        if cid is None:
            continue
        a = agg.setdefault(cid, {"revs": set(), "added": 0, "deleted": 0, "authors": set(), "cites": {}})
        a["revs"] |= s.revisions
        a["added"] += s.added
        a["deleted"] += s.deleted
        a["authors"] |= set(s.authors)
        for sha, (c, chs) in s.cites.items():
            a["cites"].setdefault(sha, (c, []))[1].extend(chs)
    out = []
    p = {**params, "component_map_digest": cmap.digest, "component_map_sha": cmap.sha}
    for cid in sorted(agg):
        a = agg[cid]
        m = {"revisions": len(a["revs"]), "added": a["added"], "deleted": a["deleted"],
             "churn": a["added"] + a["deleted"], "authors": len(a["authors"])}
        out.append(make_record(
            ctx, claim_kind="node", kind="component_history_metrics", granularity="component", frm=ep_component(cid),
            to=None, statement=f"Component {cid}: {m['revisions']} revisions and {m['churn']} lines of churn. History pattern.",
            cls="history_pattern", provenance="history:churn", provenance_raw={"aggregation": "union of member file revisions"},
            origin={"kind": "history_derived", "derived_from": sorted(a["revs"])}, qualifier="history pattern",
            citations=_sorted([citation(c, chs) for c, chs in a["cites"].values()], times),
            anchor={"range": [None, log.repo.sha], "first_parent": False}, params=p, max_status="unvalidated",
            metrics=m, unvalidated_reason="component membership comes from the component map; no independent recount in v1"))
    return out


def indent_complexity(text: str, path: str) -> tuple[int, int]:
    unit = 2 if path.endswith(JS_LIKE) else 4
    loc = ind = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        loc += 1
        s = line.replace("\t", "    ")
        ind += (len(s) - len(s.lstrip(" "))) // unit
    return loc, ind


def _avg_rank_norm(values: Mapping[str, float]) -> dict[str, float]:
    order = sorted(values.items(), key=lambda kv: (kv[1], kv[0]))
    n = len(order)
    out: dict[str, float] = {}
    i = 0
    while i < n:
        j = i
        while j + 1 < n and order[j + 1][1] == order[i][1]:
            j += 1
        r = ((i + 1) + (j + 1)) / 2 / n
        for k in range(i, j + 1):
            out[order[k][0]] = r
        i = j + 1
    return out


def hotspots(log: HistoryLog, *, ctx: RunContext | None = None, recounter: Recounter | None = None) -> HistoryResult:
    ctx = ctx or default_context(log.repo.repo, log.repo.sha)
    flt = Filters(log.config.filters)
    t = log.config.thresholds
    exts = tuple(log.config.code_extensions)
    with open_runner(log.repo, log.config) as runner:
        tree = runner.run("ls-tree", ["-r", "-z", "--full-tree", "-l", log.repo.sha])
        blobs: dict[str, tuple[str, int]] = {}
        for ent in tree.split(b"\0"):
            if not ent:
                continue
            meta, _, name = ent.partition(b"\t")
            mode, typ, oid, size = meta.split()
            path, _ = decode_path(name)
            if typ == b"blob" and mode != b"120000" and path.endswith(exts) and not flt.is_generated(path):
                blobs[path] = (oid.decode(), int(size) if size != b"-" else 0)
        alive = set(ls_tree_paths(runner, log.repo.sha))
        stats, skipped, breaks = collect(log, flt, alive)
        warnings = []
        cx: dict[str, tuple[int, int]] = {}
        want = sorted(p for p, (_, sz) in blobs.items() if sz <= log.config.limits.max_blob_bytes)
        too_big = sorted(set(blobs) - set(want))
        if too_big:
            warnings.append(f"{len(too_big)} files over max_blob_bytes skipped for complexity")
        if want:
            data = runner.run("cat-file", ["--batch", "-Z"], stdin=b"".join(blobs[p][0].encode() + b"\0" for p in want))
            i = 0
            for p in want:
                j = data.index(b"\0", i)
                n = int(data[i:j].split(b" ")[2])
                body = data[j + 1:j + 1 + n]
                i = j + 1 + n + 1
                if b"\0" in body[:8000]:
                    continue
                cx[p] = indent_complexity(body.decode("utf-8", "replace"), p)
        scope = sorted(p for p in cx if p in stats)
        rr = _avg_rank_norm({p: len(stats[p].revisions_small) for p in scope})
        rc_ = _avg_rank_norm({p: cx[p][1] for p in scope})
        params = _params(log, flt, "hotspot", {
            "code_extensions": list(exts),
            "formula": "score = average-rank-normalized revisions (commits with <= max_changeset_size paths) x average-rank-normalized indentation complexity at the pinned SHA",
            "complexity_proxy": "sum of leading-indent levels over non-blank lines; indent unit 2 for JS-like files, 4 otherwise; tabs = 4 spaces"})
        rc = recounter or Recounter(log, runner, flt)
        sizes = rc.changeset_sizes() if log.config.verify else None
        if log.config.verify:
            rc.prefetch((p, False) for p in scope)
        times = _times(log)
        out: list[Record] = []
        for p in scope:
            s = stats[p]
            loc, ind = cx[p]
            score = round(rr[p] * rc_[p], 4)
            m = {"hotspot_score": score, "revisions": len(s.revisions), "revisions_small_commits": len(s.revisions_small),
                 "indent_complexity": ind, "loc": loc, "revisions_rank_norm": round(rr[p], 4),
                 "complexity_rank_norm": round(rc_[p], 4), "files_ranked": len(scope)}
            chk = None
            if log.config.verify:
                r_revs, _, r_small = _recount(rc, flt, p, log.config.filters.exclude_bots_from_patterns, sizes, t.max_changeset_size)
                ok = (r_revs, r_small) == (m["revisions"], m["revisions_small_commits"])
                chk = _check(ok, f"git log --follow and log --name-only recount: {r_revs} revisions, {r_small} in small commits")
            hprov: dict[str, Any] = {"loc": loc}
            hflags = ["complexity_proxy"]
            hstmt = _with_breaks(p, breaks.get(p, 0),
                                 f"{p}: hotspot score {score} from {len(s.revisions_small)} revisions in small commits and "
                                 f"indentation complexity {ind} (a proxy). History pattern.", m, hprov, hflags)
            out.append(make_record(
                ctx, claim_kind="node", kind="file_history_metrics", granularity="file", frm=ep_file(p), to=None,
                statement=hstmt, cls="history_pattern", provenance="history:hotspot", provenance_raw=hprov,
                origin={"kind": "history_derived", "derived_from": sorted(s.revisions)},
                qualifier="history pattern; complexity is an indentation proxy",
                citations=_sorted([citation(c, chs) for c, chs in s.cites.values()], times),
                anchor={"range": [None, log.repo.sha], "first_parent": False}, params=params, max_status="observed",
                metrics=m, flags=hflags, check=chk))
    recs = finalize(out)
    recs_sorted = sorted(recs, key=lambda r: (-r["metrics"]["hotspot_score"], r["from"]["file"]))
    report = {"stage": "hotspots", "records": len(recs), "skipped_commits": skipped, "parameters": params,
              "filter_removals": flt.removals(log.commits),
              "filters": flt.criteria(), "warnings": warnings,
              "top": [{"path": r["from"]["file"], "score": r["metrics"]["hotspot_score"]} for r in recs_sorted[:10]]}
    return HistoryResult(recs, report)


__all__ = ["churn", "hotspots", "collect", "indent_complexity"]
