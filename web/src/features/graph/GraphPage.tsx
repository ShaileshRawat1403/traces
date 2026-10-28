// Code-split route: the architecture diagram loads with this page.
import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useId, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, type Component, type GraphEdge, type GraphNode, type GraphResponse } from "../../api/client";
import { splitSymbol } from "../../api/record";
import { snapshotBase } from "../../app/nav";
import { HiddenCounts } from "../../ui/HiddenCounts";
import { Button, Empty, ErrorState, Loading } from "../../ui/States";
import { LineSample, StatusChip } from "../../ui/StatusChip";
import { EvidenceDrawer } from "../evidence/EvidenceDrawer";
import { GraphCanvas, RecordedLinks } from "./GraphCanvas";
import { CODE_LAYERS, isLayer, layerColor } from "../layers";
import { LAYERS, STATUS_FILTERS, canvasElements, componentRollup, countsFor, drawableEdges, fileRollup, graphQuery, openingDiagram, readGraphState, symbolsInFile, toElements, writeGraphState, type ElementData, type GraphState, type StatusFilter } from "./graphModel";

const STATUS_TEXT: Record<StatusFilter, string> = {
  verified: "Verified",
  observed: "Observed",
  unvalidated: "Inferred (unvalidated)",
  missing_location: "Inferred, no source location",
};

const coreLayer = (layer: string | undefined) => isLayer(layer) && CODE_LAYERS[layer];

function Legend() {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2" aria-label="Edge legend">
      <li className="flex items-center gap-1 text-verified">
        <LineSample line="solid" /> <span className="text-ink-2">Verified</span>
      </li>
      <li className="flex items-center gap-1 text-observed">
        <LineSample line="thin" /> <span className="text-ink-2">Observed</span>
      </li>
      <li className="flex items-center gap-1 text-inferred">
        <LineSample line="dashed" /> <span className="text-ink-2">Inferred</span>
      </li>
      <li className="flex items-center gap-1 text-inferred">
        <LineSample line="dotted" /> <span className="text-ink-2">Inferred, no source location</span>
      </li>
      <li className="text-ink-2">Rejected claims are never drawn.</li>
    </ul>
  );
}

function Filters({ state: urlState, onChange: commit }: { state: GraphState; onChange: (s: GraphState) => void }) {
  const relId = useId();
  // The URL is the source of truth, but router navigation is async: hold the choice locally so a controlled checkbox
  // does not flick back for a frame before the URL catches up.
  const [state, setLocal] = useState(urlState);
  const urlKey = JSON.stringify(urlState);
  useEffect(() => setLocal(JSON.parse(urlKey) as GraphState), [urlKey]);
  const onChange = (s: GraphState) => {
    setLocal(s);
    commit(s);
  };
  const toggle = <T extends string>(list: T[], v: T) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
  const [rel, setRel] = useState(state.rel.join(", "));
  return (
    <details className="rounded-lg border border-line bg-surface" data-testid="graph-filters">
      <summary className="tap flex cursor-pointer items-center px-3 text-sm font-medium">
        Filters
        <span className="ml-2 text-xs font-normal text-muted">
          {state.status.length} statuses{state.layer.length ? `, ${state.layer.length} layers` : ""}
          {state.rel.length ? `, ${state.rel.length} kinds` : ""}
        </span>
      </summary>
      <div className="grid gap-4 border-t border-line p-3 sm:grid-cols-3">
        <fieldset>
          <legend className="mb-1 text-sm font-semibold">Evidence status</legend>
          {STATUS_FILTERS.map((s) => (
            <label key={s} className="tap flex items-center gap-2 text-sm">
              <input type="checkbox" className="h-5 w-5" checked={state.status.includes(s)} onChange={() => onChange({ ...state, status: toggle(state.status, s) })} />
              {STATUS_TEXT[s]}
            </label>
          ))}
          <p className="mt-1 text-xs text-muted">Inferred relationships are off by default. Rejected claims are never requested.</p>
        </fieldset>
        <fieldset>
          <legend className="mb-1 text-sm font-semibold">Layer</legend>
          <div className="grid grid-cols-2 gap-x-2">
            {LAYERS.map((l) => (
              <label key={l} className="tap flex items-center gap-2 text-sm">
                <input type="checkbox" className="h-5 w-5" checked={state.layer.includes(l)} onChange={() => onChange({ ...state, layer: toggle(state.layer, l) })} />
                {l}
              </label>
            ))}
          </div>
          <p className="mt-1 text-xs text-muted">None selected means all layers.</p>
        </fieldset>
        <div>
          <label htmlFor={relId} className="mb-1 block text-sm font-semibold">
            Relationship kinds
          </label>
          <input
            id={relId}
            value={rel}
            onChange={(e) => setRel(e.target.value)}
            onBlur={() => onChange({ ...state, rel: rel.split(",").map((x) => x.trim()).filter(Boolean) })}
            placeholder="renders, calls, imports"
            className="tap w-full rounded-md border border-line-strong px-2 text-sm"
          />
          <p className="mt-1 text-xs text-muted">Comma separated. Empty means all kinds.</p>
        </div>
      </div>
    </details>
  );
}

