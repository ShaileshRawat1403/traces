import type { Component, GraphEdge, GraphNode, GraphResponse } from "../../api/client";
import { presentStatus } from "../../status/status";

/** Edges the architecture graph may draw, plus client-side hidden counts (rejected never drawn as architecture). */
export function drawableEdges(data: Pick<GraphResponse, "edges">) {
  const edges: GraphEdge[] = [];
  const hidden: Record<string, number> = {};
  for (const e of data.edges) {
    const p = presentStatus(e, "default");
    if (p.hidden || p.line === "none") hidden[e.status] = (hidden[e.status] ?? 0) + 1;
    else edges.push(e);
  }
  return { edges, hidden };
}

// ---------------------------------------------------------------- URL state <-> graph query (CONTRACTS.md 4.8)

export const STATUS_FILTERS = ["verified", "observed", "unvalidated", "missing_location"] as const;
export type StatusFilter = (typeof STATUS_FILTERS)[number];
/** Unvalidated and missing_location (both "Inferred") are off by default; rejected is never requested. */
export const DEFAULT_STATUS: readonly StatusFilter[] = ["verified", "observed"];
export const LAYERS: readonly Component["layer"][] = ["frontend", "api", "backend", "data", "infra", "docs", "tests", "other"];

export interface GraphState {
  focus: string | null;
  depth: number;
  layer: string[];
  rel: string[];
  status: StatusFilter[];
  q: string;
  limit: number;
}

const clampDepth = (n: number) => (Number.isFinite(n) ? Math.min(4, Math.max(0, Math.trunc(n))) : 1);

export function readGraphState(sp: URLSearchParams): GraphState {
  const st = sp.getAll("status").filter((s): s is StatusFilter => (STATUS_FILTERS as readonly string[]).includes(s));
  return {
    focus: sp.get("focus") || null,
    depth: sp.has("depth") ? clampDepth(Number(sp.get("depth"))) : 1,
    layer: sp.getAll("layer"),
    rel: sp.getAll("rel"),
    status: sp.has("status") || sp.has("status_set") ? st : [...DEFAULT_STATUS],
    q: sp.get("q") ?? "",
    limit: Number(sp.get("limit")) || 300,
  };
}

export function writeGraphState(s: GraphState, keep?: URLSearchParams): URLSearchParams {
  const n = new URLSearchParams();
  for (const k of ["view", "claim"]) {
    const v = keep?.get(k);
    if (v) n.set(k, v);
  }
  if (s.focus) n.set("focus", s.focus);
  if (s.depth !== 1) n.set("depth", String(s.depth));
  s.layer.forEach((l) => n.append("layer", l));
  s.rel.forEach((r) => n.append("rel", r));
  const isDefault = s.status.length === DEFAULT_STATUS.length && DEFAULT_STATUS.every((d) => s.status.includes(d));
  if (!isDefault) {
    n.set("status_set", "1"); // distinguishes "none selected" from "default"
    s.status.forEach((x) => n.append("status", x));
  }
  if (s.q) n.set("q", s.q);
  if (s.limit !== 300) n.set("limit", String(s.limit));
  return n;
}

/** Query string for GET .../graph. Arrays repeat the key, as FastAPI expects. include_rejected is never sent. */
export function graphQuery(s: GraphState): string {
  const n = new URLSearchParams();
  if (s.focus) {
    n.set("focus", s.focus);
    n.set("depth", String(s.depth));
  }
  s.layer.forEach((l) => n.append("layer", l));
  s.rel.forEach((r) => n.append("rel", r));
  s.status.forEach((x) => n.append("status", x));
  if (s.q.trim()) n.set("q", s.q.trim());
  n.set("limit", String(s.limit));
  return `?${n.toString()}`;
}

// ---------------------------------------------------------------- compound grouping

/** Component that owns a file: the component whose path is the longest prefix of the file (paths from the API's rule). */
export function componentForFile(file: string | null | undefined, components: readonly Component[]): Component | null {
  if (!file) return null;
  let best: Component | null = null;
  let bestLen = -1;
  for (const c of components) {
    for (const p of c.paths) {
      const prefix = p.endsWith("/") ? p : `${p}/`;
      if ((file === p || file.startsWith(prefix)) && p.length > bestLen) {
        best = c;
        bestLen = p.length;
      }
    }
  }
  return best;
}

export interface ElementData {
  id: string;
  label: string;
  parent?: string;
  entity?: string;
  layer?: string;
  source?: string;
  target?: string;
  tone?: string;
  line?: string;
  /** Visual weight for a rolled-up count. Not a claim. */
  weight?: number;
}

/** Opening frame: components only, when the page mixes symbols in. A focused neighborhood is drawn in full. */
export function canvasElements<T extends { data: ElementData }>(elements: readonly T[], focused: boolean): T[] {
  if (focused) return [...elements];
  const nodes = elements.filter((e) => !e.data.source);
  const comps = nodes.filter((e) => e.data.entity === "component");
  if (comps.length === 0 || comps.length === nodes.length) return [...elements];
  const ids = new Set(comps.map((n) => n.data.id));
  const edges = elements.filter((e) => {
    const src = e.data.source;
    const tgt = e.data.target;
    return !!src && !!tgt && ids.has(src) && ids.has(tgt);
  });
  return [...comps, ...edges];
}

/** Unfocused canvas: every stored component, plus any component-to-component edges already on the page. */
export function openingMap(components: readonly { id: string; name: string; layer: string }[], elements: readonly { data: ElementData }[]): { data: ElementData }[] {
  if (components.length === 0) return canvasElements(elements, false);
  const ids = new Set(components.map((c) => c.id));
  const nodes = components.map((c) => ({ data: { id: c.id, label: c.name, entity: "component", layer: c.layer } }));
  const edges = elements.filter((e) => {
    const src = e.data.source;
    const tgt = e.data.target;
    return !!src && !!tgt && ids.has(src) && ids.has(tgt);
  });
  return [...nodes, ...edges];
}

