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

const LAYER_SWATCH: Record<string, string> = {
  frontend: "#8fd9cf",
  api: "#7eb6ff",
  backend: "#d7fff8",
  data: "#e2b16a",
  infra: "#b7c4ce",
  docs: "#c4b4ea",
  tests: "#ef8d86",
  other: "#8ea399",
};
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
  return (
    <section className="mb-4 rounded-lg border border-line bg-surface p-4" aria-label="Components by layer">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-semibold">Components by layer</h2>
        <p className="text-xs text-muted">Choose a component to open its relationships. Grouping is a stored rule, not a guess.</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {LAYER_ORDER.filter((layer) => groups.has(layer)).map((layer) => (
          <div key={layer} className="rounded-md border border-line bg-canvas p-3">
            <div className="mb-2 flex items-baseline justify-between gap-2">
              <h3 className="flex items-center gap-2 text-sm font-semibold capitalize">
                <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: LAYER_SWATCH[layer] }} aria-hidden="true" />
                {layer}
              </h3>
              <Link to={`${base}/graph?layer=${layer}`} className="text-xs">
                Graph
              </Link>
            </div>
            <ul className="flex flex-wrap gap-1.5">
              {(groups.get(layer) ?? []).map((c) => (
                <li key={c.id}>
                  <Link
                    to={`${base}/graph?focus=${encodeURIComponent(c.id)}`}
                    className="inline-flex max-w-full items-center gap-1 rounded-md border border-line bg-surface px-2 py-1 text-xs text-ink no-underline hover:border-accent"
                    title={c.paths.join(", ")}
                  >
                    <span className="truncate">{c.name}</span>
                    <span className="tabular-nums text-muted">{Object.values(c.claim_counts).reduce((a, b) => a + b, 0)}</span>
                  </Link>
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
      <PageHeader title="Overview">What the system does, its entry points and where to start. Grounded facts cite evidence; interpretations and unknowns are labelled as such.</PageHeader>
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
