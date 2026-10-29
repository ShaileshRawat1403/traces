"""Step 11: PR context through an injected provider (contract 6.1, 9.9, 10; HT18, HT25).

The providers here are offline fakes built from in-memory JSON. History has no GitHub client, token or cache code;
the Traces seat wires the real provider.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from traces.history import HistoryConfig, ingest
from traces.history.interface import CachedComment, CachedPr, PrContextProvider
from traces.history.pr_context import RATIONALE_QUALIFIER, link_prs, pr_context
from traces.history.records import RunContext, canonical_hash, recompute_claim_id

from ._repo import SynthRepo
from ._schema import assert_valid
from .conftest import ref

CTX = RunContext("h-test", "2026-10-21T12:00:00+05:30", "t/synth", "0" * 40)
FETCHED = "2026-10-20T10:00:00+00:00"
BODY1 = "\n  Switch the queue to RQ.\r\nWe evaluated Celery, RQ and Dramatiq; RQ was smallest. \u00e9\u2713  \n"


def _build(r: SynthRepo) -> dict[str, str]:
    s: dict[str, str] = {}
    r.write("a.py", "1\n")
    s["c1"] = r.commit("Add queue (#1)")
    r.checkout("-b", "feat")
    r.write("b.py", "1\n")
    r.commit("feat work")
    r.checkout("main")
    s["m2"] = r.merge("feat", "Merge pull request #2 from someone/feat")
    r.write("a.py", "2\n")
    s["c3"] = r.commit("Fix queue (#3)")
    r.write("a.py", "3\n")
    s["c4"] = r.commit("Refs (#9) then (#4)")
    r.write("a.py", "4\n")
    s["c5"] = r.commit("No link here #5")
    return s


def cached(number: int, merge: str | None, body: str | None, comments: list[tuple[int, str]],
           corrupt: bool = False) -> tuple[CachedPr, bytes]:
    payload = {"number": number, "merge_commit_sha": merge, "body": body,
               "review_comments": [{"id": i, "body": b, "path": "a.py", "commit_id": None} for i, b in comments]}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    if corrupt:
        digest = ("0" if digest[0] != "0" else "1") + digest[1:]
    pr = CachedPr(number=number, merge_commit_sha=merge, body=body,
                  review_comments=[CachedComment(i, b, "a.py", None) for i, b in comments],
                  source_artifact=f"github/pr/{number}.json", sha256=digest, fetched_at=FETCHED)
    return pr, raw


class OfflineFake:
    """Offline fake provider with artifact bytes (the shape the Traces seat is asked to provide)."""

    def __init__(self, items: dict[int, tuple[Any, bytes | None]]) -> None:
        self.items = items
        self.calls: list[int] = []

    def get(self, pr_number: int) -> CachedPr | None:
        self.calls.append(pr_number)
        it = self.items.get(pr_number)
        return it[0] if it else None

    def artifact_bytes(self, pr_number: int) -> bytes | None:
        it = self.items.get(pr_number)
        return it[1] if it else None


class FieldsOnlyFake:
    """Offline fake that implements only PrContextProvider.get (no artifact bytes)."""

    def __init__(self, items: dict[int, CachedPr]) -> None:
        self.items = items

    def get(self, pr_number: int) -> CachedPr | None:
        return self.items.get(pr_number)


def _kind(res: Any, kind: str, pr: int | None = None) -> list[dict[str, Any]]:
    return [r for r in res.records if r["relationship_kind"] == kind
            and (pr is None or r["from"]["symbol"].endswith(f"#{pr}"))]


def test_link_prs(synth: SynthRepo) -> None:
    s = _build(synth)
    links = link_prs(ingest(ref(synth), HistoryConfig()))
    assert links == {1: [s["c1"]], 2: [s["m2"]], 3: [s["c3"]], 4: [s["c4"]]}


def test_ht18_no_provider_and_none(synth: SynthRepo) -> None:
    _build(synth)
    log = ingest(ref(synth), HistoryConfig())
    a = pr_context(log, None, ctx=CTX)
    assert a.records == [] and a.report["pr_context"] == "none" and "no PR context provider" in a.report["reason"]
    fake = OfflineFake({})
    b = pr_context(log, fake, ctx=CTX)
    assert b.records == [] and b.report["pr_context"] == "none" and b.report["reason"]
    assert sorted(fake.calls) == [1, 2, 3, 4] and b.report["prs_missing"] == [1, 2, 3, 4]


def test_ht18_pass_mismatch_corrupt(synth: SynthRepo) -> None:
    s = _build(synth)
    log = ingest(ref(synth), HistoryConfig())
    fake = OfflineFake({
        1: cached(1, s["c1"], BODY1, [(11, "  Why RQ? Because it is small.\n"), (12, "   \n")]),
        2: cached(2, s["m2"], "Merge feature branch.", []),
        3: cached(3, "f" * 40, "Fix the queue.", []),
        4: cached(4, s["c4"], "Corrupted.", [], corrupt=True),
    })
    res = pr_context(log, fake, ctx=CTX)
    assert_valid(res.records)
    assert res.report["pr_context"] == "used" and res.report["prs_used"] == 3
    assert res.report["prs_skipped"] == [{"pr": 4, "reason": "cached artifact bytes do not match their sha256"}]
    assert res.report["warnings"] and "#4" in res.report["warnings"][0]
    assert not [r for r in res.records if r["from"]["symbol"].endswith("#4")]

    (m1,) = _kind(res, "merged_as", 1)
    assert m1["status"] == "observed" and m1["flags"] == [] and m1["to"]["symbol"] == f"commit::{s['c1']}"
    assert m1["checks"][0]["method"] == "quote_match" and m1["checks"][0]["validator"]["family"] == "text"
    d1 = _kind(res, "documents_rationale", 1)
    assert len(d1) == 2  # body and comment 11; whitespace-only comment 12 skipped
    for r in d1:
        assert r["status"] == "observed" and r["qualifier"] == RATIONALE_QUALIFIER
        assert r["class"] == "documented_rationale" and r["evidence_scope"] == "documented"
        assert r["citations"][0]["pr"] == {"number": 1, "merge_commit_sha": s["c1"], "fetched_at": FETCHED}
        assert r["from"] == {"entity": "repo", "symbol": "repo::" + log.repo.repo + "#1"}
    body = next(r for r in d1 if r["provenance"] == "github-cache:pr-body")
    q = body["origin"]["quote"]
    assert q.encode() in BODY1.encode() and q == BODY1.strip()  # byte-exact slice, CRLF and non-ASCII kept
    assert body["statement"].startswith('PR #1 description says: "Switch the queue to RQ.')
    com = next(r for r in d1 if r["provenance"] == "github-cache:pr-review-comment")
    assert com["origin"]["quote"] == "Why RQ? Because it is small."

    (m2,) = _kind(res, "merged_as", 2)
    assert m2["status"] == "observed" and m2["to"]["symbol"] == f"commit::{s['m2']}"

    (m3,) = _kind(res, "merged_as", 3)
    assert m3["status"] == "unvalidated" and "pr_sha_mismatch" in m3["flags"]
    assert m3["to"]["symbol"] == f"commit::{s['c3']}" and "f" * 12 in m3["status_reason"]
    (d3,) = _kind(res, "documents_rationale", 3)
    assert d3["status"] == "unvalidated" and "pr_sha_mismatch" in d3["flags"]
    assert res.report["pr_sha_mismatch"] == [3]
    for r in res.records:
        assert recompute_claim_id(r) == r["claim_id"]

    again = pr_context(log, fake, ctx=RunContext("h-2", "2026-10-22T09:00:00+05:30", CTX.repo, CTX.repo_sha))
    assert canonical_hash(again.records) == canonical_hash(res.records)


def test_shape_and_artifact_problems_skip(synth: SynthRepo) -> None:
    s = _build(synth)
    log = ingest(ref(synth), HistoryConfig())
    good, raw = cached(1, s["c1"], "Body.", [])
    wrong_number = cached(5, s["c3"], "x", [])[0]
    bad_time, _ = cached(4, s["c4"], "Body.", [])
    bad_time = CachedPr(4, s["c4"], "Body.", [], "github/pr/4.json", bad_time.sha256, "yesterday")
    fake = OfflineFake({1: (good, None), 2: ({"number": 2}, b"{}"),
                        3: (wrong_number, b"{}"), 4: (bad_time, b"{}")})
    res = pr_context(log, fake, ctx=CTX)
    reasons = {x["pr"]: x["reason"] for x in res.report["prs_skipped"]}
    assert 1 not in reasons  # artifact_bytes None means "not offered": used, sha256 unverified
    assert "other than CachedPr" in reasons[2]
    assert "does not match requested #3" in reasons[3]
    assert "fetched_at" in reasons[4]
    assert res.report["sha256_unverified"] == [1] and res.report["prs_used"] == 1
    assert res.records and all(r["status"] == "unvalidated" and r["from"]["symbol"].endswith("#1") for r in res.records)
    notjson = b"not json"
    pr = CachedPr(1, s["c1"], "Body.", [], "github/pr/1.json", hashlib.sha256(notjson).hexdigest(), FETCHED)
    res2 = pr_context(log, OfflineFake({1: (pr, notjson), 2: (cached(2, s["m2"], "M.", [])[0], raw)}), ctx=CTX)
    reasons2 = {x["pr"]: x["reason"] for x in res2.report["prs_skipped"]}
    assert reasons2 == {1: "cached artifact is not UTF-8 JSON", 2: "cached artifact bytes do not match their sha256"}


def test_without_artifact_bytes_stays_unvalidated(synth: SynthRepo) -> None:
    s = _build(synth)
    log = ingest(ref(synth), HistoryConfig())
    pr, _ = cached(1, s["c1"], BODY1, [])
    res = pr_context(log, FieldsOnlyFake({1: pr}), ctx=CTX)
    assert_valid(res.records)
    assert res.records and all(r["status"] == "unvalidated" for r in res.records)
    assert res.report["sha256_unverified"] == [1]
    d = _kind(res, "documents_rationale", 1)[0]
    assert d["checks"][0]["result"] == "inconclusive" and "sha256 not verified" in d["status_reason"]


def test_ht25_quote_match_never_beyond_observed(synth: SynthRepo) -> None:
    s = _build(synth)
    log = ingest(ref(synth), HistoryConfig())
    fake = OfflineFake({1: cached(1, s["c1"], BODY1, [(11, "Because.")]), 2: cached(2, s["m2"], "M.", [])})
    res = pr_context(log, fake, ctx=CTX)
    assert res.records
    for r in res.records:
        assert r["status"] in {"observed", "unvalidated"} and r["label"] in {"observed", "inferred"}
        assert r["class"] == "documented_rationale"
        assert all(c["method"] == "quote_match" and c["establishes"] == "presence" for c in r["checks"])
        assert [h["to"] for h in r["status_history"]] in (["unvalidated"], ["unvalidated", "observed"])
        assert "intent" not in r["statement"].lower() or r["qualifier"] == RATIONALE_QUALIFIER


class SubclassedProvider(PrContextProvider):
    """Subclasses the Protocol and implements only get(): inherits artifact_bytes -> None."""

    def __init__(self, pr: CachedPr) -> None:
        self.pr = pr

    def get(self, pr_number: int) -> CachedPr | None:
        return self.pr if pr_number == self.pr.number else None


def test_interface_artifact_bytes_default_and_optional(synth: SynthRepo) -> None:
    import inspect

    sig = inspect.signature(PrContextProvider.artifact_bytes)
    assert list(sig.parameters) == ["self", "pr_number"]
    assert sig.return_annotation in ("bytes | None", bytes | None)
    s = _build(synth)
    log = ingest(ref(synth), HistoryConfig())
    pr, raw = cached(1, s["c1"], BODY1, [])
    sub = SubclassedProvider(pr)
    assert sub.artifact_bytes(1) is None  # inherited default
    a = pr_context(log, sub, ctx=CTX)
    b = pr_context(log, FieldsOnlyFake({1: pr}), ctx=CTX)  # structural, no method at all
    assert a.records == b.records and a.report["sha256_unverified"] == [1]
    assert all(r["status"] == "unvalidated" for r in a.records)

    class WithBytes(SubclassedProvider):
        def artifact_bytes(self, pr_number: int) -> bytes | None:
            return raw if pr_number == 1 else None

    c = pr_context(log, WithBytes(pr), ctx=CTX)
    assert c.report["sha256_unverified"] == [] and all(r["status"] == "observed" for r in c.records)
