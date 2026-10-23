"""Co-change (logical coupling) at file or component level (contract section 9.4, decision D-H1).

revs(A) = considered commits touching A; support(A,B) = considered commits touching both;
confidence(A to B) = support / revs(A); degree = support / mean(revs(A), revs(B)).
Considered commits: non-merge, not bot-authored (default), at most max_changeset_size non-generated paths.
Kept when revs >= min_revs on both sides, support >= min_shared_revs, degree >= min_coupling.
Defaults 5 / 5 / 0.30 / 30 are the published Code Maat defaults; this is an implementation of the formulas only.
Records are history_pattern: the counts may be observed after an independent recount, never verified, and the
wording is always "changed together in N of M commits".
"""

from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations
from typing import Any, Literal

from .errors import E_COMPONENT_MAP, E_CONFIG, HistoryError
from .filters import Filters
from .ingest import ls_tree_paths, open_runner
from .lifecycle import LINEAGE_FLAG, identities, lineage_breaks, lineage_caveat
from .model import Change, Commit, HistoryLog
from .records import RunContext, citation, ep_component, ep_file, finalize, make_record
from .shapes import ComponentMap, HistoryResult, Record, default_context, validate_component_map
from .verify import Recounter

BANNED_WORDS = ("causes", "caused", "because", "depends on", "drives", "breaks")


def statement_for(a: str, b: str, support: int, union: int, level: str) -> str:
    what = "files" if level == "file" else "components"
    return (f"{a} and {b} changed together in {support} of {union} commits that touched either of these {what}. "
            "History pattern only; it is not a code dependency and does not show intent.")


