"""Evidence record construction for history claims (docs/contracts/history.md sections 5 to 7).

traces-evidence 0.4 is not on build/traces-v1 yet; these builders emit the 0.4 shapes requested in the contract as
plain dicts so they can move to `backend/traces/evidence` types when the Traces seat lands them.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .config import EXTRACTOR, canon, digest
from .errors import E_COLLISION, E_PATH, E_SCHEMA, HistoryError
from .model import Change, Commit

SCHEMA_VERSION = "traces-evidence/0.4"
ORIGINATOR = {"name": EXTRACTOR["name"], "version": EXTRACTOR["version"], "role": "history_analyzer"}
GIT_VALIDATOR = {"name": "traces-history-gitcheck", "version": EXTRACTOR["version"], "family": "git"}
VOLATILE = ("run_id", "at")
NEVER_VERIFIED = True  # no history record reaches verified in 0.4 (contract section 6)


@dataclass(frozen=True)
class RunContext:
    run_id: str
    at: str  # ISO 8601 with offset
    repo: str
    repo_sha: str


def _check_path(p: str) -> str:
    if not p or p.startswith("/") or p.endswith("/") or p == ".." or p.startswith("../") or "/../" in p or p.endswith("/.."):
        raise HistoryError(E_PATH, "emitted path is empty, absolute, ends with '/' or contains '..'", "records")
    return p


def ep_file(path: str) -> dict[str, str]:
    return {"entity": "file", "symbol": f"file::{_check_path(path)}", "file": path}


def ep_commit(sha: str) -> dict[str, str]:
    return {"entity": "commit", "symbol": f"commit::{sha}"}


def ep_component(cid: str) -> dict[str, str]:
    sym = cid if cid.startswith("component::") else f"component::{cid}"  # ComponentDef.id is already prefixed
    return {"entity": "component", "symbol": sym}


def ep_path(prefix: str) -> dict[str, str]:
    return {"entity": "file", "symbol": f"file::{_check_path(prefix)}/", "file": prefix}


def cite_change(c: Change) -> dict[str, Any]:
    return {"path": c.path, "old_path": c.old_path, "status": c.status, "similarity": c.similarity,
            "blob_before": c.blob_before, "blob_after": c.blob_after}


def citation(commit: Commit, changes: Iterable[Change] = ()) -> dict[str, Any]:
    paths = sorted((cite_change(c) for c in changes), key=lambda d: (d["path"], d["status"]))
    return {"commit": commit.sha, "parents": list(commit.parents), "paths": paths}


def sort_citations(cits: Iterable[dict[str, Any]], times: Mapping[str, int]) -> list[dict[str, Any]]:
    return sorted(cits, key=lambda c: (times.get(c["commit"], 0), c["commit"]))


def parameters(values: Mapping[str, Any]) -> dict[str, Any]:
    return {"digest": digest(values), "values": dict(values)}


def claim_id(*, claim_kind: str, kind: str, granularity: str, frm: Mapping[str, Any] | None,
             to: Mapping[str, Any] | None, anchor: Mapping[str, Any], parameters_digest: str,
             symmetric: bool = False) -> str:
    """Contract section 7.2: c_ + sha256 of canonical JSON of the claim identity (Task 002 family)."""
    a = frm["symbol"] if frm else None
    b = to["symbol"] if to else None
    if symmetric and a is not None and b is not None and b.encode() < a.encode():
        a, b = b, a
    ident = {"family": "traces-history", "claim_kind": claim_kind, "kind": kind, "granularity": granularity,
             "subject": {"from": a, "to": b}, "anchor": dict(anchor),
             "extractor": {"name": EXTRACTOR["name"], "version": EXTRACTOR["version"]},
             "parameters_digest": parameters_digest}
    return "c_" + hashlib.sha256(canon(ident).encode("utf-8")).hexdigest()


def make_check(cid: str, *, method: str, establishes: str, result: str, detail: str, ctx: RunContext,
               inputs: Sequence[Any] = (), family: str = "git", independent: bool = True) -> dict[str, Any]:
    validator = dict(GIT_VALIDATOR)
    validator["family"] = family
    body = {"claim_id": cid, "method": method, "inputs": list(inputs), "validator": validator}
    return {"check_id": "k_" + hashlib.sha256(canon(body).encode()).hexdigest(), "method": method,
            "establishes": establishes, "rule_id": None, "validator": validator, "reads_originator_output": False,
            "independent": independent, "inputs": list(inputs), "result": result, "detail": detail,
            "run_id": ctx.run_id, "at": ctx.at}


def make_record(ctx: RunContext, *, claim_kind: str, kind: str, granularity: str, frm: Mapping[str, Any] | None,
                to: Mapping[str, Any] | None, statement: str, cls: str, provenance: str,
                provenance_raw: Mapping[str, Any], origin: Mapping[str, Any], qualifier: str | None,
                citations: Sequence[Mapping[str, Any]], anchor: Mapping[str, Any], params: Mapping[str, Any],
                max_status: str, evidence_scope: str = "history", metrics: Mapping[str, Any] | None = None,
                flags: Iterable[str] = (), check: Mapping[str, Any] | None = None, symmetric: bool = False,
                unvalidated_reason: str | None = None) -> dict[str, Any]:
    """Build one record. `check` is a dict(method, establishes, result, detail, inputs) for the independent check;
    status is `observed` only when max_status allows it and that check passed."""
    if not citations:
        raise HistoryError(E_SCHEMA, "history records need at least one citation", "records")
    prm = parameters(params)
    cid = claim_id(claim_kind=claim_kind, kind=kind, granularity=granularity, frm=frm, to=to, anchor=anchor,
                   parameters_digest=prm["digest"], symmetric=symmetric)
    if symmetric and frm and to and to["symbol"].encode() < frm["symbol"].encode():
        frm, to = to, frm
    checks = []
    if check is not None:
        checks.append(make_check(cid, ctx=ctx, **check))
    passed = [c for c in checks if c["independent"] and c["result"] == "pass" and c["establishes"] == "presence"]
    hist: list[dict[str, Any]] = [{"from": None, "to": "unvalidated", "at": ctx.at, "run_id": ctx.run_id, "check_ids": [], "by": EXTRACTOR["name"]}]
    if max_status == "observed" and passed:
        status, label, reason = "observed", "observed", None
        hist.append({"from": "unvalidated", "to": "observed", "at": ctx.at, "run_id": ctx.run_id,
                     "check_ids": [c["check_id"] for c in passed], "by": EXTRACTOR["name"]})
    else:
        status, label = "unvalidated", "inferred"
        if unvalidated_reason:
            reason = unvalidated_reason
        elif not checks:
            reason = "no independent check run"
        else:
            reason = "; ".join(f"{c['method']} {c['result']}: {c['detail']}" for c in checks)
    rec: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION, "claim_id": cid, "run_id": ctx.run_id, "repo": ctx.repo,
        "repo_sha": ctx.repo_sha, "claim_kind": claim_kind, "granularity": granularity, "statement": statement,
        "class": cls, "originator": dict(ORIGINATOR), "provenance_raw": dict(provenance_raw),
        "provenance": provenance, "origin": dict(origin), "injected": False, "evidence_scope": evidence_scope,
        "qualifier": qualifier, "citations": [dict(c) for c in citations], "locations": [], "checks": checks,
        "status": status, "label": label, "status_history": hist, "visible_to_reviewer": True,
        "parameters": prm, "metrics": dict(metrics) if metrics is not None else None,
        "flags": sorted(set(flags)), "review_state": {"state": "none", "reviewer": None, "at": None},
    }
    if reason:
        rec["status_reason"] = reason
    if claim_kind == "relationship":
        rec["relationship_kind"] = kind
    else:
        rec["node_kind"] = kind
    if frm is not None:
        rec["from"] = dict(frm)
    if to is not None:
        rec["to"] = dict(to)
    return rec


def strip_volatile(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: strip_volatile(v) for k, v in obj.items() if k not in VOLATILE}
    if isinstance(obj, list):
        return [strip_volatile(v) for v in obj]
    return obj


def finalize(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort by claim_id; drop exact duplicates; raise E_COLLISION when one id carries different content."""
    seen: dict[str, str] = {}
    out: list[dict[str, Any]] = []
    for r in records:
        body = canon(strip_volatile(r))
        prev = seen.get(r["claim_id"])
        if prev is None:
            seen[r["claim_id"]] = body
            out.append(r)
        elif prev != body:
            raise HistoryError(E_COLLISION, f"claim id {r['claim_id']} carries two different records", "records")
    out.sort(key=lambda r: r["claim_id"])
    return out


def canonical_hash(records: Iterable[dict[str, Any]]) -> str:
    h = hashlib.sha256()
    for r in records:
        h.update(canon(strip_volatile(r)).encode())
        h.update(b"\n")
    return h.hexdigest()