/**
 * Count recorded relationships between components.
 * A symbol edge is counted only when both files resolve to components, and those components differ.
 * Rejected edges are already dropped by drawableEdges. Same-component edges stay off this map;
 * they appear when the component is expanded. The line uses the weakest status in the pair,
 * so a mix is not drawn as verified. Counts are from this graph page, which may be truncated.
 */
export function componentRollup(data: GraphResponse, components: readonly Component[]): { data: ElementData }[] {
  const nodes = new Map(data.nodes.map((n) => [n.id, n]));
  const owner = (id: string): string | null => {
    const n = nodes.get(id);
    if (!n) return null;
    if (n.entity === "component") return n.id;
    return componentForFile(n.file, components)?.id ?? null;
  };
  const buckets = new Map<string, { source: string; target: string; n: number; kinds: Map<string, number>; rank: number }>();
  for (const e of drawableEdges(data).edges) {
    const source = owner(e.source);
    const target = owner(e.target);
    if (!source || !target || source === target) continue;
    const key = `${source}\0${target}`;
    let row = buckets.get(key);
    if (!row) {
      row = { source, target, n: 0, kinds: new Map(), rank: 0 };
      buckets.set(key, row);
    }
    row.n += 1;
    row.kinds.set(e.kind, (row.kinds.get(e.kind) ?? 0) + 1);
    const rank = e.status === "unvalidated" || e.status === "missing_location" ? 2 : e.status === "observed" ? 1 : 0;
    if (rank > row.rank) row.rank = rank;
  }
  return [...buckets.values()]
    .sort((a, b) => a.source.localeCompare(b.source) || a.target.localeCompare(b.target))
    .map((row) => {
      const top = [...row.kinds.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
      const kind = top.length === 1 ? `${row.n} ${top[0]![0].replaceAll("_", " ")}` : String(row.n);
      const tone = row.rank === 2 ? "inferred" : row.rank === 1 ? "observed" : "verified";
      const line = row.rank === 2 ? "dashed" : row.rank === 1 ? "thin" : "solid";
      return {
        data: {
          id: `rollup::${row.source}::${row.target}`,
          label: kind,
          source: row.source,
          target: row.target,
          entity: "rollup",
          tone,
          line,
          weight: Math.min(6, 1.6 + Math.log2(row.n)),
        },
      };
    });
}

/** Opening picture: stored components in layer bands, with page-level relationship counts between them. */
export function openingDiagram(components: readonly Component[], data: GraphResponse): { data: ElementData }[] {
  if (components.length === 0) return openingMap([], toElements(data, []));
  const nodes = components.map((c) => ({ data: { id: c.id, label: c.name, entity: "component", layer: c.layer } }));
  return [...nodes, ...componentRollup(data, components)];
}

/** Cytoscape elements: component nodes become compound parents of the symbol nodes inside their paths. */
export function toElements(data: GraphResponse, components: readonly Component[]): { data: ElementData }[] {
  const ids = new Set(data.nodes.map((n) => n.id));
  const parentOf = (n: GraphNode): string | undefined => {
    if (n.entity === "component") return undefined;
    const c = componentForFile(n.file, components);
    return c && ids.has(c.id) ? c.id : undefined;
  };
  const nodes = data.nodes.map((n) => ({ data: { id: n.id, label: n.label, entity: n.entity, layer: n.layer || undefined, parent: parentOf(n) } }));
  const { edges } = drawableEdges(data);
  return [
    ...nodes,
    ...edges
      .filter((e) => ids.has(e.source) && ids.has(e.target))
      .map((e) => {
        const p = presentStatus(e, "default");
        return { data: { id: e.id, label: e.kind, source: e.source, target: e.target, tone: p.tone, line: p.line } };
      }),
  ];
}

// ---------------------------------------------------------------- keyboard navigation

export type Direction = "up" | "down" | "left" | "right";
export interface Pos {
  id: string;
  x: number;
  y: number;
}

/**
 * Nearest node in a direction (screen coordinates, y grows downward). Candidates must lie within a 45 degree cone;
 * distance is weighted to prefer nodes aligned with the direction.
 */
export function nextInDirection(nodes: readonly Pos[], fromId: string | null, dir: Direction): string | null {
  if (nodes.length === 0) return null;
  const from = nodes.find((n) => n.id === fromId);
  if (!from) {
    // No selection: start at the top-left-most node.
    return [...nodes].sort((a, b) => a.y + a.x - (b.y + b.x))[0]!.id;
  }
  let best: string | null = null;
  let bestScore = Infinity;
  for (const n of nodes) {
    if (n.id === from.id) continue;
    const dx = n.x - from.x;
    const dy = n.y - from.y;
    const main = dir === "right" ? dx : dir === "left" ? -dx : dir === "down" ? dy : -dy;
    const cross = dir === "left" || dir === "right" ? Math.abs(dy) : Math.abs(dx);
    if (main <= 0 || cross > main) continue;
    const score = main + 2 * cross;
    if (score < bestScore) {
      bestScore = score;
      best = n.id;
    }
  }
  return best;
}

/** Label counts for a component, read from the components endpoint (keys as the API reports them). */
export function countsFor(id: string, components: readonly Component[]): Record<string, number> | null {
  const c = components.find((x) => x.id === id);
  return c ? c.claim_counts : null;
}
