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

  const userScaled = useRef(false);
  const fit = useCallback(() => {
    const el = stageRef.current;
    if (!el || el.clientWidth < 40) return 1;
    const availH = el.clientHeight > 80 ? el.clientHeight - 8 : 520;
    const z = Math.min(1.15, (el.clientWidth - 8) / frame.w, availH / frame.h);
    return Math.max(0.22, z);
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
      </div>
      <div
        ref={stageRef}
        tabIndex={0}
        role="application"
        aria-roledescription="graph"
        aria-label="Architecture graph. Use arrow keys to move between nodes, Enter to expand, Escape to clear. The list and cards views show the same data."
        onKeyDown={onKeyDown}
        className="stage w-full max-w-full overflow-auto rounded-lg border border-line bg-[#070b0a]"
        data-testid="graph-canvas"
      >
        <svg width={Math.ceil(frame.w * scale)} height={Math.ceil(frame.h * scale)} viewBox={`0 0 ${frame.w} ${frame.h}`} role="group" aria-label="Nodes and recorded relationships in this view">
          <defs>
            <marker id={`${marker}-arrow`} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M 0 1.2 L 8 5 L 0 8.8 z" fill="context-stroke" />
            </marker>
          </defs>
          {headers.map((h) => (
            <text key={`${h.layer}-${h.x}`} x={h.x} y={h.y - 40} textAnchor="middle" fill={layerColor(h.layer)} fontSize="12" fontFamily="IBM Plex Sans, sans-serif" fontWeight={600}>
              {h.layer.charAt(0).toUpperCase() + h.layer.slice(1)}
            </text>
          ))}
          {edges.map((e) => {
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
                  stroke={hot ? "#7eb6ff" : color}
                  strokeWidth={hot ? 2.75 : Math.min(2.2, 0.9 + (e.data.weight ?? 1.5) * 0.35)}
                  strokeDasharray={dash}
                  markerEnd={`url(#${marker}-arrow)`}
                />
                <path d={elbow(a, b, lanes.get(e.data.id) ?? 0, busY)} fill="none" stroke="transparent" strokeWidth={14} className="cursor-pointer" onClick={() => (e.data.id.startsWith("rollup::") ? onSelect(e.data.source ?? null) : onEdge(e.data.id))} />
                {showLabels || hot ? (
                  <text x={midX} y={midY - 6} textAnchor="middle" fill="#e7f2ef" fontSize="11" fontFamily="IBM Plex Sans, sans-serif">
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
            const stroke = on ? "#7eb6ff" : layerColor(n.data.layer);
            return (
              <g
                key={n.data.id}
                data-node-id={n.data.id}
                transform={`translate(${p.x - box.w / 2} ${p.y - box.h / 2})`}
                opacity={dim ? 0.38 : 1}
                className="cursor-pointer"
                onClick={() => onSelect(n.data.id)}
                onDoubleClick={() => onExpand(n.data.id)}
              >
                <rect width={box.w} height={box.h} rx="8" fill="#1b3330" stroke={stroke} strokeWidth={on ? 3 : 2} />
                <rect width="5" height={box.h} rx="2" fill={layerColor(n.data.layer)} />
                <text x={box.w / 2} y={l2 ? box.h / 2 - 6 : box.h / 2 + 4} textAnchor="middle" fill="#f4faf7" fontSize="12" fontFamily="IBM Plex Sans, sans-serif" fontWeight={600}>
                  {l1}
                </text>
                {l2 ? (
                  <text x={box.w / 2} y={box.h / 2 + 12} textAnchor="middle" fill="#c5d2cb" fontSize="11" fontFamily="IBM Plex Sans, sans-serif">
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
