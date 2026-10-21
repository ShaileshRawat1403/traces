import { useQuery } from "@tanstack/react-query";
import { useId, useState, type FormEvent } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { api } from "../../api/client";
import { useCapability } from "../../api/queries";
import { Button, Card, ErrorState, Loading, PageHeader } from "../../ui/States";

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
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const n = new URLSearchParams();
    if (f.trim()) n.set("from", f.trim());
    if (t.trim()) n.set("to", t.trim());
    setSp(n);
  };
  return (
    <>
      <PageHeader title="Trace">Follow a flow across files and layers. Library steps that cannot be verified are shown as inferred, and gaps are shown as gaps.</PageHeader>
      {cap === false ? (
        <p className="mb-3 text-sm text-muted" role="note">
          The API reports trace as not available in this build. Submitting asks the API anyway and shows its answer.
        </p>
      ) : null}
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
        <Card>
          <p role="status">The API returned a trace with {q.data.hops.length} hops. The trace renderer is scheduled for the next UI checkpoint.</p>
        </Card>
      )}
    </>
  );
}