function nodeName(nodes: readonly GraphNode[], id: string) {
  return nodes.find((n) => n.id === id)?.label ?? splitSymbol(id).name;
}

function EdgeRow({ e, nodes, onEvidence }: { e: GraphEdge; nodes: readonly GraphNode[]; onEvidence: (id: string) => void }) {
  return (
    <li className="rounded-lg border border-line bg-surface p-3 text-sm">
      <StatusChip status={e.status} label={e.label} flags={e.flags} qualifier={e.qualifier} />
      <p className="mt-1 break-words">
        <code>{nodeName(nodes, e.source)}</code> <span className="text-muted">{e.kind}</span> <code>{nodeName(nodes, e.target)}</code>
      </p>
      <Button className="mt-1" onClick={() => onEvidence(e.id)}>
        Open evidence
      </Button>
    </li>
  );
}

function Counts({ counts }: { counts: Record<string, number> | null }) {
  if (!counts) return null;
  const entries = Object.entries(counts).filter(([k]) => k !== "rejected");
  if (entries.length === 0) return null;
  return (
    <p className="text-xs text-ink-2" data-testid="component-counts">
      {entries.map(([k, n]) => `${n.toLocaleString("en-US")} ${k}`).join(" · ")}
    </p>
  );
}

function componentNode(id: string, components: readonly Component[]): GraphNode | null {
  const c = components.find((x) => x.id === id);
  if (!c) return null;
  return { id: c.id, label: c.name, entity: "component", layer: c.layer, file: null, degree: 0 };
}

