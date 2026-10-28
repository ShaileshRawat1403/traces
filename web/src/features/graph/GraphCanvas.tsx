import { useCallback, useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Button } from "../../ui/States";
import { nextInDirection, columnLayout, depthLayout, type Direction, type ElementData } from "./graphModel";
import { layerColor } from "../layers";

const TONE: Record<string, string> = {
  verified: "#8fd9cf",
  observed: "#d5e2ea",
  inferred: "#f0c27a",
  unknown: "#d4c4f5",
};

const KEY_DIR: Record<string, Direction> = { ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right" };

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

/** Orthogonal route that stays in the gaps. A line that would cross another column uses the channel under the row. */
function elbow(a: { x: number; y: number }, b: { x: number; y: number }, lane: number, busY: number) {
  const sameCol = Math.abs(a.x - b.x) < 48;
  if (sameCol) {
    const dir = b.y >= a.y ? 1 : -1;
    const yLeave = a.y + dir * 28;
    const yEnter = b.y - dir * 28;
    const x = Math.min(a.x, b.x) - 108 + lane;
    return `M ${a.x - 86} ${yLeave} H ${x} V ${yEnter} H ${b.x - 86}`;
  }
  const dir = b.x >= a.x ? 1 : -1;
  const x1 = a.x + dir * 88;
  const x2 = b.x - dir * 88;
  if (Math.abs(a.x - b.x) > 300) {
    const y = busY + lane;
    return `M ${x1} ${a.y} V ${y} H ${x2} V ${b.y}`;
  }
  if (Math.abs(a.y - b.y) < 6 && Math.abs(lane) < 1) return `M ${x1} ${a.y} H ${x2}`;
  const mid = (a.x + b.x) / 2 + lane;
  return `M ${x1} ${a.y} H ${mid} V ${b.y} H ${x2}`;
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
    const minX = Math.min(...pts.map((p) => p.x)) - 148;
    const minY = Math.min(...pts.map((p) => p.y)) - 78;
    const maxX = Math.max(...pts.map((p) => p.x)) + 120;
    const maxY = Math.max(...pts.map((p) => p.y)) + 96;
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
  const headers = useMemo(() => {
    const cols = new Map<string, { x: number; y: number; layer: string }>();
    for (const n of nodes) {
      const p = at(n.data.id);
      if (!p || !n.data.layer) continue;
      const key = `${Math.round(p.x / 8)}:${n.data.layer}`;
      const cur = cols.get(key);
      if (!cur || p.y < cur.y) cols.set(key, { x: p.x, y: p.y, layer: n.data.layer });
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

  const showLabels = false;

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-2" role="toolbar" aria-label="Graph view controls">
        <Button onClick={() => zoom(1.25)} aria-label="Zoom in">
          +
        </Button>
        <Button onClick={() => zoom(0.8)} aria-label="Zoom out">
          −
        </Button>
        <Button
          onClick={() => {
            userScaled.current = false;
            setScale(fit());
            stageRef.current?.scrollTo({ left: 0, top: 0 });
          }}
        >
          Fit
        </Button>
        <span className="text-xs text-muted">Arrows move, Enter expands, Esc clears</span>
        {longer > 0 ? (
          <div role="group" aria-label="Which recorded lines to draw" className="flex gap-1">
            <button type="button" aria-pressed={linkScope === "near"} onClick={() => setLinkScope("near")} className={`tap rounded-md border px-3 text-sm ${linkScope === "near" ? "border-accent bg-accent text-accent-ink" : "border-line-strong bg-surface"}`}>
              Neighboring columns
            </button>
            <button type="button" aria-pressed={linkScope === "all"} onClick={() => setLinkScope("all")} className={`tap rounded-md border px-3 text-sm ${linkScope === "all" ? "border-accent bg-accent text-accent-ink" : "border-line-strong bg-surface"}`}>
              All recorded lines
            </button>
          </div>
        ) : null}
      </div>
      {longer > 0 && linkScope === "near" ? (
        <p className="mb-2 text-xs text-ink-2">
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
        className="stage w-full max-w-full overflow-auto rounded-2xl border border-white/10"
        data-testid="graph-canvas"
      >
        <svg width={Math.ceil(frame.w * scale)} height={Math.ceil(frame.h * scale)} viewBox={`0 0 ${frame.w} ${frame.h}`} role="group" aria-label="Nodes and recorded relationships in this view">
          <defs>
            <marker id={`${marker}-arrow`} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M 0 1.2 L 8 5 L 0 8.8 z" fill="context-stroke" />
            </marker>
          </defs>
          {headers.map((h) => {
            const members = nodes.flatMap((n) => {
              const p = at(n.data.id);
              if (!p || n.data.layer !== h.layer || Math.abs(p.x - h.x) > 8) return [];
              return [p.y];
            });
            if (members.length === 0) return null;
            const top = Math.min(...members) - 56;
            const height = Math.max(...members) + 36 - top;
            return <rect key={`band-${h.layer}-${h.x}`} x={h.x - 96} y={top} width={192} height={height} rx="16" fill="#141822" />;
          })}
          {headers.map((h) => (
            <text key={`${h.layer}-${h.x}`} x={h.x} y={h.y - 40} textAnchor="middle" fill={layerColor(h.layer)} fontSize="11" fontFamily="Outfit, sans-serif" fontWeight={600} letterSpacing="1.6">
              {(h.layer.charAt(0).toUpperCase() + h.layer.slice(1)).toUpperCase()}
            </text>
          ))}
          {visibleEdges.map((e) => {
            const a = at(e.data.source);
            const b = at(e.data.target);
            if (!a || !b) return null;
            const hot = !!selected && (e.data.source === selected || e.data.target === selected);
            const dim = !!linked && !hot;
            const color = TONE[e.data.tone ?? "verified"] ?? TONE.verified;
            const dash = e.data.line === "dashed" ? "6 4" : e.data.line === "dotted" ? "2 3" : undefined;
            const midX = (a.x + b.x) / 2;
            const midY = (a.y + b.y) / 2;
            return (
              <g key={e.data.id} opacity={dim ? 0.12 : 0.92}>
                <path
                  d={elbow(a, b, lanes.get(e.data.id) ?? 0, busY)}
                  fill="none"
                  stroke={hot ? "#e4c27a" : color}
                  strokeWidth={hot ? 2.75 : Math.min(2.2, 0.9 + (e.data.weight ?? 1.5) * 0.35)}
                  strokeDasharray={dash}
                  markerEnd={`url(#${marker}-arrow)`}
                />
                <path d={elbow(a, b, lanes.get(e.data.id) ?? 0, busY)} fill="none" stroke="transparent" strokeWidth={14} className="cursor-pointer" onClick={() => (e.data.id.startsWith("rollup::") ? onSelect(e.data.source ?? null) : onEdge(e.data.id))} />
                {showLabels || hot ? (
                  <text x={midX} y={midY - 6} textAnchor="middle" fill="#f4f1ea" fontSize="11" fontFamily="Outfit, sans-serif">
                    {clip(e.data.label, 28)}
                  </text>
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
            const stroke = on ? "#e4c27a" : "rgba(244,241,234,0.14)";
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
                <rect width={box.w} height={box.h} rx="11" fill="#161b26" stroke={stroke} strokeWidth={on ? 1.75 : 1} />
                <rect x="0.5" y="8" width="3" height={box.h - 16} rx="1.5" fill={layerColor(n.data.layer)} />
                <text x={box.w / 2} y={l2 ? box.h / 2 - 5 : box.h / 2 + 4} textAnchor="middle" fill="#f7f4ee" fontSize="13" fontFamily="Outfit, sans-serif" fontWeight={500}>
                  {l1}
                </text>
                {l2 ? (
                  <text x={box.w / 2} y={box.h / 2 + 12} textAnchor="middle" fill="#b7b2a8" fontSize="11" fontFamily="Outfit, sans-serif">
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
  if (ranked.length === 0) {
    return <p className="rounded-lg border border-dashed border-line-strong p-3 text-sm text-ink-2">No relationship on this page connects two components. That is not proof that nothing connects.</p>;
  }
  return (
    <div aria-label="Strongest recorded links">
      <h3 className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted">Strongest links</h3>
      <ul className="mt-2 flex flex-col">
        {ranked.map((e) => (
          <li key={e.data.id} className="border-t border-line first:border-t-0">
            <button type="button" onClick={() => e.data.source && onPick(e.data.source)} className="tap flex w-full items-baseline justify-between gap-3 rounded-md px-1 text-left text-sm hover:bg-sunken">
              <span className="min-w-0 break-words">
                <span className="font-medium text-ink">{nameOf(e.data.source)}</span>
                <span className="text-muted"> to </span>
                <span className="text-ink-2">{nameOf(e.data.target)}</span>
              </span>
              <span className="shrink-0 font-mono text-[11px] text-muted">{e.data.label}</span>
            </button>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs leading-relaxed text-muted">A count of recorded relationships, not a new claim. Select a component to read every link that touches it.</p>
    </div>
  );
}
