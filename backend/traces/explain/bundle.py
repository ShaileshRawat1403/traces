"""Explain hook points (Traces UI seat). Deterministic, no LLM, no provider keys: see engine.py and docs/CONTRACTS.md 4.12.

The API (api/app.py, Traces seat) is expected to call these with the snapshot it has already resolved."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from traces.evidence.store import Store
from traces.explain.engine import explain_records
from traces.explain.records import ClaimView, view


@lru_cache(maxsize=4)
def _views(path: str, snapshot_id: str, count: int) -> tuple[ClaimView, ...]:
    """Records of a snapshot projected once. A snapshot's records are fixed at its SHA; the count guards re-imports."""
    st = Store(path) if path != ":memory:" else None
    if st is None:
        raise LookupError("in-memory stores are not cached")
    return tuple(v for v in (view(r) for r in st.iter_claims(snapshot_id)) if v is not None)


def _records(st: Store, snapshot_id: str) -> Any:
    if st.path == ":memory:":
        return st.iter_claims(snapshot_id)
    count = sum(st.status_counts(snapshot_id).values())
    return _views(st.path, snapshot_id, count)


def _store(store: Store | None) -> Store:
    if store is not None:
        return store
    from traces.core.config import get_settings

    return Store(get_settings().db_path)


def _sha(st: Store, snapshot_id: str) -> str | None:
    snap = st.get_snapshot(snapshot_id)
    if snap is None:
        raise LookupError(f"snapshot {snapshot_id} not found")
    return snap.get("sha")


def explain(snapshot_id: str, question: str, focus_claim_ids: list[str], store: Store | None = None) -> dict[str, Any]:
    """ExplainResponse (mode no_llm): template-built answer from the snapshot's records, every sentence tagged."""
    st = _store(store)
    sha = _sha(st, snapshot_id)
    return explain_records(
        _records(st, snapshot_id), snapshot_id=snapshot_id, sha=sha, question=question, focus_claim_ids=focus_claim_ids
    )


def prompt_bundle(
    snapshot_id: str, question: str, focus_claim_ids: list[str], store: Store | None = None
) -> dict[str, Any]:
    """ExplainResponse (mode prepare_bundle): the same answer plus prompt_bundle and outbound_manifest.
    Never accepts or returns provider credentials; the browser sends the bundle after user consent."""
    st = _store(store)
    sha = _sha(st, snapshot_id)
    return explain_records(
        _records(st, snapshot_id),
        snapshot_id=snapshot_id,
        sha=sha,
        question=question,
        focus_claim_ids=focus_claim_ids,
        mode="prepare_bundle",
    )
