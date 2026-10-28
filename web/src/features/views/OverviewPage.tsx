import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { useSnapshot } from "../../api/queries";
import { snapshotBase } from "../../app/nav";
import { presentStatus } from "../../status/status";
import { ErrorState, Loading } from "../../ui/States";
import { StatusChip } from "../../ui/StatusChip";
import { EndpointView } from "./EndpointView";
import { OverviewView } from "./OverviewView";
import { SystemMap } from "./SystemMap";

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
    <div className="mb-6 border-t border-white/10 pt-5">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-medium tracking-[-0.02em]">Evidence in this snapshot</h2>
        <p className="text-xs text-muted">Schema {s.evidence_schema}</p>
      </div>
      <ul className="flex flex-wrap gap-2" data-testid="snapshot-counts">
        {shown.map(([st, n]) => (
          <li key={st} className="inline-flex items-baseline gap-2">
            <StatusChip status={st} label={LABEL_FOR[st] ?? null} />
            <span className="text-lg font-semibold tabular-nums tracking-tight">{n.toLocaleString("en-US")}</span>
          </li>
        ))}
      </ul>
      {rejected ? (
        <p className="mt-3 text-sm text-ink-2">
          {rejected.toLocaleString("en-US")} rejected claims stay in the audit trail. They are hidden from the graph and the trace. Open the{" "}
          <Link to={`${snapshotBase(repoId, sha)}/review`}>reviewer view</Link> to see them.
        </p>
      ) : null}
    </div>
  );
}

export function OverviewPage() {
  const { repoId = "", sha = "" } = useParams();
  const base = snapshotBase(repoId, sha);
  return (
    <>
      <header className="mb-3">
        <h1 className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted">Overview</h1>
      </header>
      <SystemMap />
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
