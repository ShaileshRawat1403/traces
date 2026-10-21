import { useParams } from "react-router-dom";
import { api } from "../../api/client";
import { useSnapshot } from "../../api/queries";
import { snapshotBase } from "../../app/nav";
import { presentStatus } from "../../status/status";
import { Card, ErrorState, Loading } from "../../ui/States";
import { StatusChip } from "../../ui/StatusChip";
import { EndpointView } from "./EndpointView";
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
      <h2 className="mb-2 font-semibold">Evidence in this snapshot</h2>
      <ul className="flex flex-wrap gap-x-4 gap-y-2" data-testid="snapshot-counts">
        {shown.map(([st, n]) => (
          <li key={st} className="flex items-center gap-2 text-sm">
            <StatusChip status={st} label={LABEL_FOR[st] ?? null} />
            <span className="tabular-nums">{n.toLocaleString("en-US")}</span>
            <span className="text-muted">{st}</span>
          </li>
        ))}
      </ul>
      {rejected ? (
        <p className="mt-2 text-sm text-ink-2">
          {rejected.toLocaleString("en-US")} rejected claims are kept for audit in the <Link to={`${snapshotBase(repoId, sha)}/review`}>reviewer view</Link>.
        </p>
      ) : null}
      <p className="mt-2 text-xs text-muted">
        Schema {s.evidence_schema} · extractor {Object.entries(ext).map(([k, v]) => `${k} ${v}`).join(", ")} · state {s.state}
      </p>
    </Card>
  );
}

export function OverviewPage() {
  return (
    <>
      <SnapshotCounts />
      <EndpointView
        name="overview"
        title="Overview"
        intro="What the system does, its entry points and where to start, each fact tagged grounded or interpretation."
        fetcher={api.overview}
      />
    </>
  );
}
