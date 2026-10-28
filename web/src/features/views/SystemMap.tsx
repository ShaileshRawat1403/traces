import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, type Component } from "../../api/client";
import { snapshotBase } from "../../app/nav";
import { Button } from "../../ui/States";
import { GraphCanvas, RecordedLinks } from "../graph/GraphCanvas";
import { componentRollup, graphQuery, openingDiagram, readGraphState, type ElementData } from "../graph/graphModel";
import { CODE_LAYERS, LAYERS, isLayer, layerColor } from "../layers";

/** The opening picture: stored components, and counts of recorded relationships between them. */
export function SystemMap() {
  const { repoId = "", sha = "" } = useParams();
  const navigate = useNavigate();
  const base = snapshotBase(repoId, sha);
  const query = graphQuery(readGraphState(new URLSearchParams()));
  const comps = useQuery({ queryKey: ["view", "components", repoId, sha], queryFn: () => api.components(repoId, sha) });
  const graph = useQuery({ queryKey: ["graph", repoId, sha, query], queryFn: () => api.graph(repoId, sha, query) });
  const [selected, setSelected] = useState<string | null>(null);
  const [scope, setScope] = useState<"core" | "all">("core");
  const [narrow, setNarrow] = useState(false);
  const [layerPick, setLayerPick] = useState<string | null>(null);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 720px)");
    const apply = () => setNarrow(mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);
  const components = comps.data ?? [];
  const diagram = useMemo(() => (graph.data ? openingDiagram(components, graph.data) : []), [graph.data, components]);
  const nodes = diagram.filter((e) => !e.data.source);
  const core = (layer: string | undefined) => isLayer(layer) && CODE_LAYERS[layer];
  const many = nodes.length > 12 && nodes.some((n) => core(n.data.layer));
  const layersOnMap = LAYERS.filter((l) => nodes.some((n) => n.data.layer === l));
  const phoneList = narrow && nodes.length > 8;
  const defaultLayer = phoneList ? (layersOnMap.includes("frontend") ? "frontend" : (layersOnMap[0] ?? null)) : null;
  const effectiveLayer = phoneList ? (layerPick === "all" ? null : (layerPick ?? defaultLayer)) : null;
  const coreOn = many && scope === "core" && !phoneList;
  const shown = useMemo(() => {
    const allow = (layer: string | undefined) => {
      if (effectiveLayer) return layer === effectiveLayer;
      if (coreOn) return core(layer);
      return true;
    };
    if (!effectiveLayer && !coreOn) return diagram;
    const ids = new Set(nodes.filter((n) => allow(n.data.layer)).map((n) => n.data.id));
    return diagram.filter((e) => (!e.data.source ? ids.has(e.data.id) : !!e.data.source && !!e.data.target && ids.has(e.data.source) && ids.has(e.data.target)));
  }, [diagram, coreOn, effectiveLayer, nodes]);
  if (comps.isPending || graph.isPending) return <p className="mb-3 text-sm text-muted">Loading the architecture.</p>;
  if (!nodes.length) return null;
  const selectedNode = shown.find((n) => n.data.id === selected);
  const allRolls = graph.data ? componentRollup(graph.data, components) : [];
  const rolls = selected ? allRolls.filter((e) => e.data.source === selected || e.data.target === selected) : [];

  return (
    <section className="mb-4" aria-label="Architecture map">
      <div className="grid items-start gap-3 lg:grid-cols-[minmax(0,1fr)_17rem]">
        <div className="min-w-0">
          {phoneList ? (
            <div role="group" aria-label="Layer in view" className="mb-2 flex gap-1 overflow-x-auto">
              {layersOnMap.map((l) => (
                <button key={l} type="button" aria-pressed={effectiveLayer === l} onClick={() => setLayerPick(l)} className={`tap shrink-0 rounded-md border px-3 text-sm capitalize ${effectiveLayer === l ? "border-accent bg-accent text-accent-ink" : "border-line-strong bg-surface"}`}>
                  {l}
                </button>
              ))}
            </div>
          ) : null}
          {many && !phoneList ? (
            <div role="group" aria-label="How much of the map to show" className="mb-2 flex gap-1">
              <button type="button" aria-pressed={scope === "core"} onClick={() => setScope("core")} className={`tap rounded-md border px-3 text-sm ${scope === "core" ? "border-accent bg-accent text-accent-ink" : "border-line-strong bg-surface"}`}>
                Core layers
              </button>
              <button type="button" aria-pressed={scope === "all"} onClick={() => setScope("all")} className={`tap rounded-md border px-3 text-sm ${scope === "all" ? "border-accent bg-accent text-accent-ink" : "border-line-strong bg-surface"}`}>
                All layers
              </button>
            </div>
          ) : null}
          {phoneList && effectiveLayer ? (
            <ul className="grid gap-2" aria-label={`${effectiveLayer} components`}>
              {shown.filter((e) => !e.data.source).map((n) => {
                const links = diagram.filter((e) => e.data.source && (e.data.source === n.data.id || e.data.target === n.data.id));
                return (
                  <li key={n.data.id}>
                    <button
                      type="button"
                      aria-pressed={selected === n.data.id}
                      onClick={() => setSelected(selected === n.data.id ? null : n.data.id)}
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
            elements={shown}
            layout="map"
            selected={selected}
            onSelect={setSelected}
            onExpand={(id) => navigate(`${base}/graph?focus=${encodeURIComponent(id)}`)}
            onEdge={() => undefined}
            describe={(id) => {
              const n = nodes.find((x) => x.data.id === id)?.data;
              return n ? `${n.label}, ${n.layer ?? "component"}` : "";
            }}
          />
          )}
          {graph.data?.truncated ? <p className="mt-2 text-xs text-ink-2">This page of relationships is truncated at {graph.data.limit}. Counts use only that page.</p> : null}
        </div>
        {selectedNode ? (
          <MapInspector node={selectedNode.data} components={components} rolls={rolls} base={base} onClear={() => setSelected(null)} onPick={setSelected} />
        ) : (
          <RecordedLinks rolls={allRolls} nameOf={(id) => components.find((c) => c.id === id)?.name ?? id ?? ""} onPick={setSelected} />
        )}
      </div>
    </section>
  );
}

function MapInspector({
  node,
  components,
  rolls,
  base,
  onClear,
  onPick,
}: {
  node: ElementData;
  components: readonly Component[];
  rolls: { data: ElementData }[];
  base: string;
  onClear: () => void;
  onPick: (id: string) => void;
}) {
  const comp = components.find((c) => c.id === node.id);
  return (
    <div className="mt-2 rounded-lg border border-accent/40 bg-surface p-3" aria-label="Selected component">
      <div className="flex flex-wrap items-baseline gap-2">
        <h3 className="font-semibold">{node.label}</h3>
        <span className="text-xs capitalize text-muted">{node.layer}</span>
      </div>
      {comp ? <p className="mt-1 break-all font-mono text-xs text-ink-2">{comp.paths.join(", ")}</p> : null}
      {rolls.length ? (
        <ul className="mt-2 flex flex-col gap-1 text-sm">
          {rolls.map((e) => {
            const otherId = e.data.source === node.id ? e.data.target : e.data.source;
            const other = components.find((c) => c.id === otherId)?.name ?? otherId ?? "";
            const dir = e.data.source === node.id ? "to" : "from";
            return (
              <li key={e.data.id}>
                <button type="button" onClick={() => otherId && onPick(otherId)} className="text-left hover:underline">
                  <span className="font-medium">{e.data.label}</span> <span className="text-muted">{dir}</span> {other}
                </button>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-ink-2">No relationship on this page leaves this component. That is not proof that nothing connects.</p>
      )}
      <div className="mt-2 flex flex-wrap gap-2">
        <Link to={`${base}/graph?focus=${encodeURIComponent(node.id)}`} className="tap inline-flex items-center rounded-md bg-accent px-3 text-sm font-medium text-accent-ink no-underline">
          Open on the graph
        </Link>
        <Link to={`${base}/trace`} className="tap inline-flex items-center rounded-md border border-line-strong px-3 text-sm text-ink no-underline">
          Follow a recorded flow
        </Link>
        <Link to={`${base}/history?component=${encodeURIComponent(node.id)}`} className="tap inline-flex items-center rounded-md border border-line-strong px-3 text-sm text-ink no-underline">
          History
        </Link>
        <Link to={`${base}/ask?q=${encodeURIComponent(`What is recorded about ${node.label}?`)}`} className="tap inline-flex items-center rounded-md border border-line-strong px-3 text-sm text-ink no-underline">
          Ask
        </Link>
        <Button onClick={onClear}>Clear</Button>
      </div>
    </div>
  );
}