function SelectionPanel({
  data,
  components,
  selected,
  state,
  base,
  onState,
  onEvidence,
  onClear,
}: {
  data: GraphResponse;
  components: readonly Component[];
  selected: string;
  state: GraphState;
  base: string;
  onState: (s: GraphState) => void;
  onEvidence: (id: string) => void;
  onClear: () => void;
}) {
  const node = data.nodes.find((n) => n.id === selected) ?? componentNode(selected, components);
  if (!node) return null;
  const { edges } = drawableEdges(data);
  const mine = edges.filter((e) => e.source === selected || e.target === selected);
  const rolls = node.entity === "component" ? componentRollup(data, components).filter((e) => e.data.source === selected || e.data.target === selected) : [];
  const byKind = new Map<string, number>();
  for (const e of mine) byKind.set(e.kind, (byKind.get(e.kind) ?? 0) + 1);
  const focused = state.focus === selected;
  return (
    <section className="rounded-lg border border-accent/40 bg-surface p-3" aria-label="Selected node" data-testid="selection-panel">
      <div className="flex flex-wrap items-baseline gap-2">
        <h2 className="break-all font-semibold">{node.label}</h2>
        <span className="text-xs text-muted">
          {node.entity}
          {node.layer ? ` · ${node.layer}` : ""} · {node.degree} connections
        </span>
      </div>
      {node.file ? <p className="break-all font-mono text-xs text-ink-2">{node.file}</p> : null}
      <Counts counts={countsFor(node.id, components)} />
      <div className="mt-2 flex flex-wrap gap-2">
        {focused ? (
          <>
            <Button onClick={() => onState({ ...state, depth: Math.min(4, state.depth + 1) })} disabled={state.depth >= 4}>
              Expand to depth {Math.min(4, state.depth + 1)}
            </Button>
            <Button onClick={() => onState({ ...state, depth: Math.max(0, state.depth - 1) })} disabled={state.depth <= 0}>
              Reduce depth
            </Button>
          </>
        ) : (
          <Button variant="primary" onClick={() => onState({ ...state, focus: selected, depth: 1 })}>
            {node.entity === "component" ? "Expand component" : "Focus here"}
          </Button>
        )}
        <Button onClick={onClear}>Clear selection</Button>
      </div>
      <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-sm">
        <Link to={node.entity === "component" ? `${base}/trace` : `${base}/trace?from=${encodeURIComponent(node.id)}`}>Follow a recorded flow</Link>
        <Link to={node.entity === "component" ? `${base}/history?component=${encodeURIComponent(node.id)}` : node.file ? `${base}/history?path=${encodeURIComponent(node.file)}` : `${base}/history`}>History</Link>
        <Link to={`${base}/ask?q=${encodeURIComponent(`What is recorded about ${node.label}?`)}`}>Ask about this</Link>
      </div>
      <h3 className="mt-3 text-sm font-semibold">Relationships shown ({mine.length})</h3>
      {byKind.size > 0 ? (
        <ul className="mt-1 flex flex-wrap gap-1" aria-label="Relationship kinds">
          {[...byKind.entries()].map(([k, n]) => (
            <li key={k} className="rounded-md border border-line bg-canvas px-2 py-0.5 text-xs text-ink-2">
              {n} {k.replaceAll("_", " ")}
            </li>
          ))}
        </ul>
      ) : null}
      {mine.length === 0 && rolls.length > 0 ? (
        <>
          <p className="mt-1 text-sm text-ink-2">On this page, counted between components. A line is not a new claim, and the count uses the weakest status in the pair.</p>
          <ul className="mt-1 flex flex-col gap-1">
            {rolls.map((e) => {
              const otherId = e.data.source === selected ? e.data.target : e.data.source;
              const other = components.find((c) => c.id === otherId)?.name ?? otherId ?? "";
              const dir = e.data.source === selected ? "to" : "from";
              return (
                <li key={e.data.id} className="text-sm">
                  <span className="font-medium">{e.data.label}</span> <span className="text-muted">{dir}</span> {other}
                </li>
              );
            })}
          </ul>
          <p className="text-xs text-muted">Expand the component to see the symbols these counts come from.</p>
        </>
      ) : mine.length === 0 ? (
        <p className="text-sm text-muted">
          {node.entity === "component"
            ? "The lines on the map connect symbols inside this component, not the component itself. Select a symbol to open its evidence. The boundary is a stored path rule, not a runtime edge."
            : "None with the current filters."}
        </p>
      ) : (
        <ul className="mt-1 flex max-h-72 flex-col gap-2 overflow-y-auto">
          {mine.slice(0, 50).map((e) => (
            <EdgeRow key={e.id} e={e} nodes={data.nodes} onEvidence={onEvidence} />
          ))}
        </ul>
      )}
    </section>
  );
}

function FilePanel({ node, onOpen, onClear }: { node: ElementData | undefined; onOpen: () => void; onClear: () => void }) {
  if (!node) return null;
  return (
    <section className="rounded-lg border border-accent/40 bg-surface p-3" aria-label="Selected file">
      <h2 className="break-all font-semibold">{node.label}</h2>
      <p className="break-all font-mono text-xs text-ink-2">{node.file}</p>
      <p className="mt-1 text-sm text-ink-2">{node.count ?? 0} symbols in this file. Lines to other files count recorded relationships. They are not new claims.</p>
      <div className="mt-2 flex flex-wrap gap-2">
        <Button variant="primary" onClick={onOpen}>
          Open symbols
        </Button>
        <Button onClick={onClear}>Clear selection</Button>
      </div>
    </section>
  );
}

