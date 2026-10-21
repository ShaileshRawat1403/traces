// Defensive reading of the history parts of a traces-evidence/0.4 record (docs/contracts/history.md sections 5 to 7).
// Values are shown as the API sent them; nothing is computed from them except ordering and bar lengths.

export interface HistoryPath {
  path: string;
  old_path: string | null;
  status: string | null;
  similarity: number | null;
}
export interface HistoryCitation {
  commit: string;
  parents: string[];
  paths: HistoryPath[];
  pr: { number: number | null; merge_commit_sha: string | null; fetched_at: string | null } | null;
}
export interface HistoryExtras {
  /** The record's own echo of the criteria that produced it: {digest, values}, shown verbatim. */
  parameters: { digest: string | null; values: Record<string, unknown> } | null;
  metrics: Record<string, unknown> | null;
  citations: HistoryCitation[];
  review_state: { state: string; reviewer: string | null; at: string | null } | null;
}

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const str = (v: unknown) => (typeof v === "string" ? v : null);
const num = (v: unknown) => (typeof v === "number" && Number.isFinite(v) ? v : null);

export function readHistoryExtras(raw: unknown): HistoryExtras {
  const r = isObj(raw) ? raw : {};
  const p = isObj(r.parameters) ? r.parameters : null;
  const rs = isObj(r.review_state) ? r.review_state : null;
  const citations: HistoryCitation[] = [];
  for (const c of Array.isArray(r.citations) ? r.citations : []) {
    if (!isObj(c) || !str(c.commit)) continue;
    const pr = isObj(c.pr) ? { number: num(c.pr.number), merge_commit_sha: str(c.pr.merge_commit_sha), fetched_at: str(c.pr.fetched_at) } : null;
    citations.push({
      commit: c.commit as string,
      parents: (Array.isArray(c.parents) ? c.parents : []).filter((x): x is string => typeof x === "string"),
      paths: (Array.isArray(c.paths) ? c.paths : []).filter(isObj).flatMap((x) =>
        str(x.path) ? [{ path: x.path as string, old_path: str(x.old_path), status: str(x.status), similarity: num(x.similarity) }] : [],
      ),
      pr,
    });
  }
  return {
    parameters: p ? { digest: str(p.digest), values: isObj(p.values) ? p.values : {} } : null,
    metrics: isObj(r.metrics) ? r.metrics : null,
    citations,
    review_state: rs && str(rs.state) ? { state: rs.state as string, reviewer: str(rs.reviewer), at: str(rs.at) } : null,
  };
}

/** A numeric metric, or null when absent or not a number (never coerced from strings). */
export const metric = (x: HistoryExtras | null | undefined, key: string): number | null => num(x?.metrics?.[key]);

/** Distinct parameter sets among records, keyed by digest (or by their canonical JSON when the digest is missing). */
export function distinctParameters(list: readonly (HistoryExtras | null | undefined)[]): { key: string; digest: string | null; values: Record<string, unknown>; count: number }[] {
  const m = new Map<string, { key: string; digest: string | null; values: Record<string, unknown>; count: number }>();
  for (const x of list) {
    if (!x?.parameters) continue;
    const key = x.parameters.digest ?? JSON.stringify(x.parameters.values);
    const cur = m.get(key);
    if (cur) cur.count += 1;
    else m.set(key, { key, digest: x.parameters.digest, values: x.parameters.values, count: 1 });
  }
  return [...m.values()].sort((a, b) => b.count - a.count || a.key.localeCompare(b.key));
}

const HISTORY_CLASSES = new Set(["git_object_fact", "history_pattern", "history_inferred", "documented_rationale", "snapshot_diff"]);
export const isHistoryClass = (cls: string | null | undefined) => !!cls && HISTORY_CLASSES.has(cls);

/**
 * Required wording next to a history status (history.md section 17). Observed on a pattern means the counts were
 * rechecked against Git, nothing more; rationale is a quote, not intent.
 */
export function historyNote(cls: string | null | undefined, status: string): string | null {
  if (cls === "history_pattern") return status === "observed" ? "History pattern. Count checked against Git, not a confirmed relationship." : "History pattern.";
  if (cls === "documented_rationale") return "Quoted rationale, not proof of intent.";
  if (cls === "history_inferred") return "Suggested from history, not established by Git.";
  if (cls === "snapshot_diff") return "Difference between two evidence snapshots.";
  if (cls === "git_object_fact") return status === "observed" ? "Git object fact, checked against Git." : null;
  return null;
}
