"""API request and response models (the REST contract; FastAPI generates docs/contracts/openapi.json from these).
Evidence records themselves are traces-evidence/0.4 JSON (schema in backend/traces/evidence/schema), returned as-is."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Status = Literal["verified", "observed", "unvalidated", "missing_location", "rejected"]
Label = Literal["verified", "observed", "inferred", "rejected"]
JobState = Literal["queued", "running", "succeeded", "failed", "cancelled"]
JobPhase = Literal["queued", "fetching", "checking_out", "indexing", "adapting", "validating", "storing", "history", "done", "failed"]
SnapshotState = Literal["pending", "indexing", "ready", "failed"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorBody(Strict):
    code: str = Field(description="machine code, e.g. not_implemented, invalid_repo_url, invalid_sha, not_found, repo_not_public, repo_empty, "
                                  "sha_not_found, too_large, too_many_files, fetch_timeout, upstream_unavailable, rate_limited, fetch_failed")
    message: str
    owner: str | None = Field(None, description="seat that owns the missing capability (not_implemented only)")
    milestone: str | None = None
    detail: dict[str, Any] | None = None


class ErrorResponse(Strict):
    error: ErrorBody


class Health(Strict):
    status: Literal["ok"]
    version: str
    store_migration: int


class Meta(Strict):
    version: str
    evidence_schema: str
    evidence_schemas_readable: list[str]
    extractor: dict[str, str]
    validators: dict[str, str]
    isolation: Literal["unshare", "none", "off"] = Field(description="configured worker isolation: unshare (default; auto resolves "
                                                       "to unshare or fails closed), off (explicit dev override, snapshots indexed this "
                                                       "way are unisolated). none is no longer emitted (D-026)")
    capabilities: dict[str, bool] = Field(description="capability -> implemented in this build")


class Repo(Strict):
    id: str
    host: str
    owner: str
    name: str
    url: str
    visibility: Literal["public"]
    created_at: str
    latest_discovered_sha: str | None = None
    latest_discovered_at: str | None = None
    default_branch: str | None = None
    visibility_checked_at: str | None = Field(None, description="when an anonymous (credential-free) ls-remote last confirmed the repo is public")
    external_ai_consent: bool = Field(False, description="repo-level consent to send source snippets to an external AI provider, set "
                                      "with PUT /repos/{id}/ai-consent (D-027). The browser still shows the outbound manifest and asks "
                                      "before each send")
    external_ai_consent_at: str | None = Field(None, description="when the repo-level consent was last granted or revoked (D-027)")
    external_ai_consent_text_version: str | None = Field(None, description="version of the consent text the user agreed to; null when "
                                                         "consent is not granted (D-027)")


class AiConsentUpdate(Strict):
    consent: bool = Field(description="true grants repo-level consent to send evidence to an external AI provider; false revokes it")
    consent_text_version: str | None = Field(None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$",
                                             description="version of the consent text shown to the user; required when consent is true")


class RepoCreate(Strict):
    url: str = Field(description="https://github.com/<owner>/<repo>; public repositories only in v1")
    sha: str | None = Field(None, description="optional full commit SHA to pin; default: current HEAD of the default branch")


class Snapshot(Strict):
    id: str
    repo_id: str
    sha: str
    state: SnapshotState
    evidence_schema: str
    extractor: dict[str, Any]
    languages: dict[str, int]
    frameworks: list[str]
    generated_paths: list[str]
    stats: dict[str, Any]
    created_at: str
    indexed_at: str | None = None
    isolation: Literal["unshare", "off"] | None = Field(None, description="how the analysis workers ran for the stored evidence: "
                                                        "unshare (no network, probe-checked) or off (explicit dev override). null "
                                                        "before indexing or for snapshots stored before D-026")
    unisolated: bool | None = Field(None, description="true when the evidence was produced with TRACES_ISOLATION=off; such a snapshot is "
                                               "never acceptance evidence (D-026)")


class HeadInfo(Strict):
    repo_id: str
    default_branch: str | None
    latest_sha: str | None
    displayed_sha: str | None
    behind: bool | None = Field(None, description="true when the latest discovered commit differs from the newest ready snapshot")
    checked_at: str


class JobEvent(Strict):
    at: str
    phase: JobPhase
    level: Literal["info", "warning", "error"]
    message: str


class Job(Strict):
    id: str
    repo_id: str
    snapshot_id: str | None
    kind: Literal["index", "reindex", "history", "baseline"]
    state: JobState
    phase: JobPhase
    progress: float = Field(ge=0, le=1)
    message: str | None = None
    error: ErrorBody | None = None
    version: int = Field(description="increments on every change; equals the ETag")
    created_at: str
    updated_at: str
    events: list[JobEvent] = []


class IndexJobCreate(Strict):
    sha: str | None = Field(None, description="full SHA; default: latest discovered HEAD")
    reindex: bool = False


HiddenCounts = dict[str, int]


class ClaimSummary(Strict):
    claim_id: str
    claim_kind: str
    kind: str | None
    status: Status
    label: Label
    class_: str = Field(alias="class")
    evidence_scope: str
    from_symbol: str | None = None
    to_symbol: str | None = None
    statement: str
    qualifier: str | None = None
    flags: list[str] = Field([], description="record flags; injected records also carry injected_control")
    injected: bool | None = Field(None, description="true for an injected negative control (Task 002 regression fixture): fed to the "
                                              "validators to prove they reject it, never a statement about the repository")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ClaimPage(Strict):
    items: list[ClaimSummary]
    total: int
    offset: int
    limit: int
    hidden_counts: HiddenCounts = Field(description="records excluded by the status filter, by status (rejected hidden unless include_rejected)")


class Component(Strict):
    id: str
    name: str
    layer: Literal["frontend", "api", "backend", "library", "data", "infra", "docs", "tests", "other"] = Field(
        description="library: code of a repository that declares a package and has no application framework or entrypoint "
                    "(D-029); otherwise the path-and-extension rule")
    kind: str
    paths: list[str]
    rule: str = Field(description="deterministic grouping rule that produced this component")
    claim_counts: dict[str, int]
    reason: str | None = Field(None, description="why this layer: the counted files and rule behind it (D-029); null for "
                                                 "snapshots indexed before D-029")


class RouteItem(Strict):
    method: str
    path: str
    handler_symbol: str | None
    operation_id: str | None
    file: str
    line: int
    status: Status
    claim_id: str | None
    flags: list[str] = []
    label: str | None = Field(None, description="the route's name exactly as the extractor recorded it (e.g. 'GET /items'), for "
                                                 "display; null when none was recorded. Never synthesized")


class OverviewFact(Strict):
    text: str
    kind: Literal["fact", "interpretation", "unknown"]
    claim_ids: list[str] = []


class Overview(Strict):
    snapshot_id: str
    business: list[OverviewFact]
    architecture: list[OverviewFact]
    implementation: list[OverviewFact]
    entry_points: list[OverviewFact]
    start_here: list[OverviewFact]
    languages: dict[str, int]
    counts: dict[str, int]


class GraphNode(Strict):
    id: str
    label: str
    entity: Literal["symbol", "file", "component", "route", "operation", "commit", "dependency", "repo"]
    layer: str | None = None
    file: str | None = None
    degree: int = 0


class GraphEdge(Strict):
    id: str = Field(description="claim_id")
    source: str
    target: str
    kind: str
    status: Status
    label: Label
    qualifier: str | None = None
    flags: list[str] = Field([], description="record flags; injected records also carry injected_control")
    injected: bool | None = Field(None, description="true for an injected negative control, never a statement about the repository; always sent")


class GraphResponse(Strict):
    snapshot_id: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    hidden_counts: HiddenCounts = Field(description="edges hidden by the status filter, by status, scoped like the edges: the "
                                                    "filtered snapshot when unfocused, the focused neighbourhood or component otherwise")
    truncated: bool
    truncated_counts: dict[str, int] | None = Field(None, description="edges matched but cut by `limit`, by status (empty when not truncated)")
    limit: int


class SourceView(Strict):
    snapshot_id: str
    sha: str
    path: str
    blob_sha: str
    start_line: int
    end_line: int
    total_lines: int
    lines: list[str]
    generated: bool
    claim_ids: list[str] = Field(description="claims with a location overlapping the returned range")


class TraceHop(Strict):
    index: int
    type: Literal["edge", "gap", "library_contract"]
    claim_id: str | None = Field(None, description="null only for gap hops")
    from_symbol: str
    to_symbol: str
    kind: str
    status: Status | None
    label: Label
    reason: str | None = Field(None, description="required for gap and library_contract hops (both are inferred)")
    qualifier: str | None = None
    evidence_scope: Literal["static"] = "static"
    injected: bool | None = Field(None, description="true when the hop is an injected negative control, never a repository fact; sent for edge hops")
    hidden_rejected: int | None = Field(None, description="gap hops only: rejected relationships leaving this step that the request hides "
                                                    "(include_rejected=false); the reason text states all hidden counts")


class TraceResponse(Strict):
    snapshot_id: str
    from_symbol: str
    to_symbol: str | None
    hops: list[TraceHop]
    hidden_counts: HiddenCounts
    complete: bool = Field(description="false when the trace contains gaps")
    disclaimer: str = "Static analysis only. No runtime behavior has been observed."


class ExplainRequest(Strict):
    question: str = Field(max_length=2000)
    focus_claim_ids: list[str] = []
    mode: Literal["no_llm", "prepare_bundle"] = "no_llm"


class Citation(Strict):
    claim_id: str
    status: Status
    label: Label
    file: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    commit: str | None = None


class OutboundItem(Strict):
    kind: Literal["claim_statement", "source_snippet", "history_quote", "question", "instructions"]
    claim_id: str | None = None
    file: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    chars: int
    sha256: str


class ExplainResponse(Strict):
    snapshot_id: str
    answer: list[OverviewFact] = Field(description="deterministic, template-built answer from evidence (no LLM)")
    citations: list[Citation]
    categories: dict[str, list[str]] = Field(description="code_structure | history_patterns | documented_decisions | inference | runtime_observations -> claim ids")
    prompt_bundle: dict[str, Any] | None = Field(None, description="mode=prepare_bundle: scoped prompt for the browser to send after consent; keys never reach the backend")
    outbound_manifest: list[OutboundItem] = Field(default=[], description="exactly what the bundle would send to a provider")
    requires_consent: bool = True
