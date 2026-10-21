import { useId } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import type { ClaimQuery, ClaimSummary } from "../../api/client";
import { useClaims } from "../../api/queries";
import { snapshotBase } from "../../app/nav";
import { splitSymbol } from "../../api/record";
import { presentStatus, type Context } from "../../status/status";
import { HiddenCounts } from "../../ui/HiddenCounts";
import { Button, Empty, ErrorState, Loading, PageHeader } from "../../ui/States";
import { StatusChip } from "../../ui/StatusChip";

const PAGE = 50;

/** Splits a page into what this context may show and what it must hide (rejected outside reviewer views). */
export function partitionForContext(items: ClaimSummary[], context: Context) {
  const shown: ClaimSummary[] = [];
  const hidden: Record<string, number> = {};
  for (const c of items) {
    if (presentStatus(c, context).hidden) hidden[c.status] = (hidden[c.status] ?? 0) + 1;
    else shown.push(c);
  }
  return { shown, hidden };
}

function Endpoints({ c }: { c: ClaimSummary }) {
  if (!c.from_symbol && !c.to_symbol) return null;
  const f = c.from_symbol ? splitSymbol(c.from_symbol) : null;
  const t = c.to_symbol ? splitSymbol(c.to_symbol) : null;
  return (
    <p className="mt-1 break-words text-sm">
      {f ? <span className="font-mono">{f.name}</span> : null}
      {c.kind ? <span className="mx-1 text-muted">{c.kind}</span> : null}
      {t ? <span className="font-mono">{t.name}</span> : null}
    </p>
  );
}

export function ClaimsPage({ reviewer = false }: { reviewer?: boolean }) {
  const { repoId = "", sha = "" } = useParams();
  const [sp, setSp] = useSearchParams();
  const ids = { status: useId(), kind: useId(), file: useId() };
  const context: Context = reviewer ? "reviewer" : "default";
  const offset = Math.max(0, Number(sp.get("offset") ?? 0) || 0);
  const q: ClaimQuery = {
    status: sp.get("status") ?? (reviewer ? "rejected" : undefined),
    kind: sp.get("kind") ?? undefined,
    file: sp.get("file") ?? undefined,
    include_rejected: reviewer,
    offset,
    limit: PAGE,
  };
  const claims = useClaims(repoId, sha, q);
  const base = snapshotBase(repoId, sha);
  const set = (k: string, v: string) => {
    const n = new URLSearchParams(sp);
    if (v) n.set(k, v);
    else n.delete(k);
    n.delete("offset");
    setSp(n, { replace: true });
  };
  const statuses = reviewer ? ["rejected", "unvalidated", "missing_location", "observed", "verified"] : ["verified", "observed", "unvalidated", "missing_location"];

  return (
    <>
      <PageHeader title={reviewer ? "Reviewer view" : "Claims"}>
        {reviewer
          ? "Rejected and uncertain claims, kept for audit. Rejected claims are never part of the architecture views."
          : "Every evidence record for this snapshot, with its own status. Rejected claims are excluded and counted."}
      </PageHeader>
      {reviewer ? (
        <p className="mb-4 rounded-md border border-rejected/40 bg-rejected-soft px-3 py-2 text-sm" role="note">
          Reviewer view. Rejected claims are shown for audit and are not part of the architecture.
        </p>
      ) : null}

      <form className="mb-4 grid gap-3 rounded-lg border border-line bg-surface p-3 sm:grid-cols-3" onSubmit={(e) => e.preventDefault()} aria-label="Claim filters">
        <div className="flex flex-col">
          <label htmlFor={ids.status} className="text-sm font-medium">
            Status
          </label>
          <select id={ids.status} className="tap rounded-md border border-line-strong bg-surface px-2" value={q.status ?? ""} onChange={(e) => set("status", e.target.value)}>
            <option value="">{reviewer ? "All statuses" : "All shown statuses"}</option>
            {statuses.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col">
          <label htmlFor={ids.kind} className="text-sm font-medium">
            Kind
          </label>
          <input id={ids.kind} className="tap rounded-md border border-line-strong px-2" defaultValue={q.kind ?? ""} placeholder="renders, imports, calls" onBlur={(e) => set("kind", e.target.value.trim())} onKeyDown={(e) => e.key === "Enter" && set("kind", e.currentTarget.value.trim())} />
        </div>
        <div className="flex flex-col">
          <label htmlFor={ids.file} className="text-sm font-medium">
            File
          </label>
          <input id={ids.file} className="tap rounded-md border border-line-strong px-2 font-mono text-sm" defaultValue={q.file ?? ""} placeholder="path/in/repo.py" onBlur={(e) => set("file", e.target.value.trim())} onKeyDown={(e) => e.key === "Enter" && set("file", e.currentTarget.value.trim())} />
        </div>
      </form>

      {claims.isPending ? (
        <Loading label="Loading claims" />
      ) : claims.isError ? (
        <ErrorState error={claims.error} what="Claims" />
      ) : (
        (() => {
          const page = claims.data;
          const { shown, hidden } = partitionForContext(page.items, context);
          return (
            <>
              <div className="mb-3 flex flex-col gap-1">
                <p className="text-sm" aria-live="polite">
                  {page.total.toLocaleString("en-US")} matching claims. Showing {page.total === 0 ? 0 : page.offset + 1} to {Math.min(page.offset + page.limit, page.total)}.
                </p>
                <HiddenCounts counts={page.hidden_counts} extra={hidden} reviewHref={reviewer ? undefined : `${base}/review`} />
              </div>
              {shown.length === 0 ? (
                <Empty title="No claims match these filters" />
              ) : (
                <ul className="flex flex-col gap-2" data-testid="claim-list">
                  {shown.map((c) => (
                    <li key={c.claim_id} className="rounded-lg border border-line bg-surface p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <StatusChip status={c.status} label={c.label} flags={c.flags} qualifier={c.qualifier} context={context} />
                        <span className="text-xs text-muted">
                          {c.claim_kind} · {c.class} · {c.evidence_scope}
                        </span>
                      </div>
                      <Endpoints c={c} />
                      <p className="mt-1 break-words text-sm text-ink-2">{c.statement}</p>
                      <Link to={`${base}/claim/${c.claim_id}`} className="tap -mb-2 inline-flex items-center text-sm" aria-label={`Open evidence for claim ${c.claim_id.slice(0, 12)}`}>
                        Open evidence
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
              <nav className="mt-4 flex items-center justify-between gap-2" aria-label="Pagination">
                <Button disabled={offset === 0} onClick={() => setSp((p) => { const n = new URLSearchParams(p); n.set("offset", String(Math.max(0, offset - PAGE))); return n; })}>
                  Previous
                </Button>
                <Button disabled={offset + PAGE >= page.total} onClick={() => setSp((p) => { const n = new URLSearchParams(p); n.set("offset", String(offset + PAGE)); return n; })}>
                  Next
                </Button>
              </nav>
            </>
          );
        })()
      )}
    </>
  );
}
