import { useQueries, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, type ClaimSummary, type Component, type TraceHop } from "../../api/client";
import { splitSymbol } from "../../api/record";
import { snapshotBase } from "../../app/nav";
import { componentForFile } from "../graph/graphModel";
import { HiddenCounts } from "../../ui/HiddenCounts";
import { Button, ErrorState, Loading } from "../../ui/States";
import { StatusChip } from "../../ui/StatusChip";
import { claimOnHop, componentSymbol, flagNote, flowLine, incomingRender, persistenceOnHop, pickFlowTrace } from "./flowModel";

const LAYER_COLOR: Record<string, string> = {
  frontend: "#8fd9cf",
  api: "#7eb6ff",
  backend: "#d7fff8",
  data: "#e2b16a",
  infra: "#b7c4ce",
  docs: "#c4b4ea",
  tests: "#ef8d86",
  other: "#8ea399",
};

function short(id: string) {
  return splitSymbol(id).name;
}

function Layer({ file, components }: { file: string | null; components: readonly Component[] }) {
  const layer = file ? componentForFile(file, components)?.layer : null;
  if (!layer) return null;
  return (
    <span className="inline-flex items-center gap-1 rounded-md border border-line px-1.5 text-xs capitalize text-ink-2">
      <span className="inline-block h-2 w-2 rounded-full" style={{ background: LAYER_COLOR[layer] ?? "#8ea399" }} aria-hidden="true" />
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
}: {
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
  const frame = tone === "gap" ? "border-2 border-dashed border-inferred bg-inferred-soft" : tone === "library" ? "border-2 border-dotted border-inferred bg-surface" : "border-line bg-surface";
  const note = flagNote(flags);
  return (
    <li className="grid grid-cols-[1rem_minmax(0,1fr)] gap-3" data-flow={tone}>
      <div className="flex flex-col items-center pt-4" aria-hidden="true">
        <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${tone === "edge" ? "bg-verified" : tone === "gap" ? "bg-inferred" : "bg-unknown"}`} />
        <span className={`mt-1 w-px flex-1 ${tone === "edge" ? "bg-verified" : "bg-inferred"} opacity-50`} />
      </div>
      <div className={`mb-2 rounded-lg border p-3 ${frame}`}>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-muted">Step {index}</span>
          <Layer file={file} components={components} />
          <StatusChip status={status} label={label} qualifier={qualifier} />
        </div>
        <p className="mt-2 text-sm">{flowLine(kind, short(from), short(to))}</p>
        <p className="mt-1 text-xs text-muted">
          <code className="break-all">{short(from)}</code>
          <span aria-hidden="true"> → </span>
          <span className="sr-only"> then </span>
          <code className="break-all">{short(to)}</code>
          <span className="ml-1">{kind.replaceAll("_", " ")}</span>
        </p>
        {reason ? <p className="mt-2 text-sm text-ink-2">{reason}</p> : null}
        {note ? <p className="mt-1 text-sm text-ink-2">{note}</p> : null}
        {persistence ? (
          <div className="mt-2 rounded-md border border-line bg-canvas p-2 text-sm">
            <p className="font-semibold">Static persistence path, same symbols</p>
            <p className="mt-1">{persistence.statement}</p>
            {persistence.qualifier ? <p className="mt-1 text-xs text-muted">{persistence.qualifier}</p> : null}
            <p className="mt-1 text-xs text-muted">This is a recorded code path. Nothing was executed, and no database was contacted.</p>
            <Button className="mt-2" onClick={() => onEvidence(persistence.claim_id)}>
              Open persistence evidence
            </Button>
          </div>
        ) : null}
        <div className="mt-2 flex flex-wrap gap-2">
          {claimId ? <Button onClick={() => onEvidence(claimId)}>Open evidence</Button> : null}
          <Link to={graphHref} className="tap inline-flex items-center rounded-md border border-line-strong bg-surface px-3 text-sm text-ink no-underline">
            Show on the graph
          </Link>
        </div>
      </div>
    </li>
  );
}

export function UserFlow({ repoId, sha, onEvidence }: { repoId: string; sha: string; onEvidence: (id: string) => void }) {
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

  return (
    <section className="mb-4" aria-label="Recorded user flow" data-testid="user-flow">
      <h2 className="font-semibold">From the screen to the persistence path</h2>
      <p className="mt-1 max-w-2xl text-sm text-ink-2">
        {steps.length} steps, in the order the evidence supports. {librarySteps} inferred library step{librarySteps === 1 ? "" : "s"}. {gapSteps} gap{gapSteps === 1 ? "" : "s"} left open. Rejected claims are not used as bridges.
      </p>
      <div className="mt-3">
        <HiddenCounts counts={chosen.hidden_counts} reviewHref={`${base}/review`} />
      </div>
      <ol className="mt-3 flex flex-col" aria-label="User flow steps">
        {steps.map((s, i) => (
          <Step
            key={s.key}
            index={i + 1}
            kind={s.hop.kind}
            from={s.hop.from_symbol}
            to={s.hop.to_symbol}
            status={s.tone === "library" || s.tone === "gap" ? "unvalidated" : s.hop.status}
            label={s.tone === "library" || s.tone === "gap" ? "inferred" : s.hop.label}
            qualifier={s.hop.qualifier}
            reason={s.hop.reason}
            claimId={s.hop.claim_id}
            flags={s.flags}
            persistence={s.persistence}
            file={splitSymbol(s.hop.from_symbol).file}
            components={components}
            tone={s.tone}
            onEvidence={onEvidence}
            graphHref={graph(s.hop.to_symbol)}
          />
        ))}
      </ol>
    </section>
  );
}