function CardsView({ data, components, onSelect, onFocus }: { data: GraphResponse; components: readonly Component[]; onSelect: (id: string) => void; onFocus: (id: string) => void }) {
  if (data.nodes.length === 0) return <Empty title="No nodes match these filters" />;
  return (
    <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3" data-testid="graph-cards">
      {data.nodes.map((n) => (
        <li key={n.id} className="flex flex-col gap-1 rounded-lg border border-line bg-surface p-3">
          <span className="break-all font-medium">{n.label}</span>
          <span className="text-xs text-muted">
            {n.entity}
            {n.layer ? ` · ${n.layer}` : ""} · {n.degree} connections
          </span>
          <Counts counts={countsFor(n.id, components)} />
          <div className="mt-1 flex gap-2">
            <Button onClick={() => onSelect(n.id)}>Select</Button>
            <Button onClick={() => onFocus(n.id)}>{n.entity === "component" ? "Expand" : "Focus"}</Button>
          </div>
        </li>
      ))}
    </ul>
  );
}

function ListView({ data, selected, onEvidence }: { data: GraphResponse; selected: string | null; onEvidence: (id: string) => void }) {
  const { edges } = drawableEdges(data);
  const shown = selected ? edges.filter((e) => e.source === selected || e.target === selected) : edges;
  if (shown.length === 0) return <Empty title="No relationships match these filters" />;
  return (
    <ul className="flex flex-col gap-2" data-testid="graph-list">
      {shown.map((e) => (
        <EdgeRow key={e.id} e={e} nodes={data.nodes} onEvidence={onEvidence} />
      ))}
    </ul>
  );
}

type Mode = "graph" | "list" | "cards";

