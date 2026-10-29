import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, type Component } from "../../api/client";
import { snapshotBase } from "../../app/nav";
import { Button } from "../../ui/States";
import { GraphCanvas, RecordedLinks } from "../graph/GraphCanvas";
import { componentRollup, graphQuery, nextGraphLimit, openingDiagram, readGraphState, type ElementData } from "../graph/graphModel";
import { CODE_LAYERS, LAYERS, isLayer, layerColor } from "../layers";
import { askHref } from "../ask/recordedQuestion";
import { useSubject } from "../subject/useSubject";
import { withAt } from "../subject/subject";

/** The opening picture: stored components, and counts of recorded relationships between them. */
export function SystemMap() {
  const { repoId = "", sha = "" } = useParams();
  const navigate = useNavigate();
  const base = snapshotBase(repoId, sha);
  const [limit, setLimit] = useState(300);
  const query = graphQuery({ ...readGraphState(new URLSearchParams()), limit });
  const comps = useQuery({ queryKey: ["view", "components", repoId, sha], queryFn: () => api.components(repoId, sha) });
  const graph = useQuery({ queryKey: ["graph", repoId, sha, query], queryFn: () => api.graph(repoId, sha, query) });
  const [selected, setSelected] = useState<string | null>(null);
  const { subject, setSubject } = useSubject();
  const subjectId = subject?.kind === "component" ? subject.id : null;
  useEffect(() => {
    if (subjectId) setSelected(subjectId);
  }, [subjectId]);
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
  const pick = (id: string | null) => {
    setSelected(id);
    if (!id) {
      setSubject(null);
      return;
    }
    const node = nodes.find((n) => n.data.id === id);
    setSubject({ kind: "component", id, label: node?.data.label ?? id });
  };
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
      <div className="flex flex-col gap-4">
        <div className="min-w-0">
          {phoneList ? (
            <div className="mb-2 max-w-full overflow-x-auto">
              <div role="group" aria-label="Layer in view" className="seg">
              {layersOnMap.map((l) => (
                <button key={l} type="button" aria-pressed={effectiveLayer === l} onClick={() => setLayerPick(l)} className="capitalize">
                  {l}
                </button>
              ))}
              </div>
            </div>
          ) : null}
          {many && !phoneList ? (
            <div role="group" aria-label="How much of the map to show" className="seg mb-2">
              <button type="button" aria-pressed={scope === "core"} onClick={() => setScope("core")}>
                Core layers
              </button>
              <button type="button" aria-pressed={scope === "all"} onClick={() => setScope("all")}>
                All layers
              </button>
            </div>
          ) : null}
          {phoneList && effectiveLayer ? (
            <ul className="border-t border-white/10" aria-label={`${effectiveLayer} components`}>
              {shown.filter((e) => !e.data.source).map((n) => {
                const links = diagram.filter((e) => e.data.source && (e.data.source === n.data.id || e.data.target === n.data.id));
                return (
                  <li key={n.data.id}>
                    <button
                      type="button"
                      aria-pressed={selected === n.data.id}
                      onClick={() => pick(selected === n.data.id ? null : n.data.id)}
                      className={`flex min-h-11 w-full items-start gap-3 border-b border-white/8 px-1 py-3 text-left text-ink ${selected === n.data.id ? "bg-white/[0.04]" : ""}`}
                    >
                      <span className="mt-1 h-7 w-0.5 shrink-0 rounded-full" style={{ background: layerColor(n.data.layer) }} aria-hidden="true" />
                      <span className="min-w-0">
                      <span className="block text-[15px] font-medium tracking-[-0.02em]">{n.data.label}</span>
                      <span className="mt-0.5 block text-xs text-muted">
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
            onSelect={pick}
            onExpand={(id) => {
              const node = nodes.find((n) => n.data.id === id);
              const next = { kind: "component" as const, id, label: node?.data.label ?? id };
              setSubject(next);
              navigate(withAt(`${base}/graph?focus=${encodeURIComponent(id)}`, next));
            }}
            onEdge={() => undefined}
            describe={(id) => {
              const n = nodes.find((x) => x.data.id === id)?.data;
              return n ? `${n.label}, ${n.layer ?? "component"}` : "";
            }}
          />
          )}
          {graph.data?.truncated ? (
            <div className="mt-2 flex flex-col items-start gap-2">
              <p className="text-xs text-ink-2">This page of relationships is truncated at {graph.data.limit}. Counts use only that page.</p>
              {nextGraphLimit(limit) ? (
                <Button onClick={() => setLimit(nextGraphLimit(limit)!)}>Show more recorded relationships</Button>
              ) : (
                <p className="text-xs text-muted">This page stops at {graph.data.limit} relationships, the API cap. Relationships beyond it are not in this view.</p>
              )}
            </div>
          ) : null}
        </div>
        {selectedNode ? (
          <MapInspector node={selectedNode.data} components={components} rolls={rolls} base={base} onClear={() => pick(null)} onPick={pick} />
        ) : (
          <RecordedLinks rolls={allRolls} nameOf={(id) => components.find((c) => c.id === id)?.name ?? id ?? ""} onPick={pick} />
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
  const { subject } = useSubject();
  const to = (href: string) => withAt(href, subject);
  return (
    <div className="mt-2 border-t border-white/10 pt-3" aria-label="Selected component">
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
        <Link to={to(`${base}/graph?focus=${encodeURIComponent(node.id)}`)} className="tap inline-flex items-center rounded-md bg-ink px-3 text-sm font-medium text-canvas no-underline hover:no-underline">
          Open on the graph
        </Link>
        <Link to={to(`${base}/trace`)} className="tap inline-flex items-center rounded-md border border-line-strong px-3 text-sm text-ink no-underline">
          Follow a recorded flow
        </Link>
        <Link to={to(`${base}/history?component=${encodeURIComponent(node.id)}`)} className="tap inline-flex items-center rounded-md border border-line-strong px-3 text-sm text-ink no-underline">
          History
        </Link>
        {askHref(base, comp?.paths ?? []) ? (
          <Link to={to(askHref(base, comp?.paths ?? [])!)} className="tap inline-flex items-center rounded-md border border-line-strong px-3 text-sm text-ink no-underline">
            Ask
          </Link>
        ) : null}
        <Button onClick={onClear}>Clear</Button>
      </div>
    </div>
  );
}
