import { useQueries } from "@tanstack/react-query";
import { api, type ClaimPage, type ClaimSummary } from "../../api/client";
import { keys } from "../../api/queries";
import { presentStatus } from "../../status/status";
import { HiddenCounts } from "../../ui/HiddenCounts";
import { Button } from "../../ui/States";
import { StatusChip } from "../../ui/StatusChip";
import { historyNote, readHistoryExtras, type HistoryExtras } from "./historyRecord";

/** Full records for the shown items (citations, parameters, metrics live on the record). Capped per page. */
export const RECORD_CAP = 50;

export function useHistoryRecords(repoId: string, sha: string, items: readonly ClaimSummary[] | undefined) {
  const ids = (items ?? []).slice(0, RECORD_CAP).map((i) => i.claim_id);
  const qs = useQueries({
    queries: ids.map((id) => ({ queryKey: keys.claim(repoId, sha, id), queryFn: () => api.claim(repoId, sha, id), staleTime: Infinity })),
  });
  const byId = new Map<string, HistoryExtras>();
  qs.forEach((q, i) => {
    if (q.data) byId.set(ids[i]!, readHistoryExtras(q.data));
  });
  return { byId, loading: qs.some((q) => q.isPending), failed: qs.filter((q) => q.isError).length };
}

export const shortSha = (s: string) => s.slice(0, 7);

function Commits({ x }: { x: HistoryExtras | undefined }) {
  if (!x || x.citations.length === 0) return null;
  const last = x.citations.slice(-3);
  return (
    <p className="text-xs text-ink-2" data-testid="history-commits">
      {x.citations.length === 1 ? "Cites commit " : `Cites ${x.citations.length} commits, last three: `}
      {last.map((c, i) => (
        <span key={c.commit}>
          {i ? ", " : ""}
          <code>{shortSha(c.commit)}</code>
          {c.pr?.number ? ` (PR #${c.pr.number})` : ""}
        </span>
      ))}
    </p>
  );
}

export function ReviewState({ x }: { x: HistoryExtras | undefined }) {
  const rs = x?.review_state;
  if (!rs) return null;
  const text = rs.state === "confirmed" ? `confirmed by ${rs.reviewer ?? "a reviewer"}` : rs.state === "disputed" ? `disputed by ${rs.reviewer ?? "a reviewer"}` : "suggested, not confirmed";
  return <span className="text-xs text-ink-2">Review: {text}.</span>;
}

export function HistoryItem({ item, x, onEvidence, children, eyebrow }: { item: ClaimSummary; x: HistoryExtras | undefined; onEvidence: (id: string) => void; children?: React.ReactNode; eyebrow?: React.ReactNode }) {
  const note = historyNote(item.class, item.status);
  const who = (item.from_symbol ?? "").replace(/^(file|component|commit|dep|repo)::/, "");
  return (
    <li className="flex flex-col gap-1 rounded-lg border border-line bg-surface p-3" data-testid="history-item" data-class={item.class}>
      {eyebrow}
      <span className="flex flex-wrap items-center gap-2">
        <StatusChip status={item.status} label={item.label} flags={item.flags} qualifier={item.qualifier} context={item.status === "rejected" ? "reviewer" : "default"} />
        {item.kind ? <span className="text-xs text-muted">{item.kind.replace(/_/g, " ")}</span> : null}
        {who ? <span className="history-pill">{who}</span> : null}
      </span>
      <p className="break-words text-sm text-ink-2">{item.statement}</p>
      {note ? <p className="text-xs font-medium text-ink-2">{note}</p> : null}
      <Commits x={x} />
      <ReviewState x={x} />
      {children}
      <Button className="mt-1 self-start" onClick={() => onEvidence(item.claim_id)}>
        Open evidence
      </Button>
    </li>
  );
}

/** Items the default context may show; rejected items are counted, not listed (they stay in the reviewer view). */
export function visibleItems(page: ClaimPage) {
  const shown: ClaimSummary[] = [];
  const hidden: Record<string, number> = {};
  for (const i of page.items) {
    if (presentStatus(i, "default").hidden) hidden[i.status] = (hidden[i.status] ?? 0) + 1;
    else shown.push(i);
  }
  return { shown, hidden };
}

export function PageMeta({ page, hidden, reviewHref }: { page: ClaimPage; hidden: Record<string, number>; reviewHref: string }) {
  return (
    <div className="flex flex-col gap-1">
      <p className="text-sm text-muted" data-testid="history-summary">
        Showing {page.items.length ? `${page.offset + 1} to ${page.offset + page.items.length}` : "0"} of {page.total.toLocaleString("en-US")} records.
      </p>
      <HiddenCounts counts={page.hidden_counts} extra={hidden} reviewHref={reviewHref} />
    </div>
  );
}