export default function GraphPage() {
  const { repoId = "", sha = "" } = useParams();
  const [sp, setSp] = useSearchParams();
  const state = readGraphState(sp);
  const mode: Mode = sp.get("view") === "list" ? "list" : sp.get("view") === "cards" ? "cards" : "graph";
  const claim = sp.get("claim");
  const [selected, setSelected] = useState<string | null>(state.focus);
  const picked = useRef(false);
  const [q, setQ] = useState(state.q);
  const [openedFile, setOpenedFile] = useState<string | null>(null);
  const [narrow, setNarrow] = useState(false);
  const [layerPick, setLayerPick] = useState<string | null>(null);
  const [scope, setScope] = useState<"core" | "all">("core");
  const searchId = useId();
  const query = graphQuery(state);
  const graph = useQuery({ queryKey: ["graph", repoId, sha, query], queryFn: () => api.graph(repoId, sha, query) });
  // Component counts and paths come from the components endpoint; the graph still renders if it is unavailable.
  const comps = useQuery({ queryKey: ["view", "components", repoId, sha], queryFn: () => api.components(repoId, sha) });
  const components = useMemo(() => comps.data ?? [], [comps.data]);
  const elements = useMemo(() => (graph.data ? toElements(graph.data, components) : []), [graph.data, components]);
  const focusedEls = useMemo(() => canvasElements(elements, true), [elements]);
  const symbolCount = focusedEls.filter((e) => !e.data.source && e.data.entity === "symbol").length;
  const drawn = useMemo(() => {
    if (!graph.data) return [];
    if (!state.focus) return openingDiagram(components, graph.data);
    if (openedFile) return symbolsInFile(focusedEls, openedFile);
    if (symbolCount > 8) {
      const rolled = fileRollup(focusedEls);
      if (rolled.some((e) => e.data.entity === "file")) return rolled;
    }
    return focusedEls;
  }, [graph.data, components, state.focus, openedFile, symbolCount, focusedEls]);
  const useFiles = drawn.some((e) => e.data.entity === "file");
  const mapNodes = drawn.filter((e) => !e.data.source);
  const layersOnMap = LAYERS.filter((l) => mapNodes.some((n) => n.data.layer === l));
  const defaultLayer = narrow && !state.focus && mapNodes.length > 8 ? (layersOnMap.includes("frontend") ? "frontend" : (layersOnMap[0] ?? null)) : null;
  const effectiveLayer = !state.focus ? (layerPick === "all" ? null : (layerPick ?? defaultLayer)) : null;
  const coreOn = !state.focus && !narrow && !effectiveLayer && scope === "core" && mapNodes.length > 12 && mapNodes.some((n) => coreLayer(n.data.layer));
  const shown = useMemo(() => {
    const allow = (layer: string | undefined) => {
      if (effectiveLayer) return layer === effectiveLayer;
      if (coreOn) return coreLayer(layer);
      return true;
    };
    if (!effectiveLayer && !coreOn) return drawn;
    const ids = new Set(drawn.filter((e) => !e.data.source && allow(e.data.layer)).map((e) => e.data.id));
    return drawn.filter((e) => (!e.data.source ? ids.has(e.data.id) : !!e.data.source && !!e.data.target && ids.has(e.data.source) && ids.has(e.data.target)));
  }, [drawn, effectiveLayer, coreOn]);
  const pictured = useMemo(() => {
    if (!useFiles) return shown;
    const fileEdges = shown.filter((e) => e.data.source);
    if (fileEdges.length <= 30 || !selected?.startsWith("file::")) {
      if (fileEdges.length <= 30) return shown;
      return shown.filter((e) => !e.data.source);
    }
    const nodes = shown.filter((e) => !e.data.source);
    const edges = shown.filter((e) => e.data.source === selected || e.data.target === selected);
    return [...nodes, ...edges];
  }, [shown, useFiles, selected]);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 720px)");
    const apply = () => setNarrow(mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);
  useEffect(() => {
    setOpenedFile(null);
  }, [state.focus]);
  // A component id has no incident edges: the relationships belong to its symbols. Don't preselect it, or the panel
  // says "0" and the canvas dims the neighborhood the user came to see. A symbol focus stays selected (list view).
  useEffect(() => {
    if (picked.current || !graph.data || !selected) return;
    const node = graph.data.nodes.find((n) => n.id === selected);
    if (node?.entity !== "component") return;
    const incident = drawableEdges(graph.data).edges.some((e) => e.source === selected || e.target === selected);
    if (!incident) setSelected(null);
  }, [graph.data, selected]);
  const choose = useCallback((id: string | null) => {
    picked.current = true;
    setSelected(id);
  }, []);

  const setState = (s: GraphState) => setSp(writeGraphState(s, sp));
  const setParam = (k: string, v: string | null) =>
    setSp((p) => {
      const n = new URLSearchParams(p);
      if (v) n.set(k, v);
      else n.delete(k);
      return n;
    });
  const openEvidence = useCallback(
    (id: string) =>
      setSp((p) => {
        const n = new URLSearchParams(p);
        n.set("claim", id);
        return n;
      }),
    [setSp],
  );
  const describe = useCallback(
    (id: string) => {
      const fileNode = id.startsWith("file::") ? drawn.find((e) => e.data.id === id)?.data : undefined;
      if (fileNode) return `${fileNode.label}, file, ${fileNode.count ?? 0} symbols`;
      const n = graph.data?.nodes.find((x) => x.id === id) ?? componentNode(id, components);
      if (!n) return "";
      const rel = graph.data ? drawableEdges(graph.data).edges.filter((e) => e.source === id || e.target === id).length : 0;
      return `${n.label}, ${n.entity}${n.layer ? `, ${n.layer}` : ""}, ${rel} relationships shown`;
    },
    [graph.data, components, drawn],
  );
  const submitSearch = (e: FormEvent) => {
    e.preventDefault();
    setState({ ...state, q });
  };

  return (
    <>
      <div className="mb-2 flex flex-col gap-2 md:flex-row md:flex-wrap md:items-center">
        <h1 className="text-lg font-semibold tracking-tight">Architecture</h1>
        <form onSubmit={submitSearch} role="search" className="flex min-w-0 flex-1 gap-2">
            <label htmlFor={searchId} className="sr-only">
              Search nodes
            </label>
            <input id={searchId} type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search components and symbols" className="tap min-w-0 flex-1 rounded-md border border-line-strong px-3" />
            <Button type="submit" className="shrink-0">Search</Button>
          </form>
          <div role="group" aria-label="View as" className="inline-flex shrink-0 rounded-md border border-line-strong">
            {(["graph", "list", "cards"] as const).map((m) => (
              <button key={m} type="button" aria-pressed={mode === m} onClick={() => setParam("view", m === "graph" ? null : m)} className={`tap px-3 text-sm ${mode === m ? "bg-accent text-accent-ink" : "bg-surface"}`}>
                {m === "graph" ? "Graph" : m === "list" ? "List" : "Cards"}
              </button>
            ))}
          </div>
      </div>
      <Filters state={state} onChange={setState} />
      {state.focus ? (
        <p className="mb-2 flex flex-wrap items-center gap-2 text-sm" data-testid="focus-bar">
          Focused on <code className="break-all">{graph.data ? nodeName(graph.data.nodes, state.focus) : splitSymbol(state.focus).name}</code> at depth {state.depth}
          {useFiles ? <span className="text-ink-2">Files first. Select one to draw the lines recorded from it. A line is a count, not a new claim.</span> : null}
          {openedFile ? <span className="text-ink-2">Symbols in {openedFile.split("/").pop()}, plus the symbols they record a relationship with.</span> : null}
          <Button onClick={() => setState({ ...state, focus: null, depth: 1 })}>Back to components</Button>
          {openedFile ? <Button onClick={() => setOpenedFile(null)}>Back to files</Button> : null}
        </p>
      ) : null}

      {graph.isPending ? (
        <Loading label="Loading graph" />
      ) : graph.isError ? (
        <ErrorState error={graph.error} what="The architecture graph" />
      ) : (
        <>
          <div className="grid items-start gap-3 lg:grid-cols-[1fr_18rem]">
            <div className="min-w-0">
              {graph.data.nodes.length === 0 ? (
                <Empty title="Nothing matches these filters">Try including inferred relationships or clearing the search.</Empty>
              ) : mode === "graph" ? (
                <>
                  {!state.focus ? (
                    <div className="mb-2 flex flex-col gap-2">
                      {narrow && mapNodes.length > 8 ? (
                        <div role="group" aria-label="Layer in view" className="flex gap-1 overflow-x-auto">
                          <button type="button" aria-pressed={effectiveLayer === null} onClick={() => setLayerPick("all")} className={`tap shrink-0 rounded-md border px-3 text-sm ${effectiveLayer === null ? "border-accent bg-accent text-accent-ink" : "border-line-strong bg-surface"}`}>
                            All layers
                          </button>
                          {layersOnMap.map((l) => (
                            <button key={l} type="button" aria-pressed={effectiveLayer === l} onClick={() => setLayerPick(l)} className={`tap shrink-0 rounded-md border px-3 text-sm capitalize ${effectiveLayer === l ? "border-accent bg-accent text-accent-ink" : "border-line-strong bg-surface"}`}>
                              {l}
                            </button>
                          ))}
                        </div>
                      ) : null}
                      {!narrow && mapNodes.length > 12 ? (
                        <div role="group" aria-label="How much of the map to show" className="flex gap-1">
                          <button type="button" aria-pressed={scope === "core"} onClick={() => setScope("core")} className={`tap rounded-md border px-3 text-sm ${scope === "core" ? "border-accent bg-accent text-accent-ink" : "border-line-strong bg-surface"}`}>
                            Core layers
                          </button>
                          <button type="button" aria-pressed={scope === "all"} onClick={() => setScope("all")} className={`tap rounded-md border px-3 text-sm ${scope === "all" ? "border-accent bg-accent text-accent-ink" : "border-line-strong bg-surface"}`}>
                            All layers
                          </button>
                        </div>
                      ) : null}
                      {effectiveLayer ? <p className="text-xs text-ink-2">One layer is open so the names stay readable. Select a component to list lines that leave it.</p> : null}
                      {coreOn ? <p className="text-xs text-ink-2">Code layers are in the frame. All layers adds infra, docs, and tests.</p> : null}
                    </div>
                  ) : null}
                  {narrow && effectiveLayer ? (
                    <ul className="grid gap-2" aria-label={`${effectiveLayer} components`}>
                      {shown.filter((e) => !e.data.source).map((n) => {
                        const links = drawn.filter((e) => e.data.source && (e.data.source === n.data.id || e.data.target === n.data.id));
                        return (
                          <li key={n.data.id}>
                            <button
                              type="button"
                              aria-pressed={selected === n.data.id}
                              onClick={() => choose(selected === n.data.id ? null : n.data.id)}
                              className="min-h-11 w-full rounded-lg border-2 bg-[#1b3330] px-3 py-2 text-left text-[#f4faf7]"
                              style={{ borderColor: selected === n.data.id ? "#7eb6ff" : layerColor(n.data.layer) }}
                            >
                              <span className="block text-sm font-semibold">{n.data.label}</span>
                              <span className="mt-1 block text-xs text-[#c5d2cb]">
                                {links.length
                                  ? links
                                      .slice(0, 3)
                                      .map((e) => {
                                        const otherId = e.data.source === n.data.id ? e.data.target : e.data.source;
                                        const other = components.find((c) => c.id === otherId)?.name ?? otherId;
                                        const dir = e.data.source === n.data.id ? "to" : "from";
                                        return `${e.data.label} ${dir} ${other}`;
                                      })
                                      .join(" · ")
                                  : "No line on this page leaves this component."}
                              </span>
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  ) : (
                  <GraphCanvas
                  elements={pictured}
                  layout={state.focus && !useFiles ? "neighborhood" : "map"}
                  selected={selected}
                  onSelect={choose}
                  onExpand={(id) => {
                    if (id.startsWith("file::")) {
                      setOpenedFile(id.slice("file::".length));
                      setSelected(null);
                      return;
                    }
                    const node = graph.data?.nodes.find((n) => n.id === id);
                    if (!node || node.entity === "component") {
                      picked.current = false;
                      setSelected(null);
                    }
                    setOpenedFile(null);
                    setState({ ...state, focus: id, depth: state.focus === id ? Math.min(4, state.depth + 1) : 1 });
                  }}
                  onEdge={openEvidence}
                  describe={describe}
                />
                  )}
                </>
              ) : mode === "list" ? (
                <ListView data={graph.data} selected={selected} onEvidence={openEvidence} />
              ) : (
                <CardsView data={graph.data} components={components} onSelect={choose} onFocus={(id) => setState({ ...state, focus: id, depth: 1 })} />
              )}
            </div>
            <div className="flex min-w-0 flex-col gap-2">
              <p className="text-sm text-muted" data-testid="graph-summary">
                {graph.data.nodes.length} nodes, {drawableEdges(graph.data).edges.length} relationships
                {graph.data.truncated ? `, truncated at ${graph.data.limit}` : ""}
              </p>
              {!state.focus ? (
                <p className="text-xs text-ink-2">Lines between neighboring columns are on the map. A line counts relationships on this page. The weakest status in the pair sets the line. Select a component to read every link that touches it, including ones that skip a column. A missing line is not proof that nothing connects.</p>
              ) : (
                <p className="text-xs text-muted">{useFiles ? "Files first. Select a file to emphasize the lines recorded from it. Enter opens its symbols. A line is a count, not a new claim." : "Select a symbol to label its lines. List shows every relationship."}</p>
              )}
              {selected && selected.startsWith("file::") ? (
                <FilePanel node={drawn.find((e) => e.data.id === selected)?.data} onOpen={() => setOpenedFile(selected.slice("file::".length))} onClear={() => choose(null)} />
              ) : selected && (graph.data.nodes.some((n) => n.id === selected) || components.some((c) => c.id === selected)) ? (
                <SelectionPanel data={graph.data} components={components} selected={selected} state={state} base={snapshotBase(repoId, sha)} onState={setState} onEvidence={openEvidence} onClear={() => choose(null)} />
              ) : !state.focus ? (
                <RecordedLinks
                  rolls={componentRollup(graph.data, components).filter((e) => {
                    const ids = new Set(pictured.filter((n) => !n.data.source).map((n) => n.data.id));
                    return !!e.data.source && !!e.data.target && ids.has(e.data.source) && ids.has(e.data.target);
                  })}
                  nameOf={(id) => components.find((c) => c.id === id)?.name ?? id ?? ""}
                  onPick={choose}
                />
              ) : (
                <p className="rounded-lg border border-dashed border-line-strong p-3 text-sm text-ink-2">Select a node to see its relationships and open their evidence.</p>
              )}
              <Legend />
              <HiddenCounts counts={graph.data.hidden_counts} extra={drawableEdges(graph.data).hidden} reviewHref={`${snapshotBase(repoId, sha)}/review`} />
              {comps.isError ? <p className="text-xs text-muted">Component counts are not available from the API yet.</p> : null}
            </div>
          </div>
        </>
      )}
      <EvidenceDrawer repoId={repoId} sha={sha} claimId={claim} onClose={() => setParam("claim", null)} />
    </>
  );
}
