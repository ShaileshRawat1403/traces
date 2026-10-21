"""Traces read-only query/index API (FastAPI). Contract: docs/CONTRACTS.md section 4; generated OpenAPI: docs/contracts/openapi.json.

FOUNDATION implements health/meta, repo registration and listing, snapshots, claims (list, by id) and export from the
store, and job polling with ETag. Every other endpoint is declared with its final request/response models and returns
HTTP 501 with an explicit not_implemented error naming the owning seat. Nothing returns placeholder data."""
from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from functools import lru_cache
from typing import Annotated, Any, NoReturn

from fastapi import Depends, FastAPI, Header, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse

from traces import __version__
from traces.api.models import (
    ClaimPage,
    ClaimSummary,
    Component,
    ErrorBody,
    ErrorResponse,
    ExplainRequest,
    ExplainResponse,
    GraphResponse,
    HeadInfo,
    Health,
    IndexJobCreate,
    Job,
    Meta,
    Overview,
    Repo,
    RepoCreate,
    RouteItem,
    Snapshot,
    SourceView,
    Status,
    TraceResponse,
)
from traces.core.config import get_settings
from traces.evidence.jobs import IndexJobRunner
from traces.evidence.migrate import CURRENT, SCHEMAS
from traces.evidence.store import Store, get_job, now
from traces.explain import bundle as explain_bundle
from traces.ingest.errors import IngestError
from traces.ingest.remote import HeadProbe
from traces.ingest.urls import parse_repo_url, require_sha

API = "/api/v1"
STATUSES = ("verified", "observed", "unvalidated", "missing_location", "rejected")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, owner: str | None = None, milestone: str | None = None,
                 detail: dict[str, Any] | None = None):
        self.status, self.body = status, {"error": {"code": code, "message": message, "owner": owner, "milestone": milestone, "detail": detail}}


def not_implemented(what: str, owner: str, milestone: str) -> NoReturn:
    raise ApiError(501, "not_implemented", f"{what} is not implemented in this build", owner=owner, milestone=milestone)


ERR: dict[int | str, dict[str, Any]] = {404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}
UPSTREAM: dict[int | str, dict[str, Any]] = {
    429: {"model": ErrorResponse, "description": "rate_limited (HEAD discovery called too often; Retry-After set)"},
    502: {"model": ErrorResponse, "description": "upstream_unavailable or fetch_failed (GitHub unreachable)"},
    504: {"model": ErrorResponse, "description": "fetch_timeout"}, **ERR}
NI: dict[int | str, dict[str, Any]] = {501: {"model": ErrorResponse, "description": "Not implemented in this build (error.code = not_implemented)"}, **ERR}

app = FastAPI(title="Traces API", version=__version__,
              description="Read-only evidence query and index API for Traces. Static analysis only; no runtime behavior is observed. "
                          "Evidence records follow traces-evidence/0.4.")


@app.exception_handler(ApiError)
async def _api_error(_: Request, e: ApiError) -> JSONResponse:
    return JSONResponse(e.body, status_code=e.status)


@app.exception_handler(IngestError)
async def _ingest_error(_: Request, e: IngestError) -> JSONResponse:
    headers = {"Retry-After": str(int((e.detail or {}).get("retry_after_s", 5)) + 1)} if e.code == "rate_limited" else None
    return JSONResponse({"error": {"code": e.code, "message": e.message, "owner": None, "milestone": None, "detail": e.detail}},
                        status_code=e.http_status, headers=headers)


@app.exception_handler(RequestValidationError)
async def _validation_error(_: Request, e: RequestValidationError) -> JSONResponse:
    return JSONResponse({"error": {"code": "invalid_request", "message": "request validation failed", "owner": None, "milestone": None,
                                   "detail": {"errors": json.loads(json.dumps(e.errors(), default=str))}}}, status_code=422)


@lru_cache(maxsize=1)
def _default_store() -> Store:
    return Store(get_settings().db_path)


def get_store() -> Store:
    return _default_store()


StoreDep = Annotated[Store, Depends(get_store)]


@lru_cache(maxsize=1)
def _default_probe() -> HeadProbe:
    return HeadProbe()


def get_head_probe() -> HeadProbe:
    """Anonymous, cached, rate-limited HEAD discovery (overridden in tests: they never touch the network)."""
    return _default_probe()


