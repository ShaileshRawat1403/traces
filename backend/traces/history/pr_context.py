"""PR context from cached PR data (docs/contracts/history.md sections 6.1, 9.9 and 10, D-H2).

History never touches the network, tokens or cache files. PR data arrives only through an injected
`PrContextProvider` (interface.py); the default is no provider, which yields no records and a report reason.

Linking: subject `(#N)` or `Merge pull request #N`. Linking alone creates no record. For each linked PR the provider
returns a `CachedPr` or None. Records: `merged_as` (PR to local commit) and `documents_rationale` for the PR body and
each review comment that is non-empty after trimming. Quotes are byte-exact slices of the cached text and are
observed via `quote_match` only, which establishes that the quote exists, never intent.

The sha256 of the cached artifact can only be checked when the provider offers the artifact bytes through the
optional `PrContextProvider.artifact_bytes(pr_number) -> bytes | None` (interface.py, default None). None, or a
provider without the method, means "not offered": the records stay unvalidated with that reason. A PR that fails its
shape check or its sha256 check, or whose artifact is not UTF-8 JSON, is skipped with a warning; the run continues.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Iterator
from typing import Any, Protocol, runtime_checkable

from .interface import CachedComment, CachedPr, PrContextProvider
from .model import HistoryLog
from .records import RunContext, citation, ep_commit, finalize, make_record
from .shapes import HistoryResult, Record, default_context

_PAREN = re.compile(r"\(#(\d+)\)")
_MERGE = re.compile(r"^Merge pull request #(\d+)\b")
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
QUOTE_MAX = 1000
STATEMENT_QUOTE_MAX = 200
RATIONALE_QUALIFIER = "quoted rationale, not proof of intent"


@runtime_checkable
class PrArtifactSource(Protocol):
    """Kept for compatibility with #11. The capability now lives on PrContextProvider.artifact_bytes (optional,
    default None); pr_context looks it up with getattr and does not use this Protocol."""

    def artifact_bytes(self, pr_number: int) -> bytes | None: ...


def link_prs(log: HistoryLog) -> dict[int, list[str]]:
    """PR number -> local commits whose subject links it, oldest first (contract 9.9)."""
    out: dict[int, list[str]] = defaultdict(list)
    for c in log.commits:
        m = _MERGE.match(c.subject)
        nums = [int(m.group(1))] if m else [int(x) for x in _PAREN.findall(c.subject)[-1:]]
        for n in nums:
            if n >= 1 and c.sha not in out[n]:
                out[n].append(c.sha)
    return dict(sorted(out.items()))


def _shape_problem(pr: Any, number: int) -> str | None:
    if not isinstance(pr, CachedPr):
        return "provider returned something other than CachedPr"
    if not isinstance(pr.number, int) or isinstance(pr.number, bool) or pr.number != number:
        return f"cached PR number {pr.number!r} does not match requested #{number}"
    if pr.merge_commit_sha is not None and not (isinstance(pr.merge_commit_sha, str) and _SHA40.match(pr.merge_commit_sha)):
        return "merge_commit_sha is not a 40-hex SHA or null"
    if pr.body is not None and not isinstance(pr.body, str):
        return "body is not text or null"
    if not isinstance(pr.sha256, str) or not _SHA256.match(pr.sha256):
        return "sha256 is not 64 lowercase hex"
    if not isinstance(pr.source_artifact, str) or not pr.source_artifact or pr.source_artifact.startswith("/") \
            or ".." in pr.source_artifact.split("/"):
        return "source_artifact is not a relative cache path"
    try:
        when = _dt.datetime.fromisoformat(pr.fetched_at)
    except (TypeError, ValueError):
        return "fetched_at is not ISO 8601"
    if when.tzinfo is None:
        return "fetched_at has no UTC offset"
    for cm in pr.review_comments:
        if not isinstance(cm, CachedComment) or not isinstance(cm.id, int) or not isinstance(cm.body, str):
            return "review_comments entry has the wrong shape"
        if cm.commit_id is not None and not (isinstance(cm.commit_id, str) and _SHA40.match(cm.commit_id)):
            return "review comment commit_id is not a 40-hex SHA or null"
    return None


def _strings(obj: Any) -> Iterator[str]:
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k)
            yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)


def _trimmed_quote(text: str) -> str:
    """Byte-exact slice of `text`: leading and trailing whitespace dropped, capped at QUOTE_MAX characters."""
    s = text.strip()
    return s[:QUOTE_MAX]


def _short(q: str) -> str:
    one = " ".join(q.split())
    return one if len(one) <= STATEMENT_QUOTE_MAX else one[:STATEMENT_QUOTE_MAX].rstrip() + "..."


def pr_context(log: HistoryLog, provider: PrContextProvider | None, *, ctx: RunContext | None = None) -> HistoryResult:
    ctx = ctx or default_context(log.repo.repo, log.repo.sha)
    links = link_prs(log)
    base_report: dict[str, Any] = {"stage": "pr_context", "linked_prs": len(links),
                                   "linked_commits": sum(len(v) for v in links.values()),
                                   "sources": ["pr_body", "pr_review_comment"],
                                   "deferred": "issue and Discussion threads (contract section 10)"}
    if provider is None:
        return HistoryResult([], {**base_report, "pr_context": "none", "records": 0,
                                  "reason": "no PR context provider injected (offline default)"})
    by = log.by_sha
    out: list[Record] = []
    missing: list[int] = []
    skipped: list[dict[str, Any]] = []
    mismatched: list[int] = []
    unverified: list[int] = []
    used = 0
    fetch_bytes = getattr(provider, "artifact_bytes", None)
    for number, shas in links.items():
        pr = provider.get(number)
        if pr is None:
            missing.append(number)
            continue
        problem = _shape_problem(pr, number)
        strings: set[str] | None = None
        raw = fetch_bytes(number) if problem is None and callable(fetch_bytes) else None
        if raw is not None:
            if not isinstance(raw, bytes):
                problem = "artifact_bytes returned something other than bytes"
            elif hashlib.sha256(raw).hexdigest() != pr.sha256:
                problem = "cached artifact bytes do not match their sha256"
            else:
                try:
                    strings = set(_strings(json.loads(raw.decode("utf-8"))))
                except (UnicodeDecodeError, ValueError):
                    problem = "cached artifact is not UTF-8 JSON"
        if problem is not None:
            skipped.append({"pr": number, "reason": problem})
            continue
        used += 1
        local = shas[-1]
        mismatch = pr.merge_commit_sha is None or pr.merge_commit_sha not in shas
        target = pr.merge_commit_sha if not mismatch else local
        assert target is not None
        if mismatch:
            mismatched.append(number)
        if strings is None:
            unverified.append(number)
        cm = by[target]
        cit = {**citation(cm), "pr": {"number": number, "merge_commit_sha": pr.merge_commit_sha,
                                      "fetched_at": pr.fetched_at}}
        frm = {"entity": "repo", "symbol": f"repo::{log.repo.repo}#{number}"}
        to = ep_commit(target)
        flags = ["pr_sha_mismatch"] if mismatch else []
        anchor = {"pr": number, "commit": target}
        mismatch_reason = (f"cached merge_commit_sha {pr.merge_commit_sha or 'null'} is not a local commit linked to "
                           f"#{number} (local {', '.join(s[:12] for s in shas)})")

        def check_for(quote: str, haystack: str) -> dict[str, Any]:
            if strings is None:
                return {"method": "quote_match", "establishes": "presence", "result": "inconclusive", "family": "text",
                        "detail": "artifact bytes not available from the provider; sha256 not verified"}
            ok = quote.encode() in haystack.encode() and any(quote.encode() in s.encode() for s in strings)
            return {"method": "quote_match", "establishes": "presence", "result": "pass" if ok else "fail",
                    "family": "text",
                    "detail": "quote bytes found in the cached text and in the sha256-verified artifact" if ok
                    else "quote bytes not found in the sha256-verified artifact"}

        def origin(quote: str) -> dict[str, Any]:
            return {"kind": "cached_pr", "artifact": pr.source_artifact, "sha256": pr.sha256, "quote": quote}

        params_base = {"artifact_sha256": pr.sha256, "linked_by": "subject (#N) or Merge pull request #N"}
        mq = pr.merge_commit_sha or ""
        mchk = check_for(mq, mq) if mq else None
        out.append(make_record(
            ctx, claim_kind="relationship", kind="merged_as", granularity="commit", frm=frm, to=to,
            statement=(f"Cached PR #{number} metadata records merge commit {mq[:12] or 'none'}; local commit "
                       f"{target[:12]} links to #{number} by its subject."),
            cls="documented_rationale", provenance="github-cache:pr-metadata",
            provenance_raw={"linked_commits": shas, "merge_commit_sha": pr.merge_commit_sha},
            origin=origin(mq), qualifier="cached PR metadata", citations=[cit], anchor={**anchor, "part": "metadata"},
            params={**params_base, "part": "metadata"}, max_status="unvalidated" if mismatch else "observed",
            evidence_scope="documented", flags=flags, check=mchk,
            unvalidated_reason=mismatch_reason if mismatch else None))
        parts: list[tuple[str, str, str, str]] = []
        if pr.body and pr.body.strip():
            parts.append(("body", pr.body, "github-cache:pr-body", f"PR #{number} description says"))
        for c in sorted(pr.review_comments, key=lambda x: x.id):
            if c.body.strip():
                parts.append((f"comment:{c.id}", c.body, "github-cache:pr-review-comment",
                              f"PR #{number} review comment {c.id} says"))
        for part, text, prov, lead in parts:
            q = _trimmed_quote(text)
            out.append(make_record(
                ctx, claim_kind="relationship", kind="documents_rationale", granularity="commit", frm=frm, to=to,
                statement=f'{lead}: "{_short(q)}"', cls="documented_rationale", provenance=prov,
                provenance_raw={"part": part, "quote_bytes": len(q.encode()), "text_bytes": len(text.encode())},
                origin=origin(q), qualifier=RATIONALE_QUALIFIER, citations=[cit], anchor={**anchor, "part": part},
                params={**params_base, "part": part}, max_status="unvalidated" if mismatch else "observed",
                evidence_scope="documented", flags=flags, check=check_for(q, text),
                unvalidated_reason=mismatch_reason if mismatch else None))
    recs = finalize(out)
    warnings = [f"PR #{s['pr']} skipped: {s['reason']}" for s in skipped]
    report = {**base_report, "pr_context": "used" if used else "none", "records": len(recs), "prs_used": used,
              "prs_missing": missing, "prs_skipped": skipped, "warnings": warnings, "pr_sha_mismatch": mismatched,
              "sha256_unverified": unverified,
              "observed": sum(1 for r in recs if r["status"] == "observed"),
              "wording": "quotes are what the PR text says, not proof of intent"}
    if not used:
        report["reason"] = ("no linked PRs in history" if not links else
                            "provider returned no usable cached data for any linked PR")
    return HistoryResult(recs, report)
