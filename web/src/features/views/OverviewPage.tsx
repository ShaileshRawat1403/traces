import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api, type Component } from "../../api/client";
import { useSnapshot } from "../../api/queries";
import { snapshotBase } from "../../app/nav";
import { presentStatus } from "../../status/status";
import { Card, ErrorState, Loading, PageHeader } from "../../ui/States";
import { StatusChip } from "../../ui/StatusChip";
import { EndpointView } from "./EndpointView";
import { OverviewView } from "./OverviewView";

import { LAYERS, LAYER_COLOR } from "../layers";
const LABEL_FOR: Record<string, string> = { verified: "verified", observed: "observed", unvalidated: "inferred", missing_location: "inferred", rejected: "rejected" };

function SnapshotCounts() {
  const { repoId = "", sha = "" } = useParams();
  const snap = useSnapshot(repoId, sha);
  if (snap.isPending) return <Loading label="Loading snapshot" />;
  if (snap.isError) return <ErrorState error={snap.error} what="Snapshot" />;
  const s = snap.data;
  const by = (s.stats as { by_status?: Record<string, number> }).by_status ?? {};
  const shown = Object.entries(by).filter(([st]) => !presentStatus({ status: st, label: LABEL_FOR[st] }, "default").hidden);
  const rejected = by.rejected ?? 0;
  return (
    <Card className="mb-4">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h2 className="font-semibold">Evidence in this snapshot</h2>
        <p className="text-xs text-muted">Schema {s.evidence_schema}</p>
      </div>
      <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3" data-testid="snapshot-counts">
        {shown.map(([st, n]) => (
          <li key={st} className="rounded-md border border-line bg-canvas px-3 py-2">
            <StatusChip status={st} label={LABEL_FOR[st] ?? null} />
            <p className="mt-2 text-xl font-semibold tabular-nums tracking-tight">{n.toLocaleString("en-US")}</p>
            <p className="text-xs text-muted">{st.replace("_", " ")}</p>
          </li>
        ))}
      </ul>
      {rejected ? (
        <p className="mt-3 text-sm text-ink-2">
          {rejected.toLocaleString("en-US")} rejected claims stay in the audit trail. They are hidden from the graph and the trace. Open the{" "}
          <Link to={`${snapshotBase(repoId, sha)}/review`}>reviewer view</Link> to see them.
        </p>
      ) : null}
    </Card>
  );
}

function ComponentMap() {
  const { repoId = "", sha = "" } = useParams();
  const base = snapshotBase(repoId, sha);
  const q = useQuery({ queryKey: ["view", "components", repoId, sha], queryFn: () => api.components(repoId, sha) });
  if (!q.data?.length) return null;
  const groups = new Map<Component["layer"], Component[]>();
  for (const c of q.data) {
    const list = groups.get(c.layer) ?? [];
    list.push(c);
    groups.set(c.layer, list);
  }
  const volume = (c: Component) => Object.values(c.claim_counts).reduce((a, b) => a + b, 0);
  const max = Math.max(1, ...q.data.map(volume));
  const layers = LAYERS.filter((layer) => groups.has(layer));
  return (
    <section className="mb-4 rounded-lg border border-line bg-surface p-4" aria-label="Components by layer">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-semibold">Architecture, by stored layer</h2>
        <p className="max-w-xl text-xs text-muted" data-testid="overview-layer-note">
          {q.data.length > 0 && q.data.every((c) => !!c.reason)
            ? "Each band is the API's layer label; the Components page shows the API's reason for each one. It is not a runtime boundary."
            : "Each band is the API's layer label from a file path rule, not a reading of the code and not a runtime boundary; a library's source folder can show as backend."}{" "}
          The bar is how many claims were recorded, not a connection to the next band.
        </p>
      </div>
      <ol className="flex flex-col gap-2">
        {layers.map((layer, i) => (
          <li key={layer} className="grid grid-cols-1 gap-2 rounded-md border border-line bg-canvas p-2 sm:grid-cols-[7.5rem_minmax(0,1fr)] sm:items-start">
            <div className="flex items-center gap-2 px-1">
              <span className="text-xs tabular-nums text-muted">{i + 1}</span>
              <span className="inline-block h-3 w-3 rounded-sm" style={{ background: LAYER_COLOR[layer] }} aria-hidden="true" />
              <h3 className="text-sm font-semibold capitalize">{layer}</h3>
            </div>
            <ul className="flex flex-wrap gap-2">
              {(groups.get(layer) ?? []).map((c) => {
                const n = volume(c);
                return (
                  <li key={c.id} className="min-w-[9rem] max-w-full flex-1">
                    <Link
                      to={`${base}/graph?focus=${encodeURIComponent(c.id)}`}
                      className="block rounded-md border-2 bg-surface px-2 py-1.5 text-ink no-underline hover:bg-sunken"
                      style={{ borderColor: LAYER_COLOR[layer] }}
                      title={c.paths.join(", ")}
                    >
                      <span className="block truncate text-sm font-medium">{c.name}</span>
                      <span className="mt-1 block h-1 overflow-hidden rounded-full bg-sunken" aria-hidden="true">
                        <span className="block h-1 rounded-full" style={{ width: `${Math.max(8, (n / max) * 100)}%`, background: LAYER_COLOR[layer] }} />
                      </span>
                      <span className="mt-1 block text-xs text-muted tabular-nums">{n.toLocaleString("en-US")} claims</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
            <div className="sm:col-start-2">
              <Link to={`${base}/graph?layer=${layer}`} className="text-xs">
                Open {layer} on the graph
              </Link>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

export function OverviewPage() {
  const { repoId = "", sha = "" } = useParams();
  const base = snapshotBase(repoId, sha);
  return (
    <>
      <PageHeader title="Overview">The shape of this repository. Layers and components come from a stored rule. Open one to see the relationships that were actually recorded.</PageHeader>
      <ComponentMap />
      <EndpointView
        name="overview"
        title="Overview"
        intro=""
        showHeader={false}
        fetcher={api.overview}
        render={(data) => <OverviewView data={data} base={base} />}
      />
      <SnapshotCounts />
    </>
  );
}
