import { useQuery } from "@tanstack/react-query";
import { useId } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type RouteItem } from "../../api/client";
import { keys, useClaims } from "../../api/queries";
import { splitSymbol } from "../../api/record";
import { snapshotBase } from "../../app/nav";
import { EXPECTED_LABEL, isStatus } from "../../status/status";
import { HiddenCounts } from "../../ui/HiddenCounts";
import { Button, Empty, ErrorState, Loading, PageHeader } from "../../ui/States";
import { StatusChip } from "../../ui/StatusChip";
import { EvidenceDrawer } from "../evidence/EvidenceDrawer";
import { useDrawerClaim, useParam } from "./useDrawer";

/** Filter over the fields the API returned. Plain substring match, case-insensitive, on path, handler and file. */
export function filterRoutes(items: readonly RouteItem[], text: string, method: string): RouteItem[] {
  const t = text.trim().toLowerCase();
  return items.filter(
    (r) => (!method || r.method === method) && (!t || [r.path, r.handler_symbol ?? "", r.file, r.operation_id ?? ""].some((v) => v.toLowerCase().includes(t))),
  );
}

export function RoutesView({ items, base, onEvidence, hidden }: { items: RouteItem[]; base: string; onEvidence: (id: string) => void; hidden?: Record<string, number> }) {
  const [text, setText] = useParam("q");
  const [method, setMethod] = useParam("method");
  const ids = { q: useId(), m: useId() };
  const methods = [...new Set(items.map((r) => r.method))].sort();
  const shown = filterRoutes(items, text, method);
  return (
    <section aria-label="Route inventory" data-testid="routes">
      <form role="search" className="mb-3 flex flex-wrap items-end gap-3 rounded-lg border border-line bg-surface p-3" onSubmit={(e) => e.preventDefault()}>
        <label htmlFor={ids.q} className="flex min-w-0 flex-1 flex-col gap-1 text-sm">
          <span className="font-medium">Filter routes</span>
          <input id={ids.q} type="search" value={text} onChange={(e) => setText(e.target.value)} placeholder="Path, handler or file" className="tap rounded-md border border-line-strong px-2" />
        </label>
        <label htmlFor={ids.m} className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Method</span>
          <select id={ids.m} value={method} onChange={(e) => setMethod(e.target.value)} className="tap rounded-md border border-line-strong px-2">
            <option value="">All</option>
            {methods.map((m) => (
              <option key={m} value={m}>
                {m === "UNKNOWN" ? "Not recorded" : m}
              </option>
            ))}
          </select>
        </label>
      </form>
      <p className="mb-2 text-sm text-ink-2" role="status" data-testid="routes-count">
        Showing {shown.length} of {items.length} routes.
      </p>
      <div className="mb-3">
        <HiddenCounts counts={hidden} reviewHref={`${base}/review`} />
      </div>
      {shown.length === 0 ? (
        <Empty title={items.length ? "No route matches the filter" : "No routes recorded"}>
          {items.length ? "Clear the filter to see every route." : "The route inventory for this snapshot is empty. Absence in static evidence is not proof that the code has no routes."}
        </Empty>
      ) : (
        <ul className="flex flex-col gap-2" aria-label="Routes">
          {shown.map((r) => {
            const h = r.handler_symbol ? splitSymbol(r.handler_symbol) : null;
            const label = isStatus(r.status) ? EXPECTED_LABEL[r.status] : undefined;
            return (
              <li key={`${r.claim_id ?? r.path}-${r.method}-${r.handler_symbol ?? ""}`} className="rounded-lg border border-line bg-surface p-3" data-testid="route-item">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-sm border border-line-strong px-1.5 font-mono text-xs" data-testid="route-method">
                    {r.method === "UNKNOWN" ? "method not recorded" : r.method}
                  </span>
                  <code className="break-all text-sm font-semibold">{r.path || "(path not recorded)"}</code>
                  <StatusChip status={r.status} label={label} flags={r.flags} />
                </div>
                <p className="mt-1 break-words text-sm text-ink-2">
                  {h ? (
                    <>
                      Handler <code>{h.name}</code>{" "}
                    </>
                  ) : (
                    "Handler not recorded "
                  )}
                  in{" "}
                  <Link to={`${base}/source?path=${encodeURIComponent(r.file)}&start=${r.line}&end=${r.line}`} className="break-all font-mono text-xs">
                    {r.file}:{r.line}
                  </Link>
                </p>
                {r.claim_id ? (
                  <div className="mt-2">
                    <Button onClick={() => onEvidence(r.claim_id!)} aria-label={`Open evidence for ${r.method === "UNKNOWN" ? "" : `${r.method} `}${r.path}`}>
                      Open evidence
                    </Button>
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

export function RoutesPage() {
  const { repoId = "", sha = "" } = useParams();
  const base = snapshotBase(repoId, sha);
  const q = useQuery({ queryKey: keys.view("routes", repoId, sha), queryFn: () => api.routes(repoId, sha) });
  const hidden = useClaims(repoId, sha, { kind: "route", limit: 1 });
  const [claim, setClaim, opener] = useDrawerClaim();
  return (
    <>
      <PageHeader title="Routes">
        Declared routes and API paths from static evidence, with the status of each route claim. A route that is declared is not proof that it is reachable or served when the code runs.
      </PageHeader>
      {q.isPending ? (
        <Loading label="Loading routes" />
      ) : q.isError ? (
        <ErrorState error={q.error} what="Routes" />
      ) : (
        <RoutesView items={q.data} base={base} onEvidence={setClaim} hidden={hidden.data?.hidden_counts} />
      )}
      <EvidenceDrawer repoId={repoId} sha={sha} claimId={claim} onClose={() => setClaim(null)} returnFocus={opener} />
    </>
  );
}
