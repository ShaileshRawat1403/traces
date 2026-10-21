// Typed API client. Types come from docs/contracts/openapi.json via `npm run gen:api`.
import type { components } from "./schema";

export type Schemas = components["schemas"];
export type Repo = Schemas["Repo"];
export type Snapshot = Schemas["Snapshot"];
export type ClaimPage = Schemas["ClaimPage"];
export type ClaimSummary = Schemas["ClaimSummary"];
export type GraphResponse = Schemas["GraphResponse"];
export type ErrorBody = Schemas["ErrorBody"];
export type Health = Schemas["Health"];

export class ApiError extends Error {
  constructor(public status: number, public body: ErrorBody) {
    super(body.message);
  }
  get notImplemented(): boolean {
    return this.status === 501 && this.body.code === "not_implemented";
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api/v1${path}`, {
    method,
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    let err: ErrorBody = { code: "http_error", message: `HTTP ${res.status}` };
    try {
      const j = (await res.json()) as { error?: ErrorBody };
      if (j.error) err = j.error;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, err);
  }
  return (await res.json()) as T;
}

const enc = encodeURIComponent;
export const api = {
  health: () => request<Health>("GET", "/health"),
  repos: () => request<Repo[]>("GET", "/repos"),
  registerRepo: (url: string) => request<Repo>("POST", "/repos", { url }),
  snapshots: (repoId: string) => request<Snapshot[]>("GET", `/repos/${enc(repoId)}/snapshots`),
  claims: (repoId: string, sha: string, includeRejected: boolean, offset = 0) =>
    request<ClaimPage>(
      "GET",
      `/repos/${enc(repoId)}/snapshots/${enc(sha)}/claims?include_rejected=${includeRejected}&offset=${offset}&limit=100`,
    ),
  view: <T,>(repoId: string, sha: string, view: string) => request<T>("GET", `/repos/${enc(repoId)}/snapshots/${enc(sha)}/${view}`),
  graph: (repoId: string, sha: string) => request<GraphResponse>("GET", `/repos/${enc(repoId)}/snapshots/${enc(sha)}/graph`),
};
