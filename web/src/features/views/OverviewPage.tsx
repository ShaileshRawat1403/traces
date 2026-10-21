import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api, type Component } from "../../api/client";
import { useSnapshot } from "../../api/queries";
import { snapshotBase } from "../../app/nav";
import { presentStatus } from "../../status/status";
import { Card, ErrorState, Loading } from "../../ui/States";
import { StatusChip } from "../../ui/StatusChip";
import { EndpointView } from "./EndpointView";
import { OverviewView } from "./OverviewView";

const LAYER_ORDER = ["frontend", "api", "backend", "data", "infra", "docs", "tests", "other"] as const;
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
  const ext = s.extractor as Record<string, string>;
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
            <p className="mt-2 text-2xl font-semibold tabular-nums tracking-tight">{n.toLocaleString("en-US")}</p>
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
      <p className="mt-3 text-xs text-muted">Extractor {Object.entries(ext).map(([k, v]) => `${k} ${v}`).join(", ")}</p>
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
  return (
    <section className="mb-4 rounded-lg border border-line bg-surface p-4" aria-label="Components by layer">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-semibold">Components by layer</h2>
        <p className="text-xs text-muted">Open a layer in the graph. Grouping is a stored rule, not a guess.</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {LAYER_ORDER.filter((layer) => groups.has(layer)).map((layer) => (
          <div key={layer} className="rounded-md border border-line bg-canvas p-3">
            <div className="mb-2 flex items-baseline justify-between gap-2">
              <h3 className="text-sm font-semibold capitalize">{layer}</h3>
              <Link to={`${base}/graph?layer=${layer}`} className="text-xs">
                Graph
              </Link>
            </div>
            <ul className="flex flex-col gap-1">
              {(groups.get(layer) ?? []).map((c) => (
                <li key={c.id} className="flex items-baseline justify-between gap-2 text-sm">
                  <span className="min-w-0 truncate" title={c.paths.join(", ")}>
                    {c.name}
                  </span>
                  <span className="shrink-0 tabular-nums text-xs text-muted">{Object.values(c.claim_counts).reduce((a, b) => a + b, 0)}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}

export function OverviewPage() {
  const { repoId = "", sha = "" } = useParams();
  const base = snapshotBase(repoId, sha);
  return (
    <>
      <SnapshotCounts />
      <ComponentMap />
      <EndpointView
        name="overview"
        title="Overview"
        intro="What the system does, its entry points and where to start. Grounded facts cite evidence; interpretations and unknowns are labelled as such."
        fetcher={api.overview}
        render={(data) => <OverviewView data={data} base={base} />}
      />
    </>
  );
}