def cochange(log: HistoryLog, *, level: Literal["file", "component"] = "file", components: ComponentMap | None = None,
             ctx: RunContext | None = None, recounter: Recounter | None = None) -> HistoryResult:
    if level not in ("file", "component"):
        raise HistoryError(E_CONFIG, "level must be 'file' or 'component'", "cochange")
    if level == "component":
        if components is None:
            raise HistoryError(E_COMPONENT_MAP, "component-level co-change needs a component map", "cochange")
        validate_component_map(components, log.repo.sha, "cochange")
    ctx = ctx or default_context(log.repo.repo, log.repo.sha)
    flt = Filters(log.config.filters)
    spec = log.config.filters
    t = log.config.thresholds
    with open_runner(log.repo, log.config) as runner:
        alive = set(ls_tree_paths(runner, log.repo.sha))
        ids = identities(log, alive)
        breaks = lineage_breaks(log, ids) if level == "file" else {}
        revs: Counter[str] = Counter()
        pairs: Counter[tuple[str, str]] = Counter()
        support_commits: dict[tuple[str, str], list[str]] = defaultdict(list)
        touched: dict[tuple[str, str], list[Change]] = defaultdict(list)  # (commit, unit) -> changes
        skipped = Counter[str]()
        considered = 0
        for c in log.commits:
            if c.is_merge:
                skipped["merge"] += 1
                continue
            if spec.exclude_bots_from_patterns and flt.is_bot(c.author_name, c.author_email):
                skipped["bot"] += 1
                continue
            kept = [ch for ch in c.changes if not (spec.exclude_generated_from_patterns and flt.is_generated(ch.path))]
            if len(kept) > t.max_changeset_size:
                skipped["large_changeset"] += 1
                continue
            considered += 1
            units: set[str] = set()
            for ch in kept:
                hp = ids.head_path(c.sha, ch.path)
                if hp is None or (spec.exclude_generated_from_patterns and flt.is_generated(hp)):
                    continue
                u = hp if level == "file" else (components.component_of(hp) if components else None)
                if u is None:
                    continue
                units.add(u)
                touched[(c.sha, u)].append(ch)
            revs.update(units)
            for a, b in combinations(sorted(units, key=lambda s: s.encode()), 2):
                pairs[(a, b)] += 1
                support_commits[(a, b)].append(c.sha)
        params: dict[str, Any] = {
            **log.ingest_parameters(), "level": level, "min_revs": t.min_revs, "min_shared_revs": t.min_shared_revs,
            "min_coupling": t.min_coupling, "max_changeset_size": t.max_changeset_size,
            "rename_normalization": "head_paths", "commits": "non-merge commits only", "filters": flt.criteria(),
            "formula": "degree = support / mean(revs_a, revs_b); confidence = support / revs",
            "defaults_source": "published Code Maat defaults (formulas only, no code)"}
        if components is not None:
            params.update({"component_map_digest": components.digest, "component_map_sha": components.sha})
        kept_pairs = []
        for (a, b), s in pairs.items():
            ra, rb = revs[a], revs[b]
            degree = s / ((ra + rb) / 2)
            if s >= t.min_shared_revs and ra >= t.min_revs and rb >= t.min_revs and degree >= t.min_coupling:
                kept_pairs.append((a, b, s, ra, rb, degree))
        rc = recounter or Recounter(log, runner, flt)
        sizes = None
        if log.config.verify and level == "file" and kept_pairs:
            sizes = rc.changeset_sizes()
            rc.prefetch({(p, False) for a, b, *_ in kept_pairs for p in (a, b)})
        by = log.by_sha
        times = {c.sha: c.committer_time for c in log.commits}
        out: list[Record] = []
        for a, b, s, ra, rb, degree in kept_pairs:
            union = ra + rb - s
            m = {"support": s, "revs_a": ra, "revs_b": rb, "union_commits": union,
                 "confidence_a_to_b": round(s / ra, 4), "confidence_b_to_a": round(s / rb, 4),
                 "degree": round(degree, 4), "commits_considered": considered,
                 "commits_skipped_merge": skipped.get("merge", 0), "commits_skipped_bot": skipped.get("bot", 0),
                 "commits_skipped_large": skipped.get("large_changeset", 0)}
            chk = None
            if sizes is not None:
                ok, detail = _recount(rc, flt, spec.exclude_bots_from_patterns, sizes, t.max_changeset_size, a, b, s, ra, rb)
                chk = {"method": "git_recount", "establishes": "presence", "result": "pass" if ok else "inconclusive",
                       "detail": detail}
            cits = []
            for sha in support_commits[(a, b)]:
                cm: Commit = by[sha]
                cits.append(citation(cm, touched[(sha, a)] + touched[(sha, b)]))
            cits.sort(key=lambda x: (times[x["commit"]], x["commit"]))
            ep = ep_file if level == "file" else ep_component
            reason = None if level == "file" else "component-level counts use the component map; no independent recount in v1"
            prov: dict[str, Any] = {"support": s, "revs_a": ra, "revs_b": rb}
            stmt = statement_for(a, b, s, union, level)
            flags: list[str] = []
            ba, bb = breaks.get(a, 0), breaks.get(b, 0)
            if ba or bb:  # D-H15: only pairs with a delete then re-add gap on either side change
                m.update({"lineage_breaks": ba + bb, "lineage_breaks_a": ba, "lineage_breaks_b": bb})
                prov["caveat"] = " ".join(lineage_caveat(x, n) for x, n in ((a, ba), (b, bb)) if n)
                stmt = f"{stmt} {prov['caveat']}"
                flags.append(LINEAGE_FLAG)
            out.append(make_record(
                ctx, claim_kind="relationship", kind="co_changed_with", granularity=level, frm=ep(a), to=ep(b),
                statement=stmt, cls="history_pattern", provenance="history:cochange", provenance_raw=prov, flags=flags,
                origin={"kind": "history_derived", "derived_from": support_commits[(a, b)]},
                qualifier=f"changed together in {s} of {union} commits", citations=cits,
                anchor={"range": [None, log.repo.sha], "first_parent": False}, params=params,
                max_status="observed" if level == "file" else "unvalidated", metrics=m, check=chk, symmetric=True,
                unvalidated_reason=reason))
    recs = finalize(out)
    report = {"stage": "cochange", "level": level, "records": len(recs), "commits_considered": considered,
              "skipped_commits": dict(skipped), "parameters": params, "filters": flt.criteria(),
              "filter_removals": flt.removals(log.commits),
              "observed": sum(1 for r in recs if r["status"] == "observed"),
              "lineage_break_records": sum(1 for r in recs if LINEAGE_FLAG in r["flags"]),
              "wording": "changed together in N of M commits; never causation"}
    return HistoryResult(recs, report)


def _recount(rc: Recounter, flt: Filters, bots: bool, sizes: dict[str, tuple[str, str, int]], max_cs: int,
             a: str, b: str, s: int, ra: int, rb: int) -> tuple[bool, str]:
    def considered(path: str) -> set[str]:
        out = set()
        for e in rc.follow(path):
            info = sizes.get(e.commit)
            if info is None:
                continue
            if bots and flt.is_bot(info[0], info[1]):
                continue
            if info[2] > max_cs:
                continue
            out.add(e.commit)
        return out

    sa, sb = considered(a), considered(b)
    got = (len(sa & sb), len(sa), len(sb))
    return got == (s, ra, rb), f"git log --follow and log --name-only recount: support {got[0]}, revs {got[1]} / {got[2]}"
