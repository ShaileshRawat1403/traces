import { useCallback, useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { nextInDirection, columnLayout, depthLayout, type Direction, type ElementData } from "./graphModel";
import { layerColor } from "../layers";

const TONE: Record<string, string> = {
  verified: "#8fd9cf",
  observed: "#d5e2ea",
  inferred: "#f0c27a",
  unknown: "#d4c4f5",
};

const KEY_DIR: Record<string, Direction> = { ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right" };

const SANS = "Inter Tight, ui-sans-serif, sans-serif";

function layerTitle(layer: string) {
  if (layer === "api") return "API";
  return layer.charAt(0).toUpperCase() + layer.slice(1);
}

function clip(s: string, n: number) {
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}

function nodeBox(n: ElementData) {
  if (n.entity === "symbol") return { w: 156, h: 36 };
  return { w: 168, h: 50 };
}

function nodeLines(n: ElementData): [string, string] {
  if (n.entity === "symbol") return [clip(n.label, 24), ""];
  if (n.entity === "file") {
    const leaf = n.label.split("/").pop() || n.label;
    return [clip(leaf, 24), n.count ? `${n.count} symbols` : ""];
  }
  const parts = n.label.split("/").filter(Boolean);
  if (parts.length >= 2) {
    const tail = parts.pop() ?? n.label;
    return [clip(tail, 22), clip(parts.join("/"), 26)];
  }
  return [clip(n.label, 24), ""];
}

function positionsFor(model: { data: ElementData }[], layout: "map" | "neighborhood") {
  const nodes = model.filter((e) => !e.data.source).map((n) => ({ id: n.data.id, label: n.data.label, layer: n.data.layer }));
  const edges = model.filter((e) => e.data.source).map((e) => ({ source: e.data.source, target: e.data.target }));
  return layout === "map" ? columnLayout(nodes, edges) : depthLayout(nodes, edges);
}

/** A route that stays readable. Same-layer links bow out beside the column. Cross-layer links stay in the gaps. */
function route(a: { x: number; y: number }, b: { x: number; y: number }, lane: number, busY: number) {
  const sameCol = Math.abs(a.x - b.x) < 48;
  if (sameCol) {
    const down = b.y >= a.y;
    const y1 = a.y + (down ? 18 : -18);
    const y2 = b.y + (down ? -18 : 18);
    const bow = Math.min(70, 26 + Math.abs(b.y - a.y) * 0.1) + Math.abs(lane);
    const x = Math.max(a.x, b.x) + 96 + bow;
    return { d: `M ${a.x + 84} ${y1} C ${x} ${y1}, ${x} ${y2}, ${b.x + 84} ${y2}`, lx: x - 6, ly: (y1 + y2) / 2 };
  }
  const dir = b.x >= a.x ? 1 : -1;
  const x1 = a.x + dir * 88;
  const x2 = b.x - dir * 88;
  if (Math.abs(a.x - b.x) > 300) {
    const y = busY + lane;
    return { d: `M ${x1} ${a.y} V ${y} H ${x2} V ${b.y}`, lx: (x1 + x2) / 2, ly: y - 8 };
  }
  if (Math.abs(a.y - b.y) < 6 && Math.abs(lane) < 1) return { d: `M ${x1} ${a.y} H ${x2}`, lx: (x1 + x2) / 2, ly: a.y - 8 };
  const mid = (a.x + b.x) / 2 + lane;
  return { d: `M ${x1} ${a.y} H ${mid} V ${b.y} H ${x2}`, lx: mid, ly: (a.y + b.y) / 2 };
}

export interface GraphCanvasProps {
  elements: { data: ElementData }[];
  /** map: components or files in layer columns. neighborhood: focused symbols, left to right. */
  layout: "map" | "neighborhood";
  selected: string | null;
  onSelect: (id: string | null) => void;
  /** Enter or double tap on a node: expand its neighborhood. */
  onExpand: (id: string) => void;
  /** Tap or Enter on an edge: open its evidence. Rollup counts are not claims. */
  onEdge: (claimId: string) => void;
  describe: (id: string) => string;
}

/**
 * Layered diagram. Arrow keys move between nodes, Enter expands, Escape clears.
 * The picture is fitted so every node in this view stays inside the frame.
 */
export function GraphCanvas({ elements, layout, selected, onSelect, onExpand, onEdge, describe }: GraphCanvasProps) {
  const stageRef = useRef<HTMLDivElement>(null);
  const [announce, setAnnounce] = useState("");
  const [scale, setScale] = useState(1);
  const marker = useId().replace(/:/g, "");
  const nodes = useMemo(() => elements.filter((e) => !e.data.source), [elements]);
  const edges = useMemo(() => elements.filter((e) => e.data.source && e.data.target), [elements]);
  const pos = useMemo(() => positionsFor(elements, layout), [elements, layout]);
  const frame = useMemo(() => {
    const pts = nodes.map((n) => pos[n.data.id]).filter((p): p is { x: number; y: number } => !!p);
    if (pts.length === 0) return { minX: 0, minY: 0, w: 320, h: 180 };
    const minX = Math.min(...pts.map((p) => p.x)) - 36;
    const minY = Math.min(...pts.map((p) => p.y)) - 72;
    const maxX = Math.max(...pts.map((p) => p.x)) + 250;
    const maxY = Math.max(...pts.map((p) => p.y)) + 110;
    return { minX, minY, w: Math.max(280, maxX - minX), h: Math.max(180, maxY - minY) };
  }, [nodes, pos]);
  const at = (id: string | undefined) => {
    if (!id || !pos[id]) return null;
    return { x: pos[id].x - frame.minX, y: pos[id].y - frame.minY };
  };
  const lanes = useMemo(() => {
    const groups = new Map<string, string[]>();
    for (const e of edges) {
      const a = pos[e.data.source!];
      const b = pos[e.data.target!];
      if (!a || !b) continue;
      const key = `${Math.round(a.x)}:${Math.round(b.x)}`;
      const list = groups.get(key) ?? [];
      list.push(e.data.id);
      groups.set(key, list);
    }
    const out = new Map<string, number>();
    for (const ids of groups.values()) {
      ids.forEach((id, i) => out.set(id, Math.max(-18, Math.min(18, (i - (ids.length - 1) / 2) * 7))));
    }
    return out;
  }, [edges, pos]);
  const busY = useMemo(() => {
    let bottom = 0;
    for (const n of nodes) {
      const p = at(n.data.id);
      if (!p) continue;
      bottom = Math.max(bottom, p.y + nodeBox(n.data).h / 2);
    }
    return bottom + 26;
  }, [nodes, pos, frame]);
  const bands = useMemo(() => {
    const cols = new Map<string, { x: number; top: number; bottom: number; layer: string }>();
    for (const n of nodes) {
      const p0 = pos[n.data.id];
      if (!p0) continue;
      const p = { x: p0.x - frame.minX, y: p0.y - frame.minY };
      const box = nodeBox(n.data);
      const key = `${Math.round(p.x / 8)}:${n.data.layer ?? "other"}`;
      const top = p.y - box.h / 2;
      const bottom = p.y + box.h / 2;
      const cur = cols.get(key);
      if (!cur) cols.set(key, { x: p.x, top, bottom, layer: n.data.layer ?? "other" });
      else {
        cur.top = Math.min(cur.top, top);
        cur.bottom = Math.max(cur.bottom, bottom);
      }
    }
    return [...cols.values()];
  }, [nodes, pos, frame]);
  const linked = useMemo(() => {
    if (!selected) return null;
    const ids = new Set<string>([selected]);
    for (const e of edges) {
      if (e.data.source === selected || e.data.target === selected) {
        if (e.data.source) ids.add(e.data.source);
        if (e.data.target) ids.add(e.data.target);
      }
    }
    return ids;
  }, [edges, selected]);

  const [linkScope, setLinkScope] = useState<"near" | "all">("near");
  const multiLayer = useMemo(() => new Set(nodes.map((n) => n.data.layer).filter(Boolean)).size > 1, [nodes]);
  const neighboring = useCallback(
    (e: { data: ElementData }) => {
      const a = pos[e.data.source!];
      const b = pos[e.data.target!];
      if (!a || !b) return false;
      return Math.abs(a.x - b.x) <= 280;
    },
    [pos],
  );
  const holdLong = layout === "map" && multiLayer && linkScope === "near";
  const visibleEdges = useMemo(() => {
    if (!holdLong) return edges;
    return edges.filter((e) => neighboring(e) || (!!selected && (e.data.source === selected || e.data.target === selected)));
  }, [edges, holdLong, neighboring, selected]);
  const longer = useMemo(() => (layout === "map" && multiLayer ? edges.filter((e) => !neighboring(e)).length : 0), [edges, layout, multiLayer, neighboring]);

  const userScaled = useRef(false);
  const fit = useCallback(() => {
    const el = stageRef.current;
    if (!el || el.clientWidth < 40) return 1;
    const top = el.getBoundingClientRect().top;
    const visible = Math.max(240, window.innerHeight - Math.max(top, 0) - 12);
    const z = Math.min(1.15, (el.clientWidth - 8) / frame.w, visible / frame.h);
    return Math.max(0.42, z);
  }, [frame.w, frame.h]);

  useEffect(() => {
    userScaled.current = false;
    setScale(fit());
  }, [fit]);

  useEffect(() => {
    const el = stageRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      if (!userScaled.current) setScale(fit());
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [fit]);

  useEffect(() => {
    if (selected) setAnnounce(describe(selected));
  }, [selected, describe]);

  useEffect(() => {
    if (!selected || !stageRef.current) return;
    const node = stageRef.current.querySelector(`[data-node-id="${CSS.escape(selected)}"]`);
    node?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [selected, scale]);

  const zoom = (factor: number) => {
    userScaled.current = true;
    setScale((s) => Math.min(2, Math.max(0.35, s * factor)));
  };

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const dir = KEY_DIR[e.key];
    if (dir) {
      e.preventDefault();
      const spots = nodes.flatMap((n) => {
        const p = at(n.data.id);
        return p ? [{ id: n.data.id, ...p }] : [];
      });
      const next = nextInDirection(spots, selected, dir);
      if (next) onSelect(next);
      return;
    }
    if (e.key === "Enter" && selected) {
      e.preventDefault();
      onExpand(selected);
    } else if (e.key === "Escape") {
      onSelect(null);
    } else if (e.key === "+" || e.key === "=") {
      zoom(1.25);
    } else if (e.key === "-") {
      zoom(0.8);
    } else if (e.key === "0") {
      setScale(fit());
    }
  };

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-2">
        <div className="seg" role="toolbar" aria-label="Graph view controls">
          <button type="button" onClick={() => zoom(1.25)} aria-label="Zoom in" className="min-w-8">
            +
          </button>
          <button type="button" onClick={() => zoom(0.8)} aria-label="Zoom out" className="min-w-8">
            −
          </button>
          <button
            type="button"
            onClick={() => {
              userScaled.current = false;
              setScale(fit());
              stageRef.current?.scrollTo({ left: 0, top: 0 });
            }}
          >
            Fit
          </button>
        </div>
        {longer > 0 ? (
          <div role="group" aria-label="Which recorded lines to draw" className="seg">
            <button type="button" aria-pressed={linkScope === "near"} onClick={() => setLinkScope("near")}>
              Neighboring columns
            </button>
            <button type="button" aria-pressed={linkScope === "all"} onClick={() => setLinkScope("all")}>
              All recorded lines
            </button>
          </div>
        ) : null}
        <span className="text-[12px] text-muted">Arrows move, Enter expands, Esc clears</span>
      </div>
      {longer > 0 && linkScope === "near" ? (
        <p className="mb-2 max-w-3xl text-[12px] leading-relaxed text-muted">
          {longer} longer {longer === 1 ? "link is" : "links are"} not drawn across other columns. Select a component to see its own, or choose All recorded lines. A missing line is not proof that nothing connects.
        </p>
      ) : null}
      <div
        ref={stageRef}
        tabIndex={0}
        role="application"
        aria-roledescription="graph"
        aria-label="Architecture graph. Use arrow keys to move between nodes, Enter to expand, Escape to clear. The list and cards views show the same data."
        onKeyDown={onKeyDown}
        className="stage w-full max-w-full overflow-auto rounded-2xl border border-white/[0.06]"
        data-testid="graph-canvas"
      >
        <svg width={Math.ceil(frame.w * scale)} height={Math.ceil(frame.h * scale)} viewBox={`0 0 ${frame.w} ${frame.h}`} role="group" aria-label="Nodes and recorded relationships in this view">
          <defs>
            <marker id={`${marker}-arrow`} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M 0 1.2 L 8 5 L 0 8.8 z" fill="context-stroke" />
            </marker>
          </defs>
          {bands.map((b) => (
            <g key={`${b.layer}-${b.x}`}>
              <rect x={b.x - 96} y={b.top - 28} width={192} height={b.bottom - b.top + 44} rx="18" fill={layerColor(b.layer)} opacity="0.08" />
              <rect x={b.x - 96} y={b.top - 28} width={192} height="2" rx="1" fill={layerColor(b.layer)} />
              <text x={b.x - 84} y={b.top - 36} textAnchor="start" fill={layerColor(b.layer)} fontSize="12" fontFamily={SANS} fontWeight={600} letterSpacing="0.4">
                {layerTitle(b.layer)}
              </text>
            </g>
          ))}
          {visibleEdges.map((e) => {
            const a = at(e.data.source);
            const b = at(e.data.target);
            if (!a || !b) return null;
            const hot = !!selected && (e.data.source === selected || e.data.target === selected);
            const dim = !!linked && !hot;
            const color = TONE[e.data.tone ?? "verified"] ?? TONE.verified;
            const dash = e.data.line === "dashed" ? "6 4" : e.data.line === "dotted" ? "2 3" : undefined;
            const drawn = route(a, b, lanes.get(e.data.id) ?? 0, busY);
            const near = Math.abs(a.x - b.x) <= 280;
            const showLabel = hot || (near && visibleEdges.length <= 16);
            const text = clip(e.data.label, 18);
            const plate = Math.max(28, text.length * 6.6 + 10);
            return (
              <g key={e.data.id} opacity={dim ? 0.16 : 1}>
                <path
                  d={drawn.d}
                  fill="none"
                  stroke={hot ? "#e7edf5" : color}
                  strokeWidth={hot ? 2.6 : Math.min(3.4, 1.2 + (e.data.weight ?? 1.5) * 0.4)}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeDasharray={dash}
                  markerEnd={`url(#${marker}-arrow)`}
                />
                <path d={drawn.d} fill="none" stroke="transparent" strokeWidth={16} className="cursor-pointer" onClick={() => (e.data.id.startsWith("rollup::") ? onSelect(e.data.source ?? null) : onEdge(e.data.id))} />
                {showLabel ? (
                  <g>
                    <rect x={drawn.lx - plate / 2} y={drawn.ly - 9} width={plate} height={16} rx="4" fill="#090c13" opacity="0.92" />
                    <text x={drawn.lx} y={drawn.ly + 3} textAnchor="middle" fill="#eef1f6" fontSize="11" fontFamily={SANS}>
                      {text}
                    </text>
                  </g>
                ) : null}
              </g>
            );
          })}
          {nodes.map((n) => {
            const p = at(n.data.id);
            if (!p) return null;
            const box = nodeBox(n.data);
            const [l1, l2] = nodeLines(n.data);
            const on = selected === n.data.id;
            const dim = !!linked && !linked.has(n.data.id);
            return (
              <g
                key={n.data.id}
                data-node-id={n.data.id}
                transform={`translate(${p.x - box.w / 2} ${p.y - box.h / 2})`}
                opacity={dim ? 0.34 : 1}
                className="cursor-pointer"
                onClick={() => onSelect(n.data.id)}
                onDoubleClick={() => onExpand(n.data.id)}
              >
                <rect width={box.w} height={box.h} rx="10" fill={on ? "#171d28" : "#10141c"} stroke={on ? "#eef1f6" : "rgba(255,255,255,0.14)"} strokeWidth={on ? 1.5 : 1} />
                <rect x="0" y="8" width="3" height={box.h - 16} rx="1.5" fill={layerColor(n.data.layer)} />
                <text x={14} y={l2 ? 22 : 30} textAnchor="start" fill="#f4f7fb" fontSize="14" fontFamily={SANS} fontWeight={500}>
                  {l1}
                </text>
                {l2 ? (
                  <text x={14} y={38} textAnchor="start" fill="#8e97a8" fontSize="11" fontFamily={SANS}>
                    {l2}
                  </text>
                ) : null}
              </g>
            );
          })}
        </svg>
      </div>
      <p className="sr-only" aria-live="polite" data-testid="graph-announce">
        {announce}
      </p>
    </div>
  );
}

function linkRank(label: string) {
  const n = Number.parseInt(label, 10);
  return Number.isFinite(n) ? n : 0;
}

/** The busiest recorded links on this page. Selecting one highlights its source. Counts are not new claims. */
export function RecordedLinks({
  rolls,
  nameOf,
  onPick,
}: {
  rolls: readonly { data: ElementData }[];
  nameOf: (id: string | undefined) => string;
  onPick: (id: string) => void;
}) {
  const ranked = [...rolls].sort((a, b) => linkRank(b.data.label) - linkRank(a.data.label) || a.data.id.localeCompare(b.data.id)).slice(0, 6);
  const max = Math.max(1, ...ranked.map((e) => linkRank(e.data.label)));
  if (ranked.length === 0) {
    return <p className="rounded-lg border border-dashed border-line-strong p-3 text-sm text-ink-2">No relationship on this page connects two components. That is not proof that nothing connects.</p>;
  }
  return (
    <div aria-label="Strongest recorded links">
      <h3 className="text-sm font-medium tracking-[-0.02em] text-ink">Strongest links on this page</h3>
      <ul className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {ranked.map((e) => {
          const n = linkRank(e.data.label);
          const tone = TONE[e.data.tone ?? "verified"] ?? TONE.verified;
          return (
            <li key={e.data.id}>
              <button type="button" onClick={() => e.data.source && onPick(e.data.source)} className="flex min-h-11 w-full items-center gap-3 rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-left hover:border-white/25">
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-ink">{nameOf(e.data.source)}</span>
                  <span className="my-1.5 block h-1.5 overflow-hidden rounded-full bg-white/10" aria-hidden="true">
                    <span className="block h-1.5 rounded-full" style={{ width: `${Math.max(12, (n / max) * 100)}%`, background: tone }} />
                  </span>
                  <span className="block truncate text-[13px] text-ink-2">{nameOf(e.data.target)}</span>
                </span>
                <span className="shrink-0 text-right">
                  <span className="block font-mono text-lg tabular-nums leading-none text-ink">{n || e.data.label}</span>
                  <span className="mt-1 block text-[10px] uppercase tracking-[0.12em] text-muted">recorded</span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      <p className="mt-3 text-xs leading-relaxed text-muted">The bar is how many relationships this page recorded between those two components. It is not a new claim. Select a component to read every link that touches it.</p>
    </div>
  );
}
