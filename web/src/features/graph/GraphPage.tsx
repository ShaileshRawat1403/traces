// Code-split route: this module (and Cytoscape) loads only when the graph route is opened.
import { useQuery } from "@tanstack/react-query";
import cytoscape from "cytoscape";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, type GraphResponse } from "../../api/client";
import { splitSymbol } from "../../api/record";
import { snapshotBase } from "../../app/nav";
import { presentStatus } from "../../status/status";
import { HiddenCounts } from "../../ui/HiddenCounts";
import { Button, Empty, ErrorState, Loading, PageHeader } from "../../ui/States";
import { StatusChip } from "../../ui/StatusChip";
import { drawableEdges } from "./graphModel";

const TOKENS = { verified: "#0f5e63", observed: "#475569", inferred: "#8a5300", unknown: "#5b21b6", node: "#ffffff", nodeLine: "#c9c3b8", ink: "#1d1b18" };

function Canvas({ data, onSelect }: { data: GraphResponse; onSelect: (id: string) => void }) {
  const box = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const { edges } = useMemo(() => drawableEdges(data), [data]);
  useEffect(() => {
    if (!box.current) return;
    const ids = new Set(data.nodes.map((n) => n.id));
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    const cy = cytoscape({
      container: box.current,
      elements: [
        ...data.nodes.map((n) => ({ data: { id: n.id, label: n.label } })),
        ...edges
          .filter((e) => ids.has(e.source) && ids.has(e.target))
          .map((e) => {
            const p = presentStatus(e, "default");
            return { data: { id: e.id, source: e.source, target: e.target, tone: p.tone, line: p.line } };
          }),
      ],
      style: [
        { selector: "node", style: { label: "data(label)", "font-size": 11, color: TOKENS.ink, "background-color": TOKENS.node, "border-width": 1.5, "border-color": TOKENS.nodeLine, "text-valign": "bottom", "text-margin-y": 4, width: 18, height: 18, "text-max-width": "120px", "text-wrap": "ellipsis" } },
        { selector: "edge", style: { width: 2, "curve-style": "bezier", "target-arrow-shape": "triangle", "arrow-scale": 0.8 } },
        { selector: 'edge[tone = "verified"]', style: { "line-color": TOKENS.verified, "target-arrow-color": TOKENS.verified } },
        { selector: 'edge[tone = "observed"]', style: { "line-color": TOKENS.observed, "target-arrow-color": TOKENS.observed, width: 1 } },
        { selector: 'edge[tone = "inferred"]', style: { "line-color": TOKENS.inferred, "target-arrow-color": TOKENS.inferred, "target-arrow-fill": "hollow" } },
        { selector: 'edge[tone = "unknown"]', style: { "line-color": TOKENS.unknown, "target-arrow-color": TOKENS.unknown } },
        { selector: 'edge[line = "dashed"]', style: { "line-style": "dashed" } },
        { selector: 'edge[line = "dotted"]', style: { "line-style": "dotted" } },
        { selector: ":selected", style: { "border-width": 3, "border-color": "#1c64d8", "line-color": "#1c64d8", "target-arrow-color": "#1c64d8" } },
      ],
      layout: { name: "cose", animate: !reduced },
      wheelSensitivity: 0.3,
    });
    cy.on("tap", "node", (ev) => onSelect(ev.target.id() as string));
    cyRef.current = cy;
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [data, edges, onSelect]);
  const zoom = (f: number) => cyRef.current?.zoom({ level: (cyRef.current.zoom() ?? 1) * f, renderedPosition: { x: (box.current?.clientWidth ?? 0) / 2, y: (box.current?.clientHeight ?? 0) / 2 } });
  return (
    <div>
      <div className="mb-2 flex gap-2" role="toolbar" aria-label="Graph view controls">
        <Button onClick={() => zoom(1.25)} aria-label="Zoom in">+</Button>
        <Button onClick={() => zoom(0.8)} aria-label="Zoom out">−</Button>
        <Button onClick={() => cyRef.current?.fit(undefined, 24)}>Fit</Button>
      </div>
      <div ref={box} className="h-[60vh] min-h-80 w-full rounded-lg border border-line bg-surface" role="img" aria-label={`Architecture graph with ${data.nodes.length} nodes. Use the list view for keyboard and screen reader navigation.`} />
    </div>
  );
}

function ListView({ data, focus }: { data: GraphResponse; focus: string | null }) {
  const { repoId = "", sha = "" } = useParams();
  const { edges } = drawableEdges(data);
  const shown = focus ? edges.filter((e) => e.source === focus || e.target === focus) : edges;
  const name = (id: string) => data.nodes.find((n) => n.id === id)?.label ?? splitSymbol(id).name;
  if (shown.length === 0) return <Empty title="No relationships match these filters" />;
  return (
    <ul className="flex flex-col gap-2" data-testid="graph-list">
      {shown.map((e) => (
        <li key={e.id} className="rounded-lg border border-line bg-surface p-3 text-sm">
          <StatusChip status={e.status} label={e.label} flags={e.flags} qualifier={e.qualifier} />
          <p className="mt-1 break-words">
            <code>{name(e.source)}</code> <span className="text-muted">{e.kind}</span> <code>{name(e.target)}</code>
          </p>
          {e.id.startsWith("c_") ? <Link to={`${snapshotBase(repoId, sha)}/claim/${e.id}`}>Open evidence</Link> : null}
        </li>
      ))}
    </ul>
  );
}

export default function GraphPage() {
  const { repoId = "", sha = "" } = useParams();
  const [sp, setSp] = useSearchParams();
  const mode = sp.get("view") === "list" ? "list" : "graph";
  const focus = sp.get("focus");
  const params = { focus: focus ?? undefined, depth: sp.get("depth") ?? undefined, q: sp.get("q") ?? undefined, layer: sp.get("layer") ?? undefined };
  const q = useQuery({ queryKey: ["graph", repoId, sha, params], queryFn: () => api.graph(repoId, sha, params) });
  const [selected, setSelected] = useState<string | null>(null);
  const setMode = (m: string) =>
    setSp((p) => {
      const n = new URLSearchParams(p);
      n.set("view", m);
      return n;
    });
  return (
    <>
      <PageHeader title="Architecture graph">Components first; expand one to see its symbols. Inferred relationships are dashed, and rejected ones are never drawn.</PageHeader>
      {q.isPending ? (
        <Loading label="Loading graph" />
      ) : q.isError ? (
        <ErrorState error={q.error} what="The architecture graph" />
      ) : (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <div role="group" aria-label="View as" className="inline-flex rounded-md border border-line-strong">
              {(["graph", "list"] as const).map((m) => (
                <button key={m} type="button" aria-pressed={mode === m} onClick={() => setMode(m)} className={`tap px-3 text-sm ${mode === m ? "bg-accent text-accent-ink" : "bg-surface"}`}>
                  {m === "graph" ? "Graph" : "List"}
                </button>
              ))}
            </div>
            <span className="text-sm text-muted">
              {q.data.nodes.length} nodes{q.data.truncated ? `, truncated at ${q.data.limit}` : ""}
            </span>
            {selected ? <span className="text-sm">Selected: <code>{selected}</code></span> : null}
          </div>
          <div className="mb-3">
            <HiddenCounts counts={q.data.hidden_counts} extra={drawableEdges(q.data).hidden} reviewHref={`${snapshotBase(repoId, sha)}/review`} />
          </div>
          {mode === "graph" ? <Canvas data={q.data} onSelect={setSelected} /> : <ListView data={q.data} focus={focus} />}
        </>
      )}
    </>
  );
}
