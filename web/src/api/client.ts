// Typed API client. Types come from docs/contracts/openapi.json via `npm run gen:api` (src/api/schema.d.ts).
import type { components } from "./schema";

export type Schemas = components["schemas"];
export type Repo = Schemas["Repo"];
export type Snapshot = Schemas["Snapshot"];
export type ClaimPage = Schemas["ClaimPage"];
export type ClaimSummary = Schemas["ClaimSummary"];
export type GraphResponse = Schemas["GraphResponse"];
export type GraphNode = Schemas["GraphNode"];
export type GraphEdge = Schemas["GraphEdge"];
export type ErrorBody = Schemas["ErrorBody"];
export type Health = Schemas["Health"];
export type Meta = Schemas["Meta"];
export type Job = Schemas["Job"];
export type HeadInfo = Schemas["HeadInfo"];
export type Overview = Schemas["Overview"];
export type Component = Schemas["Component"];
export type RouteItem = Schemas["RouteItem"];
export type SourceView = Schemas["SourceView"];
export type TraceResponse = Schemas["TraceResponse"];
export type TraceHop = Schemas["TraceHop"];
export type Citation = Schemas["Citation"];
export type OutboundItem = Schemas["OutboundItem"];
export type ExplainRequest = Schemas["ExplainRequest"];
export type ExplainResponse = Schemas["ExplainResponse"];
export type IndexJobCreate = Schemas["IndexJobCreate"];
export type HiddenCounts = Record<string, number>;

export class ApiError extends Error {
  constructor(
    public status: number,
    public body: ErrorBody,
  ) {
    super(body.message);
    this.name = "ApiError";
  }
  /** 501 with the contract's error envelope: the endpoint exists but is owned by a seat that has not shipped it. */
  get notImplemented(): boolean {
    return this.status === 501 && this.body.code === "not_implemented";
  }
}

export const API_BASE = "/api/v1";

async function parseError(res: Response): Promise<ApiError> {
  let err: ErrorBody = { code: "http_error", message: `HTTP ${res.status}` };
  try {
    const j = (await res.json()) as { error?: ErrorBody };
    if (j && j.error) err = j.error;
  } catch {
    /* non-JSON error body */
  }
  return new ApiError(res.status, err);
}

export async function request<T>(method: string, path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: body === undefined ? { Accept: "application/json" } : { Accept: "application/json", "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  if (!res.ok) throw await parseError(res);
  return (await res.json()) as T;
}

export interface JobPoll {
  job: Job;
  etag: string | null;
  /** True when the server answered 304 Not Modified and `job` is the previously seen version. */
  notModified: boolean;
}

/** Poll a job with ETag / If-None-Match (CONTRACTS.md 4.4). On 304 the previous job is returned unchanged. */
export async function pollJob(jobId: string, previous?: JobPoll, signal?: AbortSignal): Promise<JobPoll> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (previous?.etag) headers["If-None-Match"] = previous.etag;
  const res = await fetch(`${API_BASE}/jobs/${encodeURIComponent(jobId)}`, { headers, signal, cache: "no-store" });
  if (res.status === 304 && previous) return { ...previous, notModified: true };
  if (!res.ok) throw await parseError(res);
  return { job: (await res.json()) as Job, etag: res.headers.get("ETag"), notModified: false };
}

const enc = encodeURIComponent;

export function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") u.set(k, String(v));
  const s = u.toString();
  return s ? `?${s}` : "";
}

export const snapPath = (repoId: string, sha: string) => `/repos/${enc(repoId)}/snapshots/${enc(sha)}`;

export interface ClaimQuery {
  status?: string;
  claim_kind?: string;
  kind?: string;
  symbol?: string;
  file?: string;
  include_rejected?: boolean;
  offset?: number;
  limit?: number;
}

export const api = {
  health: () => request<Health>("GET", "/health"),
  meta: () => request<Meta>("GET", "/meta"),
  repos: () => request<Repo[]>("GET", "/repos"),
  repo: (repoId: string) => request<Repo>("GET", `/repos/${enc(repoId)}`),
  registerRepo: (url: string) => request<Repo>("POST", "/repos", { url }),
  head: (repoId: string) => request<HeadInfo>("GET", `/repos/${enc(repoId)}/head`),
  startIndex: (repoId: string, body: IndexJobCreate) => request<Job>("POST", `/repos/${enc(repoId)}/index-jobs`, body),
  snapshots: (repoId: string) => request<Snapshot[]>("GET", `/repos/${enc(repoId)}/snapshots`),
  snapshot: (repoId: string, sha: string) => request<Snapshot>("GET", snapPath(repoId, sha)),
  claims: (repoId: string, sha: string, q: ClaimQuery) => request<ClaimPage>("GET", `${snapPath(repoId, sha)}/claims${qs({ ...q })}`),
  /** Full traces-evidence/0.4 record. The OpenAPI schema leaves it open, so it is parsed defensively (see record.ts). */
  claim: (repoId: string, sha: string, claimId: string) => request<unknown>("GET", `${snapPath(repoId, sha)}/claims/${enc(claimId)}`),
  overview: (repoId: string, sha: string) => request<Overview>("GET", `${snapPath(repoId, sha)}/overview`),
  components: (repoId: string, sha: string) => request<Component[]>("GET", `${snapPath(repoId, sha)}/components`),
  routes: (repoId: string, sha: string) => request<RouteItem[]>("GET", `${snapPath(repoId, sha)}/routes`),
  /** `query` is built by graphQuery() so array filters repeat their key. */
  graph: (repoId: string, sha: string, query: string) => request<GraphResponse>("GET", `${snapPath(repoId, sha)}/graph${query}`),
  source: (repoId: string, sha: string, path: string, start?: number, end?: number) =>
    request<SourceView>("GET", `${snapPath(repoId, sha)}/source${qs({ path, start, end })}`),
  trace: (repoId: string, sha: string, from: string, to?: string) =>
    request<TraceResponse>("GET", `${snapPath(repoId, sha)}/trace${qs({ from, to })}`),
  historyTimeline: (repoId: string, sha: string) => request<ClaimPage>("GET", `${snapPath(repoId, sha)}/history/timeline`),
  explain: (repoId: string, sha: string, body: ExplainRequest) => request<ExplainResponse>("POST", `${snapPath(repoId, sha)}/explain`, body),
  /** Scoped prompt bundle for browser-side chat. The request never carries a provider key. */
  chatBundle: (repoId: string, sha: string, body: ExplainRequest) => request<ExplainResponse>("POST", `${snapPath(repoId, sha)}/chat/bundle`, body),
};