ProbeDep = Annotated[HeadProbe, Depends(get_head_probe)]


@lru_cache(maxsize=1)
def _default_runner() -> IndexJobRunner:
    return IndexJobRunner(_default_store())


def get_index_runner() -> IndexJobRunner:
    """In-process index job runner bound to the default store (tests inject one with a stub pipeline)."""
    return _default_runner()


RunnerDep = Annotated[IndexJobRunner, Depends(get_index_runner)]


def _repo(st: Store, repo_id: str) -> dict[str, Any]:
    r = st.get_repo(repo_id)
    if r is None:
        raise ApiError(404, "not_found", f"repo {repo_id} not found")
    return r


def _snapshot(st: Store, repo_id: str, sha: str) -> dict[str, Any]:
    _repo(st, repo_id)
    try:
        require_sha(sha)
    except ValueError as e:
        raise ApiError(422, "invalid_sha", str(e)) from None
    s = st.get_snapshot(f"{repo_id}@{sha}")
    if s is None:
        raise ApiError(404, "not_found", f"snapshot {repo_id}@{sha} not found")
    return s


def _snapshot_out(s: dict[str, Any]) -> Snapshot:
    return Snapshot(id=s["id"], repo_id=s["repo_id"], sha=s["sha"], state=s["state"], evidence_schema=s["evidence_schema"],
                    extractor=json.loads(s["extractor_json"]), languages=json.loads(s["languages_json"]), frameworks=json.loads(s["frameworks_json"]),
                    generated_paths=json.loads(s["generated_paths_json"]), stats=json.loads(s["stats_json"]), created_at=s["created_at"],
                    indexed_at=s["indexed_at"])


# ------------------------------------------------------------------------------------------------ service
@app.get(f"{API}/health", response_model=Health, tags=["service"])
def health(st: StoreDep) -> Health:
    return Health(status="ok", version=__version__, store_migration=st.schema_version())


@app.get(f"{API}/meta", response_model=Meta, tags=["service"])
def meta() -> Meta:
    s = get_settings()
    return Meta(version=__version__, evidence_schema=CURRENT, evidence_schemas_readable=sorted(SCHEMAS),
                extractor={"codegraph": "@colbymchenry/codegraph@1.6.2"},
                validators={"python": "cpython-3.14 ast", "typescript": "typescript@6.0.3 compiler api"},
                isolation="none" if s.isolation == "none" else "unshare",
                capabilities={"repos": True, "snapshots": True, "claims": True, "export": True, "jobs_poll": True,
                              "index_jobs": True, "head": True, "overview": False, "components": False, "routes": False,
                              "graph": False, "source": False, "trace": False, "history": False, "compare": False,
                              "explain": True, "chat_bundle": True})


# ------------------------------------------------------------------------------------------------ repos and snapshots
@app.post(f"{API}/repos", response_model=Repo, status_code=201, responses=UPSTREAM, tags=["repos"])
def register_repo(body: RepoCreate, st: StoreDep, probe: ProbeDep) -> Repo:
    """Validate a public GitHub URL, confirm anonymously that it is public (credential-free `git ls-remote`), record the
    default branch and HEAD, and pin a snapshot (state `pending`) at `sha` or, when omitted, at the discovered HEAD.
    Nothing is cloned here; indexing is a separate job. A private, missing or renamed repository gives 422 repo_not_public."""
    try:
        ref = parse_repo_url(body.url)
    except ValueError as e:
        raise ApiError(422, "invalid_repo_url", str(e)) from None
    if body.sha is not None:
        try:
            require_sha(body.sha)
        except ValueError as e:
            raise ApiError(422, "invalid_sha", str(e)) from None
    head = probe.head(ref, max_age_s=0)
    st.upsert_repo(ref.cache_key, ref.host, ref.owner, ref.name, f"https://github.com/{ref.slug}")
    st.record_remote_head(ref.cache_key, head.sha, head.default_branch, head.checked_at)
    st.ensure_snapshot(ref.cache_key, body.sha or head.sha)
    return Repo(**_repo(st, ref.cache_key))


@app.get(f"{API}/repos", response_model=list[Repo], tags=["repos"])
def list_repos(st: StoreDep) -> list[Repo]:
    return [Repo(**r) for r in st.list_repos()]


