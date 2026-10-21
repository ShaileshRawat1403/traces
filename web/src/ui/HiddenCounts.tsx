import { Link } from "react-router-dom";
import { statusName } from "../status/status";

export interface HiddenCountsProps {
  counts: Record<string, number> | null | undefined;
  /** Link to the reviewer view, offered when rejected claims are hidden. */
  reviewHref?: string;
  /** Extra items hidden on the client (for example rejected records that arrived in a non-reviewer view). */
  extra?: Record<string, number>;
}

/** Every filtered view states what it hides, by status (EVIDENCE_SCHEMA section 9, CONTRACTS.md 4). */
export function HiddenCounts({ counts, reviewHref, extra }: HiddenCountsProps) {
  const merged: Record<string, number> = { ...(counts ?? {}) };
  for (const [k, v] of Object.entries(extra ?? {})) merged[k] = (merged[k] ?? 0) + v;
  const entries = Object.entries(merged).filter(([, n]) => n > 0);
  if (entries.length === 0)
    return (
      <p className="text-sm text-muted" data-testid="hidden-counts">
        Nothing hidden by the current filters.
      </p>
    );
  const total = entries.reduce((a, [, n]) => a + n, 0);
  return (
    <p className="text-sm text-ink-2" data-testid="hidden-counts">
      <span className="font-semibold">Hidden by current filters: {total.toLocaleString("en-US")}</span>{" "}
      ({entries.map(([s, n]) => `${n.toLocaleString("en-US")} ${statusName(s)}`).join(", ")}).
      {merged.rejected && reviewHref ? (
        <>
          {" "}
          Rejected claims are kept for audit in the <Link to={reviewHref}>reviewer view</Link>.
        </>
      ) : null}
    </p>
  );
}
