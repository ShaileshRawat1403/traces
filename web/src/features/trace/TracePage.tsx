import { useQuery } from "@tanstack/react-query";
import { useId, useState, type FormEvent } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { api } from "../../api/client";
import { useCapability } from "../../api/queries";
import { snapshotBase } from "../../app/nav";
import { Button, ErrorState, Loading, PageHeader } from "../../ui/States";
import { EvidenceDrawer } from "../evidence/EvidenceDrawer";
import { TraceView } from "./TraceView";
import { UserFlow } from "./UserFlow";

export function TracePage() {
  const { repoId = "", sha = "" } = useParams();
  const [sp, setSp] = useSearchParams();
  const from = sp.get("from") ?? "";
  const to = sp.get("to") ?? "";
  const [f, setF] = useState(from);
  const [t, setT] = useState(to);
  const ids = { f: useId(), t: useId() };
  const cap = useCapability("trace");
  const q = useQuery({ queryKey: ["trace", repoId, sha, from, to], queryFn: () => api.trace(repoId, sha, from, to || undefined), enabled: !!from });
  const claim = sp.get("claim");
  const setClaim = (id: string | null) =>
    setSp((p) => {
      const n = new URLSearchParams(p);
      if (id) n.set("claim", id);
      else n.delete("claim");
      return n;
    });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const n = new URLSearchParams();
    if (f.trim()) n.set("from", f.trim());
    if (t.trim()) n.set("to", t.trim());
    setSp(n);
  };
  return (
    <>
      <PageHeader title="Trace">Follow one recorded path. Library steps stay inferred, and a missing connection stays a gap.</PageHeader>
      {cap === false ? (
        <p className="mb-3 text-sm text-muted" role="note">
          The API reports trace as not available in this build. Submitting asks the API anyway and shows its answer.
        </p>
      ) : null}
      {from ? null : <UserFlow repoId={repoId} sha={sha} onEvidence={setClaim} />}
      <form onSubmit={submit} className="mb-4 grid gap-3 rounded-lg border border-line bg-surface p-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
        <div className="flex flex-col">
          <label htmlFor={ids.f} className="text-sm font-medium">
            From symbol
          </label>
          <input id={ids.f} value={f} onChange={(e) => setF(e.target.value)} placeholder="path/file.tsx::Name" className="tap rounded-md border border-line-strong px-2 font-mono text-sm" />
        </div>
        <div className="flex flex-col">
          <label htmlFor={ids.t} className="text-sm font-medium">
            To symbol (optional)
          </label>
          <input id={ids.t} value={t} onChange={(e) => setT(e.target.value)} placeholder="path/file.py::name" className="tap rounded-md border border-line-strong px-2 font-mono text-sm" />
        </div>
        <Button type="submit" variant="primary" disabled={!f.trim()}>
          Trace
        </Button>
      </form>
      {!from ? null : q.isPending ? (
        <Loading label="Tracing" />
      ) : q.isError ? (
        <ErrorState error={q.error} what="Trace" />
      ) : (
        <TraceView t={q.data} reviewHref={`${snapshotBase(repoId, sha)}/review`} onEvidence={setClaim} />
      )}
      <EvidenceDrawer repoId={repoId} sha={sha} claimId={claim} onClose={() => setClaim(null)} />
    </>
  );
}