@app.get(f"{API}/repos/{{repo_id}}", response_model=Repo, responses=ERR, tags=["repos"])
def get_repo(repo_id: str, st: StoreDep) -> Repo:
    return Repo(**_repo(st, repo_id))


@app.get(f"{API}/repos/{{repo_id}}/head", response_model=HeadInfo, responses=UPSTREAM, tags=["repos"])
def repo_head(repo_id: str, st: StoreDep, probe: ProbeDep) -> HeadInfo:
    """Latest discovered commit on the default branch vs. the displayed snapshot (the newest ready one). Anonymous
    `git ls-remote`, cached for 60 s per repo and rate limited (429 rate_limited only when nothing is cached)."""
    r = _repo(st, repo_id)
    ref = parse_repo_url(r["url"])
    head = probe.head(ref)
    st.record_remote_head(repo_id, head.sha, head.default_branch, head.checked_at)
    shown = st.newest_ready_snapshot(repo_id)
    displayed = shown["sha"] if shown else None
    return HeadInfo(repo_id=repo_id, default_branch=head.default_branch, latest_sha=head.sha, displayed_sha=displayed,
                    behind=None if displayed is None else displayed != head.sha, checked_at=head.checked_at or now())


@app.get(f"{API}/repos/{{repo_id}}/snapshots", response_model=list[Snapshot], responses=ERR, tags=["snapshots"])
def list_snapshots(repo_id: str, st: StoreDep) -> list[Snapshot]:
    _repo(st, repo_id)
    return [_snapshot_out(s) for s in st.list_snapshots(repo_id)]


@app.get(f"{API}/repos/{{repo_id}}/snapshots/{{sha}}", response_model=Snapshot, responses=ERR, tags=["snapshots"])
def get_snapshot(repo_id: str, sha: str, st: StoreDep) -> Snapshot:
    return _snapshot_out(_snapshot(st, repo_id, sha))


# ------------------------------------------------------------------------------------------------ jobs
def _job_out(j: dict[str, Any]) -> Job:
    err = ErrorBody(code=j["error_code"], message=j["error_detail"] or j["error_code"], owner=None, milestone=None, detail=None) if j["error_code"] else None
    return Job(id=j["id"], repo_id=j["repo_id"], snapshot_id=j["snapshot_id"], kind=j["kind"], state=j["state"], phase=j["phase"],
               progress=j["progress"], message=j["message"], error=err, version=j["version"], created_at=j["created_at"],
               updated_at=j["updated_at"], events=j["events"])


@app.post(f"{API}/repos/{{repo_id}}/index-jobs", response_model=Job, status_code=202,
          responses={409: {"model": ErrorResponse, "description": "already_indexed (the snapshot is ready; send reindex=true)"}, **UPSTREAM},
          tags=["jobs"])
def create_index_job(repo_id: str, body: IndexJobCreate, st: StoreDep, probe: ProbeDep, runner: RunnerDep, response: Response) -> Job:
    """Start an index job for `sha` (default: the latest discovered HEAD, discovered now if unknown). Returns the job
    (202); an index already queued or running for the same snapshot is returned instead of a duplicate. Poll
    GET /jobs/{id} with If-None-Match. Phases: fetching, checking_out, indexing, adapting, validating, storing, history."""
    r = _repo(st, repo_id)
    ref = parse_repo_url(r["url"])
    if body.sha is not None:
        try:
            sha = require_sha(body.sha)
        except ValueError as e:
            raise ApiError(422, "invalid_sha", str(e)) from None
    else:
        sha = r["latest_discovered_sha"]
        if not sha:
            head = probe.head(ref)
            st.record_remote_head(repo_id, head.sha, head.default_branch, head.checked_at)
            sha = head.sha
    snap = st.get_snapshot(f"{repo_id}@{sha}")
    if snap and snap["state"] == "ready" and not body.reindex and not st.active_job(snap["id"]):
        raise ApiError(409, "already_indexed", f"{snap['id']} is already indexed; send reindex=true to index it again",
                       detail={"snapshot_id": snap["id"]})
    j = runner.submit(ref, sha, "reindex" if body.reindex else "index")
    response.headers["Location"] = f"{API}/jobs/{j['id']}"
    return _job_out(get_job(st, j["id"]) or j)


