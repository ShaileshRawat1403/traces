import { GAP_MEANING } from "./traceModel";
import { GapHidden } from "./GapHidden";
import { useQueries, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, type ClaimSummary, type Component, type TraceHop } from "../../api/client";
import { splitSymbol } from "../../api/record";
import { snapshotBase } from "../../app/nav";
import { componentForFile } from "../graph/graphModel";
import { HiddenCounts } from "../../ui/HiddenCounts";
import { Button, ErrorState, Loading } from "../../ui/States";
import { StatusChip } from "../../ui/StatusChip";
import { layerColor } from "../layers";
import { claimOnHop, componentSymbol, flagNote, flowLine, incomingRender, persistenceOnHop, pickFlowTrace } from "./flowModel";

function short(id: string) {
  return splitSymbol(id).name;
}

function Layer({ file, components }: { file: string | null; components: readonly Component[] }) {
  const layer = file ? componentForFile(file, components)?.layer : null;
  if (!layer) return null;
  return (
    <span className="inline-flex items-center gap-1 rounded-md border border-line px-1.5 text-xs capitalize text-ink-2">
      <span className="inline-block h-2 w-2 rounded-full" style={{ background: layerColor(layer) }} aria-hidden="true" />
      {layer}
    </span>
  );
}

function Step({
  index,
  kind,
  from,
  to,
  status,
  label,
  qualifier,
  reason,
  claimId,
  flags,
  persistence,
  file,
  components,
  tone,
  onEvidence,
  graphHref,
  hop,
  snapshotHidden,
  reviewHref,
}: {
  hop: TraceHop;
  snapshotHidden: Record<string, number> | null | undefined;
  reviewHref: string;
  index: number;
  kind: string;
  from: string;
  to: string;
  status: string | null;
  label: string | null;
  qualifier?: string | null;
  reason?: string | null;
  claimId?: string | null;
  flags?: string[];
  persistence?: ClaimSummary | null;
  file: string | null;
  components: readonly Component[];
  tone: "edge" | "gap" | "library";
  onEvidence: (id: string) => void;
  graphHref: string;
}) {
  const frame = tone;
  const note = flagNote(flags);
  return (
    <div className="flow-detail" data-flow={frame}>
      <div className="flow-node">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted">From</span>
        <code className="block break-all text-sm font-semibold">{short(from)}</code>
        <Layer file={file} components={components} />
      </div>
      <div className="flow-join">
        <span className="font-semibold text-ink">{kind.replaceAll("_", " ")}</span>
        <StatusChip status={status} label={label} qualifier={qualifier} />
      </div>
      <div className="flow-node">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted">To</span>
        <code className="block break-all text-sm font-semibold">{short(to)}</code>
      </div>
      <p className="flow-span text-sm">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted">Step {index}. </span>
        {flowLine(kind, short(from), short(to))}
      </p>
      {tone === "gap" ? (
        <p className="flow-span text-sm" data-testid="gap-meaning">
          <span className="font-semibold">What this gap means: </span>
          {GAP_MEANING}
        </p>
      ) : null}
      {tone === "gap" ? <GapHidden hop={hop} snapshotHidden={snapshotHidden} reviewHref={reviewHref} /> : null}
      {reason ? (
        <p className="flow-span text-sm text-ink-2">
          {tone === "gap" ? <span className="font-semibold">API note: </span> : null}
          {reason}
        </p>
      ) : null}
      {note ? <p className="flow-span text-sm text-ink-2">{note}</p> : null}
      {persistence ? (
        <div className="flow-span rounded-md border border-line bg-canvas p-2 text-sm">
          <p className="font-semibold">Static persistence path, same symbols</p>
          <p className="mt-1 text-xs text-muted">This is a recorded code path. Nothing was executed, and no database was contacted.</p>
          <details className="mt-2">
            <summary className="tap flex cursor-pointer items-center text-sm">Recorded steps</summary>
            <p className="mt-1">{persistence.statement}</p>
            {persistence.qualifier ? <p className="mt-1 text-xs text-muted">{persistence.qualifier}</p> : null}
            <Button className="mt-2" onClick={() => onEvidence(persistence.claim_id)}>
              Open persistence evidence
            </Button>
          </details>
        </div>
      ) : null}
      <div className="flow-span flex flex-wrap gap-2">
        {claimId ? <Button onClick={() => onEvidence(claimId)}>Open evidence</Button> : null}
        <Link to={graphHref} className="tap inline-flex items-center rounded-md border border-line-strong bg-surface px-3 text-sm text-ink no-underline">
          Show on the graph
        </Link>
      </div>
    </div>
  );
}

