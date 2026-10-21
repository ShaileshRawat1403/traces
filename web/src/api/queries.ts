import { QueryClient, useQuery } from "@tanstack/react-query";
import { ApiError, api, type ClaimQuery } from "./client";

/** Contract answers (4xx, 501) are final. Network failures and other 5xx are retried twice. */
export function shouldRetry(count: number, err: unknown): boolean {
  if (count >= 2) return false;
  if (err instanceof ApiError) return err.status >= 500 && err.status !== 501;
  return true;
}

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        retry: shouldRetry,
      },
    },
  });
}

export const keys = {
  health: ["health"] as const,
  meta: ["meta"] as const,
  repos: ["repos"] as const,
  repo: (id: string) => ["repo", id] as const,
  head: (id: string) => ["head", id] as const,
  snapshots: (id: string) => ["snapshots", id] as const,
  snapshot: (id: string, sha: string) => ["snapshot", id, sha] as const,
  claims: (id: string, sha: string, q: ClaimQuery) => ["claims", id, sha, q] as const,
  claim: (id: string, sha: string, cid: string) => ["claim", id, sha, cid] as const,
  view: (name: string, id: string, sha: string, extra?: unknown) => ["view", name, id, sha, extra ?? null] as const,
};

export const useHealth = () => useQuery({ queryKey: keys.health, queryFn: api.health, staleTime: 60_000 });
export const useMeta = () => useQuery({ queryKey: keys.meta, queryFn: api.meta, staleTime: 300_000 });
export const useRepos = () => useQuery({ queryKey: keys.repos, queryFn: api.repos });
export const useRepo = (id: string) => useQuery({ queryKey: keys.repo(id), queryFn: () => api.repo(id) });
export const useHead = (id: string) => useQuery({ queryKey: keys.head(id), queryFn: () => api.head(id) });
export const useSnapshots = (id: string) => useQuery({ queryKey: keys.snapshots(id), queryFn: () => api.snapshots(id) });
export const useSnapshot = (id: string, sha: string) => useQuery({ queryKey: keys.snapshot(id, sha), queryFn: () => api.snapshot(id, sha) });
export const useClaims = (id: string, sha: string, q: ClaimQuery) =>
  useQuery({ queryKey: keys.claims(id, sha, q), queryFn: () => api.claims(id, sha, q), placeholderData: (prev) => prev });
export const useClaim = (id: string, sha: string, cid: string) => useQuery({ queryKey: keys.claim(id, sha, cid), queryFn: () => api.claim(id, sha, cid) });

/** True when /meta says a capability is not implemented in this build (CONTRACTS.md 4.1). Unknown capabilities return null. */
export function useCapability(name: string): boolean | null {
  const meta = useMeta();
  const v = meta.data?.capabilities?.[name];
  return typeof v === "boolean" ? v : null;
}
