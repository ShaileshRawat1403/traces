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
export { LAYERS } from "../layers";

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

/** Page sizes the graph API accepts. 2000 is the contract cap, not the whole repository. */
export const GRAPH_LIMITS = [300, 800, 2000] as const;

export function clampLimit(raw: string | null): number {
  const n = Number(raw);
  if (!Number.isFinite(n) || n <= 0) return 300;
  return Math.min(2000, Math.max(1, Math.trunc(n)));
}

/** The next larger page, or null when this page is already at the API cap. */
export function nextGraphLimit(limit: number): number | null {
  return GRAPH_LIMITS.find((n) => n > limit) ?? null;
}

export function readGraphState(sp: URLSearchParams): GraphState {
  const st = sp.getAll("status").filter((s): s is StatusFilter => (STATUS_FILTERS as readonly string[]).includes(s));
  return {
    focus: sp.get("focus") || null,
    depth: sp.has("depth") ? clampDepth(Number(sp.get("depth"))) : 1,
    layer: sp.getAll("layer"),
    rel: sp.getAll("rel"),
    status: sp.has("status") || sp.has("status_set") ? st : [...DEFAULT_STATUS],
    q: sp.get("q") ?? "",
    limit: clampLimit(sp.get("limit")),
  };
}

export function writeGraphState(s: GraphState, keep?: URLSearchParams): URLSearchParams {
  const n = new URLSearchParams();
  for (const k of ["view", "claim", "at"]) {
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
  /** Source file for a symbol, or the path a file node stands for. */
  file?: string;
  /** How many symbols a file node stands for. Not a claim. */
  count?: number;
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

const COL_W = 220;
const ROW_H = 76;
const MAX_ROWS = 6;
const PRIMARY_LAYERS = ["frontend", "api", "backend", "library", "data"] as const;
const SUPPORT_LAYERS = ["infra", "docs", "tests", "other"] as const;

export interface LayoutNode {
  id: string;
  label: string;
  layer?: string;
}
export interface LayoutEdge {
  source?: string;
  target?: string;
}

function barycenterOrder(groups: Map<string, LayoutNode[]>, edges: readonly LayoutEdge[], layerOrder: readonly string[]) {
  const index = new Map<string, number>();
  const reindex = () => {
    for (const list of groups.values()) list.forEach((n, i) => index.set(n.id, i));
  };
  reindex();
  const adj = new Map<string, string[]>();
  for (const e of edges) {
    if (!e.source || !e.target || !index.has(e.source) || !index.has(e.target)) continue;
    const a = adj.get(e.source) ?? [];
    a.push(e.target);
    adj.set(e.source, a);
    const b = adj.get(e.target) ?? [];
    b.push(e.source);
    adj.set(e.target, b);
  }
  const score = (id: string) => {
    const nbrs = (adj.get(id) ?? []).filter((n) => index.has(n));
    if (nbrs.length === 0) return index.get(id) ?? 0;
    return nbrs.reduce((sum, n) => sum + (index.get(n) ?? 0), 0) / nbrs.length;
  };
  for (let sweep = 0; sweep < 4; sweep += 1) {
    const order = sweep % 2 ? [...layerOrder].reverse() : layerOrder;
    for (const layer of order) {
      const list = groups.get(layer);
      if (!list) continue;
      list.sort((a, b) => score(a.id) - score(b.id) || a.label.localeCompare(b.label) || a.id.localeCompare(b.id));
      reindex();
    }
  }
}

/**
 * Place nodes in layer columns, left to right. A layer taller than MAX_ROWS wraps into the next column
 * so names stay large enough to read. Shorter columns are centered on the tallest column in that row.
 * Order inside a column follows neighboring nodes, to shorten the lines. Positions are a picture of
 * stored nodes, not new relationships.
 */
export function columnLayout(nodes: readonly LayoutNode[], edges: readonly LayoutEdge[]): Record<string, { x: number; y: number }> {
  const groups = new Map<string, LayoutNode[]>();
  for (const n of nodes) {
    const layer = n.layer || "other";
    const list = groups.get(layer) ?? [];
    list.push({ ...n, layer });
    groups.set(layer, list);
  }
  for (const list of groups.values()) list.sort((a, b) => a.label.localeCompare(b.label) || a.id.localeCompare(b.id));
  const known = new Set<string>([...PRIMARY_LAYERS, ...SUPPORT_LAYERS]);
  const extra = [...groups.keys()].filter((l) => !known.has(l)).sort();
  const primary = PRIMARY_LAYERS.filter((l) => groups.has(l));
  const support = [...SUPPORT_LAYERS, ...extra].filter((l) => groups.has(l));
  barycenterOrder(groups, edges, [...primary, ...support]);

  const positions: Record<string, { x: number; y: number }> = {};
  const place = (layers: readonly string[], y0: number) => {
    const columns: { layer: string; list: LayoutNode[] }[] = [];
    for (const layer of layers) {
      const list = groups.get(layer) ?? [];
      for (let i = 0; i < list.length; i += MAX_ROWS) columns.push({ layer, list: list.slice(i, i + MAX_ROWS) });
    }
    const maxH = Math.max(1, ...columns.map((c) => c.list.length));
    columns.forEach((col, i) => {
      const extraY = ((maxH - col.list.length) * ROW_H) / 2;
      col.list.forEach((n, row) => {
        positions[n.id] = { x: 110 + i * COL_W, y: y0 + extraY + row * ROW_H };
      });
    });
    return y0 + maxH * ROW_H;
  };
  let y = 48;
  if (primary.length) y = place(primary, y) + 64;
  if (support.length) place(support, y);
  return positions;
}

/**
 * Left-to-right columns by distance along recorded edges. Nodes with no incoming edge start at the left.
 * A column taller than MAX_ROWS wraps beside itself. This is a reading order, not a new claim.
 */
export function depthLayout(nodes: readonly LayoutNode[], edges: readonly LayoutEdge[]): Record<string, { x: number; y: number }> {
  const ids = nodes.map((n) => n.id);
  const outgoing = new Map<string, string[]>(ids.map((id) => [id, []]));
  const incoming = new Map<string, string[]>(ids.map((id) => [id, []]));
  for (const e of edges) {
    if (!e.source || !e.target || !outgoing.has(e.source) || !outgoing.has(e.target)) continue;
    outgoing.get(e.source)!.push(e.target);
    incoming.get(e.target)!.push(e.source);
  }
  const depth = new Map<string, number>();
  const roots = ids.filter((id) => (incoming.get(id)?.length ?? 0) === 0);
  const start = roots.length ? roots : ids.length ? [ids.slice().sort((a, b) => (outgoing.get(b)!.length + incoming.get(b)!.length) - (outgoing.get(a)!.length + incoming.get(a)!.length))[0]!] : [];
  const queue = [...start];
  for (const id of start) depth.set(id, 0);
  while (queue.length) {
    const id = queue.shift()!;
    const d = depth.get(id)!;
    for (const next of outgoing.get(id) ?? []) {
      if (!depth.has(next)) {
        depth.set(next, d + 1);
        queue.push(next);
      }
    }
  }
  for (const id of ids) if (!depth.has(id)) depth.set(id, 0);
  const label = new Map(nodes.map((n) => [n.id, n.label]));
  const cols = new Map<number, string[]>();
  for (const id of ids) {
    const d = depth.get(id)!;
    const list = cols.get(d) ?? [];
    list.push(id);
    cols.set(d, list);
  }
  for (const list of cols.values()) list.sort((a, b) => (label.get(a) ?? "").localeCompare(label.get(b) ?? "") || a.localeCompare(b));
  const index = new Map<string, number>();
  const reindex = () => {
    for (const list of cols.values()) list.forEach((id, i) => index.set(id, i));
  };
  reindex();
  const score = (id: string) => {
    const nbrs = [...(incoming.get(id) ?? []), ...(outgoing.get(id) ?? [])].filter((n) => index.has(n));
    if (!nbrs.length) return index.get(id) ?? 0;
    return nbrs.reduce((sum, n) => sum + (index.get(n) ?? 0), 0) / nbrs.length;
  };
  for (let sweep = 0; sweep < 4; sweep += 1) {
    const keys = [...cols.keys()].sort((a, b) => (sweep % 2 ? b - a : a - b));
    for (const d of keys) {
      const list = cols.get(d);
      if (!list) continue;
      list.sort((a, b) => score(a) - score(b) || (label.get(a) ?? "").localeCompare(label.get(b) ?? "") || a.localeCompare(b));
      reindex();
    }
  }
  const positions: Record<string, { x: number; y: number }> = {};
  const keys = [...cols.keys()].sort((a, b) => a - b);
  let x = 80;
  for (const d of keys) {
    const list = cols.get(d) ?? [];
    const parts: string[][] = [];
    for (let i = 0; i < list.length; i += MAX_ROWS) parts.push(list.slice(i, i + MAX_ROWS));
    const maxH = Math.max(1, ...parts.map((p) => p.length));
    parts.forEach((part) => {
      const extraY = ((maxH - part.length) * ROW_H) / 2;
      part.forEach((id, row) => {
        positions[id] = { x, y: 40 + extraY + row * ROW_H };
      });
      x += COL_W;
    });
  }
  return positions;
}

/** Symbols that share a file, plus recorded edges between different files. Same-file edges stay off until the file is opened. */
export function fileRollup(elements: readonly { data: ElementData }[]): { data: ElementData }[] {
  const symbols = elements.filter((e) => !e.data.source && e.data.entity !== "component");
  if (symbols.length === 0 || symbols.some((s) => !s.data.file)) return [...elements];
  const owner = new Map<string, string>();
  const files = new Map<string, { layer?: string; n: number }>();
  for (const s of symbols) {
    const file = s.data.file!;
    owner.set(s.data.id, file);
    const row = files.get(file) ?? { layer: s.data.layer, n: 0 };
    row.n += 1;
    if (!row.layer && s.data.layer) row.layer = s.data.layer;
    files.set(file, row);
  }
  if (files.size <= 1 || files.size === symbols.length) return [...elements];
  const nodes = [...files.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([file, row]) => ({
      data: {
        id: `file::${file}`,
        label: file.split("/").pop() || file,
        entity: "file",
        layer: row.layer,
        file,
        count: row.n,
      },
    }));
  const rankOf = (tone?: string) => (tone === "inferred" || tone === "unknown" ? 2 : tone === "observed" ? 1 : 0);
  const buckets = new Map<string, { source: string; target: string; n: number; rank: number }>();
  for (const e of elements) {
    if (!e.data.source || !e.data.target) continue;
    const source = owner.get(e.data.source);
    const target = owner.get(e.data.target);
    if (!source || !target || source === target) continue;
    const key = `${source}\0${target}`;
    let row = buckets.get(key);
    if (!row) {
      row = { source: `file::${source}`, target: `file::${target}`, n: 0, rank: 0 };
      buckets.set(key, row);
    }
    row.n += 1;
    const rank = rankOf(e.data.tone);
    if (rank > row.rank) row.rank = rank;
  }
  const edges = [...buckets.values()]
    .sort((a, b) => a.source.localeCompare(b.source) || a.target.localeCompare(b.target))
    .map((row) => {
      const tone = row.rank === 2 ? "inferred" : row.rank === 1 ? "observed" : "verified";
      const line = row.rank === 2 ? "dashed" : row.rank === 1 ? "thin" : "solid";
      return {
        data: {
          id: `rollup::${row.source}::${row.target}`,
          label: String(row.n),
          source: row.source,
          target: row.target,
          entity: "rollup",
          tone,
          line,
          weight: Math.min(6, 1.6 + Math.log2(row.n)),
        },
      };
    });
  return [...nodes, ...edges];
}

/** One file's symbols, plus the symbols they record a relationship with. */
export function symbolsInFile(elements: readonly { data: ElementData }[], file: string): { data: ElementData }[] {
  const inside = new Set(elements.filter((e) => !e.data.source && e.data.file === file).map((e) => e.data.id));
  const keep = new Set(inside);
  for (const e of elements) {
    if (!e.data.source || !e.data.target) continue;
    if (inside.has(e.data.source) || inside.has(e.data.target)) {
      keep.add(e.data.source);
      keep.add(e.data.target);
    }
  }
  return elements.filter((e) => {
    if (!e.data.source) return keep.has(e.data.id);
    return !!e.data.source && !!e.data.target && keep.has(e.data.source) && keep.has(e.data.target);
  });
}

/** Cytoscape elements: component nodes become compound parents of the symbol nodes inside their paths. */
export function toElements(data: GraphResponse, components: readonly Component[]): { data: ElementData }[] {
  const ids = new Set(data.nodes.map((n) => n.id));
  const parentOf = (n: GraphNode): string | undefined => {
    if (n.entity === "component") return undefined;
    const c = componentForFile(n.file, components);
    return c && ids.has(c.id) ? c.id : undefined;
  };
  const nodes = data.nodes.map((n) => ({
    data: { id: n.id, label: n.label, entity: n.entity, layer: n.layer || undefined, parent: parentOf(n), file: n.file ?? undefined },
  }));
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