export function UserFlow({ repoId, sha, onEvidence }: { repoId: string; sha: string; onEvidence: (id: string) => void }) {
  const [picked, setPicked] = useState<number | null>(null);
  const base = snapshotBase(repoId, sha);
  const claimQ = (kind: string, limit: number) => ({ kind, claim_kind: "relationship", limit });
  const persist = useQuery({ queryKey: ["flow", "persistence", repoId, sha], queryFn: () => api.claims(repoId, sha, claimQ("persistence_path", 5)) });
  const libs = useQuery({ queryKey: ["flow", "library", repoId, sha], queryFn: () => api.claims(repoId, sha, claimQ("library_contract", 20)) });
  const binds = useQuery({ queryKey: ["flow", "binds", repoId, sha], queryFn: () => api.claims(repoId, sha, claimQ("binds_handler", 10)) });
  const ops = useQuery({ queryKey: ["flow", "ops", repoId, sha], queryFn: () => api.claims(repoId, sha, claimQ("implements_operation", 10)) });
  const routes = useQuery({ queryKey: ["flow", "routes", repoId, sha], queryFn: () => api.claims(repoId, sha, claimQ("routes_to", 10)) });
  const comps = useQuery({ queryKey: ["view", "components", repoId, sha], queryFn: () => api.components(repoId, sha) });

  const target = persist.data?.items.find((c) => c.to_symbol)?.to_symbol ?? null;
  const starts = [...new Set((libs.data?.items ?? []).map((c) => c.from_symbol).filter((s): s is string => !!s))].sort();
  const traceQs = useQueries({
    queries: starts.map((from) => ({
      queryKey: ["flow", "trace", repoId, sha, from, target],
      queryFn: () => api.trace(repoId, sha, from, target!),
      enabled: !!target,
    })),
  });
  const chosen = pickFlowTrace(traceQs.map((q) => q.data).filter((t): t is NonNullable<typeof t> => !!t));
  const owner = chosen ? componentSymbol(chosen.from_symbol) : null;
  const renders = useQuery({
    queryKey: ["flow", "renders", repoId, sha, owner],
    queryFn: () => api.claims(repoId, sha, { kind: "renders", symbol: owner!, claim_kind: "relationship", limit: 50 }),
    enabled: !!owner,
  });
  const page = owner && renders.data ? incomingRender(renders.data.items, owner) : null;
  const bridge = useQuery({
    queryKey: ["flow", "bridge", repoId, sha, page?.from_symbol, chosen?.from_symbol],
    queryFn: () => api.trace(repoId, sha, page!.from_symbol!, chosen!.from_symbol),
    enabled: !!page?.from_symbol && !!chosen && page.from_symbol !== chosen.from_symbol,
  });

  if (persist.isPending || libs.isPending) return <Loading label="Reading the recorded path" />;
  if (persist.isError) return <ErrorState error={persist.error} what="The recorded path" />;
  const pathClaim = persist.data?.items[0];
  if (!pathClaim) {
    return <p className="mb-4 text-sm text-ink-2">No static persistence path is recorded for this snapshot, so there is no cross-layer flow to draw.</p>;
  }
  if (target && starts.length > 0 && traceQs.some((q) => q.isPending)) return <Loading label="Tracing the recorded path" />;
  if (!chosen) {
    return (
      <section className="mb-4 rounded-lg border border-line bg-surface p-4" data-testid="user-flow">
        <h2 className="font-semibold">Recorded persistence path</h2>
        <p className="mt-2 text-sm">{pathClaim.statement}</p>
        <p className="mt-1 text-xs text-muted">{pathClaim.qualifier}</p>
        <Button className="mt-2" onClick={() => onEvidence(pathClaim.claim_id)}>
          Open evidence
        </Button>
      </section>
    );
  }

  const components = comps.data ?? [];
  const extra = [...(ops.data?.items ?? []), ...(routes.data?.items ?? [])];
  const bind = (binds.data?.items ?? []).find((c) => c.from_symbol && owner && c.from_symbol.startsWith(owner));
  const bridgeHop = bridge.data?.hops.length === 1 && bridge.data.hops[0]?.type === "gap" ? bridge.data.hops[0] : null;
  const graph = (id: string) => `${base}/graph?focus=${encodeURIComponent(id)}`;

  const steps: { key: string; hop: TraceHop; tone: "edge" | "gap" | "library"; persistence: ClaimSummary | null; flags?: string[] }[] = [];
  if (page?.from_symbol && page.to_symbol) {
    steps.push({
      key: page.claim_id,
      tone: "edge",
      persistence: null,
      hop: {
        index: 0,
        type: "edge",
        kind: page.kind ?? "renders",
        from_symbol: page.from_symbol,
        to_symbol: page.to_symbol,
        status: page.status,
        label: page.label,
        claim_id: page.claim_id,
        qualifier: page.qualifier,
        evidence_scope: "static",
      },
    });
  }
  if (bridgeHop) {
    steps.push({ key: "bridge", tone: "gap", persistence: null, hop: bridgeHop });
  }
  if (bind?.from_symbol && bind.to_symbol) {
    steps.push({
      key: bind.claim_id,
      tone: "edge",
      persistence: null,
      hop: {
        index: 0,
        type: "edge",
        kind: "binds_handler",
        from_symbol: bind.from_symbol,
        to_symbol: bind.to_symbol,
        status: bind.status,
        label: bind.label,
        claim_id: bind.claim_id,
        qualifier: bind.qualifier,
        evidence_scope: "static",
      },
    });
  }
  for (const hop of chosen.hops) {
    const matched = claimOnHop(hop, extra, hop.kind);
    steps.push({
      key: hop.claim_id ?? `h-${hop.index}`,
      tone: hop.type === "library_contract" ? "library" : hop.type === "gap" ? "gap" : "edge",
      persistence: persistenceOnHop(hop, persist.data?.items ?? []),
      flags: matched?.flags,
      hop,
    });
  }

  const librarySteps = steps.filter((s) => s.tone === "library").length;
  const gapSteps = steps.filter((s) => s.tone === "gap").length;
  const preferred = Math.max(0, steps.findIndex((s) => s.persistence));
  const index = Math.min(steps.length - 1, picked ?? preferred);
  const current = steps[index]!;

  return (
    <section className="mb-4" aria-label="Recorded user flow" data-testid="user-flow">
      <h2 className="font-semibold">From the screen to the persistence path</h2>
      <p className="mt-1 max-w-2xl text-sm text-ink-2">
        {steps.length} steps, in the order the evidence supports. {librarySteps} inferred library step{librarySteps === 1 ? "" : "s"}. {gapSteps} gap{gapSteps === 1 ? "" : "s"} left open. Rejected claims are not used as bridges.
      </p>
      <div className="mt-3">
        <HiddenCounts counts={chosen.hidden_counts} reviewHref={`${base}/review`} />
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2" aria-label="How to read the flow">
        <li className="inline-flex items-center gap-1">
          <span className="inline-block h-0.5 w-6 bg-verified" aria-hidden="true" /> Solid, verified or observed
        </li>
        <li className="inline-flex items-center gap-1">
          <span className="inline-block h-0.5 w-6 border-t-2 border-dotted border-unknown" aria-hidden="true" /> Dotted, inferred library
        </li>
        <li className="inline-flex items-center gap-1">
          <span className="inline-block h-0.5 w-6 border-t-2 border-dashed border-inferred" aria-hidden="true" /> Dashed, gap: no accepted static evidence
        </li>
      </ul>
      <div className="mt-3 flex flex-col gap-4">
      <ol className="flow-rail" aria-label="User flow steps">
        {steps.map((s, i) => (
          <li key={s.key} data-flow={s.tone}>
            <button type="button" aria-pressed={i === index} onClick={() => setPicked(i)} className="flow-stop">
              <span className="text-xs text-muted">{i + 1}</span>
              <span className="block truncate font-semibold">{short(s.hop.to_symbol)}</span>
              <span className="block truncate text-xs text-ink-2">{s.hop.kind.replaceAll("_", " ")}</span>
            </button>
          </li>
        ))}
      </ol>
      <Step
        index={index + 1}
        kind={current.hop.kind}
        from={current.hop.from_symbol}
        to={current.hop.to_symbol}
        status={current.tone === "library" || current.tone === "gap" ? "unvalidated" : current.hop.status}
        label={current.tone === "library" || current.tone === "gap" ? "inferred" : current.hop.label}
        qualifier={current.hop.qualifier}
        reason={current.hop.reason}
        claimId={current.hop.claim_id}
        flags={current.flags}
        persistence={current.persistence}
        file={splitSymbol(current.hop.from_symbol).file}
        components={components}
        tone={current.tone}
        onEvidence={onEvidence}
        graphHref={graph(current.hop.to_symbol)}
        hop={current.hop}
        snapshotHidden={current.key === "bridge" ? bridge.data?.hidden_counts : chosen.hidden_counts}
        reviewHref={`${base}/review`}
      />
      </div>
    </section>
  );
}
