"""Explain hook points. Not implemented in FOUNDATION; owner: Traces UI seat."""
from __future__ import annotations

from typing import Any


def explain(snapshot_id: str, question: str, focus_claim_ids: list[str]) -> dict[str, Any]:
    raise NotImplementedError("explain: not implemented (owner: Traces UI)")


def prompt_bundle(snapshot_id: str, question: str, focus_claim_ids: list[str]) -> dict[str, Any]:
    """Return {prompt, citations, outbound_manifest}. Must never accept or return provider credentials."""
    raise NotImplementedError("explain: not implemented (owner: Traces UI)")
