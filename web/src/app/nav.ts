// Snapshot navigation (IA.md section 3). `primary` items form the phone bottom bar; the rest live in the More sheet.
export interface NavItem {
  to: string; // relative to the snapshot base
  label: string;
  primary: boolean;
  capability?: string;
}

export const SNAPSHOT_NAV: readonly NavItem[] = [
  { to: "", label: "Overview", primary: true, capability: "overview" },
  { to: "graph", label: "Graph", primary: true, capability: "graph" },
  { to: "trace", label: "Trace", primary: true, capability: "trace" },
  { to: "history", label: "History", primary: true, capability: "history" },
  { to: "ask", label: "Ask", primary: true, capability: "explain" },
  { to: "components", label: "Components", primary: false, capability: "components" },
  { to: "routes", label: "Routes", primary: false, capability: "routes" },
  { to: "claims", label: "Claims", primary: false, capability: "claims" },
  { to: "review", label: "Review", primary: false, capability: "claims" },
];

export const snapshotBase = (repoId: string, sha: string) => `/r/${encodeURIComponent(repoId)}/s/${sha}`;
export const shortSha = (sha: string) => sha.slice(0, 7);
