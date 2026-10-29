import { useQuery } from "@tanstack/react-query";
import { useEffect, useId, useState, type FormEvent } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, type RouteItem } from "../../api/client";
import { useCapability } from "../../api/queries";
import { snapshotBase } from "../../app/nav";
import { Button, ErrorState, Loading, PageHeader } from "../../ui/States";
import { EvidenceDrawer } from "../evidence/EvidenceDrawer";
import { decodeSubject, withAt } from "../subject/subject";
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
  const at = sp.get("at");
  useEffect(() => {
    if (from) return;
    const s = decodeSubject(at);
    if (s?.kind === "symbol") setF(s.id);
    else if (s?.kind === "route" && s.handler) setF(s.handler);
  }, [at, from]);
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
    if (at) n.set("at", at);
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
      {from ? null : <RecordedStarts repoId={repoId} sha={sha} />}
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

function RecordedStarts({ repoId, sha }: { repoId: string; sha: string }) {
  const routes = useQuery({ queryKey: ["view", "routes", repoId, sha], queryFn: () => api.routes(repoId, sha) });
  const base = snapshotBase(repoId, sha);
  const starts = (routes.data ?? []).filter((r) => r.handler_symbol && r.method !== "UNKNOWN" && r.method !== "USE");
  if (!starts.length) return null;
  const shown = starts.slice(0, 12);
  return (
    <section className="mb-5" aria-label="Recorded routes you can trace">
      <h2 className="text-sm font-medium tracking-[-0.02em]">Start from a recorded route</h2>
      <p className="mt-1 max-w-2xl text-[13px] text-muted">Each row is a route this snapshot stored. Tracing follows that handler. It does not fill in steps that were not recorded.</p>
      <ul className="mt-3 border-t border-white/10">
        {shown.map((r) => (
          <li key={routeKey(r)}>
            <Link to={withAt(`${base}/trace?from=${encodeURIComponent(r.handler_symbol!)}`, { kind: "route", method: r.method, path: r.path, handler: r.handler_symbol! })} className="flex min-h-11 items-center gap-3 border-b border-white/8 py-2 text-ink no-underline hover:no-underline">
              <span className="w-14 shrink-0 font-mono text-[12px] text-verified">{r.method}</span>
              <span className="min-w-0 flex-1 truncate font-mono text-[13px]">{r.path || "(path not recorded)"}</span>
              <span className="shrink-0 text-[12px] text-muted">Trace</span>
            </Link>
          </li>
        ))}
      </ul>
      {starts.length > shown.length ? (
        <p className="mt-2 text-xs text-muted">
          {starts.length - shown.length} more routes are on the <Link to={`${base}/routes`}>routes page</Link>.
        </p>
      ) : null}
    </section>
  );
}

function routeKey(r: RouteItem) {
  return `${r.claim_id ?? r.path}-${r.method}-${r.handler_symbol ?? ""}`;
}
