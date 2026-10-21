import { useParams } from "react-router-dom";
import { api } from "../../api/client";
import { useSnapshot } from "../../api/queries";
import { snapshotBase } from "../../app/nav";
import { presentStatus } from "../../status/status";
import { Card, ErrorState, Loading } from "../../ui/States";
import { StatusChip } from "../../ui/StatusChip";
import { EndpointView } from "./EndpointView";
import { OverviewView } from "./OverviewView";
import { Link } from "react-router-dom";

// Allowed label for each status, used only to render the chip for a status count (CONTRACTS.md 2).
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

export function OverviewPage() {
  const { repoId = "", sha = "" } = useParams();
  const base = snapshotBase(repoId, sha);
  return (
    <>
      <SnapshotCounts />
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