@app.get(f"{API}/jobs/{{job_id}}", response_model=Job, responses={304: {"description": "Not modified (If-None-Match matched the ETag)"}, **ERR},
         tags=["jobs"])
def poll_job(job_id: str, st: StoreDep, response: Response,
             if_none_match: Annotated[str | None, Header()] = None) -> Any:
    """Poll a job. ETag is the job version; send If-None-Match to get 304 when nothing changed. Poll every 1-2 s. No SSE."""
    j = get_job(st, job_id)
    if j is None:
        raise ApiError(404, "not_found", f"job {job_id} not found")
    etag = f'"{j["version"]}"'
    if if_none_match is not None and if_none_match.strip() == etag:
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": "no-cache"})
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "no-cache"
    return _job_out(j)


# ------------------------------------------------------------------------------------------------ claims and export
SNAP = f"{API}/repos/{{repo_id}}/snapshots/{{sha}}"


@app.get(f"{SNAP}/claims", response_model=ClaimPage, responses=ERR, tags=["evidence"])
def list_claims(repo_id: str, sha: str, st: StoreDep,
                status: Annotated[list[Status] | None, Query()] = None,
                claim_kind: str | None = None,
                kind: str | None = None, symbol: str | None = None, file: str | None = None,
                include_rejected: bool = False,
                offset: Annotated[int, Query(ge=0)] = 0, limit: Annotated[int, Query(ge=1, le=500)] = 100) -> ClaimPage:
    """List claims. Rejected claims are excluded unless include_rejected=true (reviewer view); hidden_counts reports what was excluded."""
    snap = _snapshot(st, repo_id, sha)
    allowed: set[str] = set(status) if status else {s for s in STATUSES if s != "rejected"}
    if include_rejected:
        allowed.add("rejected")
    where, args = [], []
    if claim_kind:
        where.append("claim_kind=?"); args.append(claim_kind)  # noqa: E702
    if kind:
        where.append("kind=?"); args.append(kind)  # noqa: E702
    if symbol:
        where.append("(from_symbol=? OR to_symbol=?)"); args += [symbol, symbol]  # noqa: E702
    if file:
        where.append("(from_file=? OR to_file=?)"); args += [file, file]  # noqa: E702
    base = (" AND " + " AND ".join(where)) if where else ""
    counts = st.status_counts(snap["id"], base, tuple(args))
    hidden = {s: c for s, c in counts.items() if s not in allowed}
    ph = ",".join("?" * len(allowed))
    q = f"SELECT record_json FROM claims WHERE snapshot_id=? {base} AND status IN ({ph}) ORDER BY claim_id LIMIT ? OFFSET ?"
    rows = st.db.execute(q, (snap["id"], *args, *sorted(allowed), limit, offset)).fetchall()
    items = []
    for (rj,) in rows:
        r = json.loads(rj)
        items.append(ClaimSummary.model_validate({
            "claim_id": r["claim_id"], "claim_kind": r["claim_kind"], "kind": r.get("relationship_kind") or r.get("node_kind"),
            "status": r["status"], "label": r["label"], "class": r["class"], "evidence_scope": r["evidence_scope"],
            "from_symbol": (r.get("from") or {}).get("symbol"), "to_symbol": (r.get("to") or {}).get("symbol"),
            "statement": r["statement"], "qualifier": r.get("qualifier"), "flags": r.get("flags", [])}))
    total = sum(c for s, c in counts.items() if s in allowed)
    return ClaimPage(items=items, total=total, offset=offset, limit=limit, hidden_counts=hidden)


@app.get(f"{SNAP}/claims/{{claim_id}}", responses=ERR, tags=["evidence"],
         response_description="The full traces-evidence/0.4 record (schema: backend/traces/evidence/schema/evidence_record.v0.4.schema.json)")
def get_claim(repo_id: str, sha: str, claim_id: str, st: StoreDep) -> dict[str, Any]:
    """Evidence by claim: the full record with locations, checks, status history and provenance. Rejected claims are returned
    (a deep link names them explicitly); the UI shows them only in reviewer and evidence views."""
    snap = _snapshot(st, repo_id, sha)
    r = st.get_claim(snap["id"], claim_id)
    if r is None:
        raise ApiError(404, "not_found", f"claim {claim_id} not found in {snap['id']}")
    return r


