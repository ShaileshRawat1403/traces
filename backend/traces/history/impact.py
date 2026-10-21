"""History impact (docs/contracts/history.md sections 6.1 and 8.9, D-H1).

History side only. Every result sits under a `history:*` source key, every emitted record is an unvalidated
`history_impact_candidate` that cites the co_changed_with record it derives from, and code-dependency edges are never
read or returned. "May be affected" is an interpretation of past coupling, never causation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from .errors import E_CONFIG, E_EVIDENCE_SET, HistoryError
from .records import RunContext, finalize, make_record

SOURCE_COCHANGE = "history:co_change"
SOURCE_ALIAS = "history:alias"
BASE_GAPS = (
    "history signals do not show code dependencies; see CodeGraph and framework-rule impact for those",
    "co-change is coupling over past commits, not causation",
)
_STAGE = "impact"


@dataclass(frozen=True)
class ImpactResult:
    target: str
    by_source: Mapping[str, Sequence[dict[str, Any]]]
    known_gaps: tuple[str, ...]
    parameters: Mapping[str, object] = field(default_factory=dict)


def normalize_target(target: str) -> str:
    t = target.strip()
    if not t:
        raise HistoryError(E_CONFIG, "impact target is empty", _STAGE)
    if t.startswith(("file::", "component::")):
        return t
    if "::" in t:
        raise HistoryError(E_CONFIG, "impact target must be a file:: or component:: symbol or a repo path", _STAGE)
    return f"file::{t}"


def _ctx_from(rec: Mapping[str, Any]) -> RunContext:
    hist = rec.get("status_history") or [{}]
    return RunContext(run_id=rec["run_id"], at=hist[0].get("at") or "1970-01-01T00:00:00+00:00", repo=rec["repo"],
                      repo_sha=rec["repo_sha"])


def _usable_alias(rec: Mapping[str, Any]) -> bool:
    return (rec.get("relationship_kind") == "alias_of"
            and (rec.get("review_state") or {}).get("state") != "disputed")


def history_impact(target: str, cochange_records: Sequence[Mapping[str, Any]], *,
                   aliases: Sequence[Mapping[str, Any]] = (), limit: int = 20,
                   ctx: RunContext | None = None) -> ImpactResult:
    """Rank co-change partners of `target` and wrap each as an unvalidated history_impact_candidate.

    Input records that are not co_changed_with (for example code-dependency edges) are ignored and counted, never
    returned. alias_of records that touch the target (and are not disputed) are passed through unchanged under
    `history:alias`; their other end widens the co-change lookup and those candidates carry flag x-via_alias.
    """
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise HistoryError(E_CONFIG, "limit must be a positive integer", _STAGE)
    tgt = normalize_target(target)
    gaps = list(BASE_GAPS)
    cochange = [r for r in cochange_records if r.get("relationship_kind") == "co_changed_with"]
    ignored = len(cochange_records) - len(cochange)
    if ignored:
        gaps.append(f"{ignored} input record(s) were not co_changed_with and were ignored")
    origins = {(r["repo"], r["repo_sha"]) for r in cochange}
    if len(origins) > 1:
        raise HistoryError(E_EVIDENCE_SET, "co-change records come from more than one repo or commit", _STAGE)

    alias_recs = []
    via: dict[str, str] = {}  # alias symbol -> alias claim id
    for a in aliases:
        if not _usable_alias(a):
            continue
        ends = {(a.get("from") or {}).get("symbol"), (a.get("to") or {}).get("symbol")}
        if tgt in ends:
            alias_recs.append(dict(a))
            for e in ends - {tgt, None}:
                via.setdefault(str(e), a["claim_id"])
    if not alias_recs:
        gaps.append("no alias_of records for this target; v1 does not generate alias suggestions (contract 8.8)")
    alias_recs.sort(key=lambda r: r["claim_id"])

    lookup = {tgt: None, **via}
    found: dict[str, tuple[Mapping[str, Any], str | None]] = {}
    for r in cochange:
        a, b = r["from"]["symbol"], r["to"]["symbol"]
        for me, other in ((a, b), (b, a)):
            if me in lookup and other != tgt and other not in lookup:
                prev = found.get(other)
                if prev is None or (prev[1] is not None and lookup[me] is None):
                    found[other] = (r, lookup[me])

    def rank(item: tuple[str, tuple[Mapping[str, Any], str | None]]) -> tuple[float, int, bytes]:
        m = item[1][0].get("metrics") or {}
        return (-float(m.get("degree", 0.0)), -int(m.get("support", 0)), item[0].encode())

    ranked = sorted(found.items(), key=rank)
    truncated = max(0, len(ranked) - limit)
    if truncated:
        gaps.append(f"{truncated} further co-change partner(s) not shown (limit {limit})")
    out = []
    for other, (src, via_cid) in ranked[:limit]:
        c = ctx or _ctx_from(src)
        m = src.get("metrics") or {}
        n, total = int(m.get("support", 0)), int(m.get("union_commits", 0))
        my_end = src["from"] if src["to"]["symbol"] == other else src["to"]
        other_end = src["to"] if src["to"]["symbol"] == other else src["from"]
        frm = {"entity": my_end["entity"], "symbol": tgt}
        if frm["entity"] == "file":
            frm["file"] = tgt.removeprefix("file::")
        derived = [src["claim_id"]] + ([via_cid] if via_cid else [])
        out.append(make_record(
            c, claim_kind="relationship", kind="history_impact_candidate", granularity=src["granularity"],
            frm=frm, to=dict(other_end),
            statement=(f"{other.split('::', 1)[1]} may be worth checking when {tgt.split('::', 1)[1]} changes: "
                       f"they changed together in {n} of {total} commits. History signal only, not a code dependency."),
            cls="history_pattern", provenance="history:impact",
            provenance_raw={"source_claim": src["claim_id"], "via_alias": via_cid, "source_status": src["status"]},
            origin={"kind": "history_derived", "derived_from": derived},
            qualifier=f"history signal: changed together in {n} of {total} commits",
            citations=src["citations"], anchor=dict((src.get("provenance_raw") or {}).get("claim_anchor") or {}),
            params={"source_claim": src["claim_id"], "via_alias": via_cid,
                    "source_parameters_digest": src["parameters"]["digest"]},
            max_status="unvalidated", metrics={k: m[k] for k in ("support", "union_commits", "degree") if k in m},
            flags=["x-via_alias"] if via_cid else (),
            unvalidated_reason="interpretation of past co-change; impact is not established (D-H1)"))
    recs = finalize(out)
    if not recs:
        gaps.append(f"no co-change records for {tgt}")
    params: dict[str, object] = {"target": tgt, "limit": limit, "inputs_cochange": len(cochange),
                                 "inputs_ignored": ignored, "aliases_used": len(alias_recs), "truncated": truncated}
    return ImpactResult(target=tgt, by_source={SOURCE_COCHANGE: recs, SOURCE_ALIAS: alias_recs},
                        known_gaps=tuple(gaps), parameters=params)