@app.get(f"{SNAP}/export", responses=ERR, tags=["evidence"], response_class=StreamingResponse,
         response_description="application/x-ndjson, one traces-evidence/0.4 record per line, sorted by claim_id")
def export(repo_id: str, sha: str, st: StoreDep) -> StreamingResponse:
    snap = _snapshot(st, repo_id, sha)

    def gen() -> Iterator[bytes]:
        for r in st.iter_claims(snap["id"]):
            yield (json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()

    name = f"traces-{snap['repo_id']}-{snap['sha'][:12]}.jsonl"
    return StreamingResponse(gen(), media_type="application/x-ndjson", headers={"Content-Disposition": f'attachment; filename="{name}"'})


# ------------------------------------------------------------------------------------------------ views (declared, not implemented)
@app.get(f"{SNAP}/overview", response_model=Overview, responses=NI, tags=["views"])
def overview(repo_id: str, sha: str, st: StoreDep) -> Overview:
    _snapshot(st, repo_id, sha)
    not_implemented("Overview", "Traces", "VIEWS")


@app.get(f"{SNAP}/components", response_model=list[Component], responses=NI, tags=["views"])
def components(repo_id: str, sha: str, st: StoreDep) -> list[Component]:
    _snapshot(st, repo_id, sha)
    not_implemented("Components", "Traces", "VIEWS")


@app.get(f"{SNAP}/routes", response_model=list[RouteItem], responses=NI, tags=["views"])
def routes(repo_id: str, sha: str, st: StoreDep) -> list[RouteItem]:
    _snapshot(st, repo_id, sha)
    not_implemented("Route inventory", "Traces", "VIEWS")


@app.get(f"{SNAP}/graph", response_model=GraphResponse, responses=NI, tags=["views"])
def graph(repo_id: str, sha: str, st: StoreDep,
          focus: str | None = None, depth: Annotated[int, Query(ge=0, le=4)] = 1,
          layer: Annotated[list[str] | None, Query()] = None, rel: Annotated[list[str] | None, Query()] = None,
          status: Annotated[list[Status] | None, Query()] = None, q: str | None = None,
          include_rejected: bool = False, limit: Annotated[int, Query(ge=1, le=2000)] = 300) -> GraphResponse:
    """Graph query: filters (layer, rel, status, q) and neighborhood (focus + depth). Rejected excluded unless include_rejected."""
    _snapshot(st, repo_id, sha)
    not_implemented("Graph query", "Traces", "VIEWS")


@app.get(f"{SNAP}/source", response_model=SourceView, responses=NI, tags=["views"])
def source(repo_id: str, sha: str, st: StoreDep, path: str, start: Annotated[int, Query(ge=1)] = 1,
           end: Annotated[int | None, Query(ge=1)] = None) -> SourceView:
    """Pinned source view at the snapshot SHA (read from Git objects, never from a working tree)."""
    _snapshot(st, repo_id, sha)
    not_implemented("Source view", "Traces", "VIEWS")


@app.get(f"{SNAP}/trace", response_model=TraceResponse, responses=NI, tags=["views"])
def trace(repo_id: str, sha: str, st: StoreDep, from_: Annotated[str, Query(alias="from")],
          to: str | None = None, include_rejected: bool = False) -> TraceResponse:
    """Cross-layer trace as ordered hops: edge, gap and library_contract (gap and library_contract are inferred with a reason)."""
    _snapshot(st, repo_id, sha)
    not_implemented("Trace", "Traces", "VIEWS")


# ------------------------------------------------------------------------------------------------ history (Traces History seat)
HIST = "Traces History"


@app.get(f"{SNAP}/history/timeline", response_model=ClaimPage, responses=NI, tags=["history"])
def history_timeline(repo_id: str, sha: str, st: StoreDep, path: str | None = None, component: str | None = None,
                     offset: Annotated[int, Query(ge=0)] = 0, limit: Annotated[int, Query(ge=1, le=500)] = 100) -> ClaimPage:
    _snapshot(st, repo_id, sha)
    not_implemented("History timeline", HIST, "HISTORY")


@app.get(f"{SNAP}/history/lifecycle", response_model=ClaimPage, responses=NI, tags=["history"])
def history_lifecycle(repo_id: str, sha: str, st: StoreDep, path: str) -> ClaimPage:
    _snapshot(st, repo_id, sha)
    not_implemented("File lifecycle", HIST, "HISTORY")


@app.get(f"{SNAP}/history/hotspots", response_model=ClaimPage, responses=NI, tags=["history"])
def history_hotspots(repo_id: str, sha: str, st: StoreDep, level: Annotated[str, Query(pattern="^(file|component)$")] = "file") -> ClaimPage:
    _snapshot(st, repo_id, sha)
    not_implemented("Hotspots", HIST, "HISTORY")


@app.get(f"{SNAP}/history/cochange", response_model=ClaimPage, responses=NI, tags=["history"])
def history_cochange(repo_id: str, sha: str, st: StoreDep, target: str | None = None,
                     level: Annotated[str, Query(pattern="^(file|component)$")] = "file") -> ClaimPage:
    _snapshot(st, repo_id, sha)
    not_implemented("Co-change", HIST, "HISTORY")


@app.get(f"{SNAP}/history/milestones", response_model=ClaimPage, responses=NI, tags=["history"])
def history_milestones(repo_id: str, sha: str, st: StoreDep) -> ClaimPage:
    _snapshot(st, repo_id, sha)
    not_implemented("Milestones", HIST, "HISTORY")


@app.get(f"{SNAP}/history/rationale", response_model=ClaimPage, responses=NI, tags=["history"])
def history_rationale(repo_id: str, sha: str, st: StoreDep, target: str | None = None) -> ClaimPage:
    _snapshot(st, repo_id, sha)
    not_implemented("Documented rationale", HIST, "HISTORY")


@app.get(f"{API}/repos/{{repo_id}}/compare", response_model=ClaimPage, responses=NI, tags=["history"])
def compare(repo_id: str, base: str, head: str, st: StoreDep) -> ClaimPage:
    _repo(st, repo_id)
    not_implemented("Snapshot compare", HIST, "HISTORY")


# ------------------------------------------------------------------------------------------------ explain and chat (Traces UI seat, D-023)
def _explain(fn: Callable[..., dict[str, Any]], what: str, repo_id: str, sha: str, body: ExplainRequest, st: Store) -> ExplainResponse:
    """Calls the deterministic explain engine (traces.explain.bundle) on the resolved snapshot. No LLM call and no provider
    credentials: prepare_bundle only returns the scoped prompt and outbound manifest for the browser to send after consent."""
    snap = _snapshot(st, repo_id, sha)
    try:
        out = fn(snap["id"], body.question, body.focus_claim_ids, store=st)
    except NotImplementedError:
        not_implemented(what, "Traces UI", "EXPLAIN")
    except LookupError as e:
        raise ApiError(404, "not_found", str(e.args[0]) if e.args else f"not found in {snap['id']}") from None
    return ExplainResponse.model_validate(out)


@app.post(f"{SNAP}/explain", response_model=ExplainResponse, responses=ERR, tags=["explain"])
def explain(repo_id: str, sha: str, body: ExplainRequest, st: StoreDep) -> ExplainResponse:
    """No-LLM explanation, or (mode=prepare_bundle) a scoped prompt bundle with citations and an outbound manifest for the browser
    to send after user consent. The request model forbids extra fields, so provider keys cannot be submitted."""
    if body.mode == "prepare_bundle":
        return _explain(explain_bundle.prompt_bundle, "Explain", repo_id, sha, body, st)
    return _explain(explain_bundle.explain, "Explain", repo_id, sha, body, st)


@app.post(f"{SNAP}/chat/bundle", response_model=ExplainResponse, responses=ERR, tags=["explain"])
def chat_bundle(repo_id: str, sha: str, body: ExplainRequest, st: StoreDep) -> ExplainResponse:
    """Prompt bundle for browser-side chat (always prepare_bundle, whatever mode says); the backend never sees provider keys."""
    return _explain(explain_bundle.prompt_bundle, "Chat bundle", repo_id, sha, body, st)


def openapi_json() -> str:
    return json.dumps(app.openapi(), indent=1, sort_keys=True) + "\n"
