import cytoscape from "cytoscape";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Button } from "../../ui/States";
import { nextInDirection, type Direction, type ElementData } from "./graphModel";

const C = {
  verified: "#8fd9cf",
  observed: "#d5e2ea",
  inferred: "#f0c27a",
  unknown: "#d4c4f5",
  ink: "#f4faf7",
  line: "#6f8f86",
  focus: "#7eb6ff",
  comp: "#14302c",
  node: "#d7fff8",
};

const KEY_DIR: Record<string, Direction> = { ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right" };

export interface GraphCanvasProps {
  elements: { data: ElementData }[];
  selected: string | null;
  onSelect: (id: string | null) => void;
  /** Enter or double tap on a node: expand its neighborhood. */
  onExpand: (id: string) => void;
  /** Tap or Enter on an edge: open its evidence. */
  onEdge: (claimId: string) => void;
  describe: (id: string) => string;
}

/**
 * Cytoscape canvas with keyboard equivalents: arrows move between nodes by position, Enter expands, E opens the
 * first relationship's evidence via the side panel, +/- zoom, 0 fits, Escape clears. Touch: tap selects, double tap expands.
 */
export function GraphCanvas({ elements, selected, onSelect, onExpand, onEdge, describe }: GraphCanvasProps) {
  const box = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const handlers = useRef({ onSelect, onExpand, onEdge });
  handlers.current = { onSelect, onExpand, onEdge };
  const [announce, setAnnounce] = useState("");

  useEffect(() => {
    if (!box.current) return;
    const cy = cytoscape({
      container: box.current,
      elements,
      style: [
        { selector: "node", style: { label: "data(label)", "font-size": 12, color: C.ink, "background-color": C.node, "border-width": 2, "border-color": C.verified, "text-valign": "bottom", "text-margin-y": 4, width: 18, height: 18, "text-max-width": "140px", "text-wrap": "ellipsis", "min-zoomed-font-size": 6 } },
        { selector: "node:parent", style: { "background-color": C.comp, "background-opacity": 0.55, "border-width": 1, "border-color": C.verified, "text-valign": "top", "text-margin-y": -2, "font-weight": "bold", padding: "14px", shape: "round-rectangle" } },
        { selector: 'node[entity = "component"]', style: { shape: "round-rectangle", width: 26, height: 20, "font-weight": "bold" } },
        { selector: "edge", style: { width: 1.8, "curve-style": "bezier", "target-arrow-shape": "triangle", "arrow-scale": 0.8 } },
        { selector: 'edge[tone = "verified"]', style: { "line-color": C.verified, "target-arrow-color": C.verified } },
        { selector: 'edge[tone = "observed"]', style: { "line-color": C.observed, "target-arrow-color": C.observed, width: 1 } },
        { selector: 'edge[tone = "inferred"]', style: { "line-color": C.inferred, "target-arrow-color": C.inferred, "target-arrow-fill": "hollow" } },
        { selector: 'edge[tone = "unknown"]', style: { "line-color": C.unknown, "target-arrow-color": C.unknown } },
        { selector: 'edge[line = "dashed"]', style: { "line-style": "dashed", "line-dash-pattern": [6, 4] } },
        { selector: 'edge[line = "dotted"]', style: { "line-style": "dotted" } },
        { selector: ".sel", style: { "border-width": 3, "border-color": C.focus, "line-color": C.focus, "target-arrow-color": C.focus, "z-index": 10 } },
        { selector: ".dim", style: { opacity: 0.35 } },
      ],
      layout: { name: "cose", animate: false, nodeDimensionsIncludeLabels: true, padding: 24 },
      wheelSensitivity: 0.3,
      boxSelectionEnabled: false,
      selectionType: "single",
    });
    cy.on("tap", "node", (ev) => handlers.current.onSelect(ev.target.id() as string));
    cy.on("dbltap", "node", (ev) => handlers.current.onExpand(ev.target.id() as string));
    cy.on("tap", "edge", (ev) => handlers.current.onEdge(ev.target.id() as string));
    cy.on("tap", (ev) => ev.target === cy && handlers.current.onSelect(null));
    cy.one("layoutstop", () => {
      if (cy.destroyed()) return;
      const comps = cy.nodes().filter('[entity = "component"]');
      cy.fit(comps.length ? comps : cy.elements(), 36);
    });
    cyRef.current = cy;
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [elements]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().removeClass("sel dim");
    if (!selected) return;
    const n = cy.getElementById(selected);
    if (n.empty()) return;
    const hood = n.closedNeighborhood();
    cy.elements().not(hood).not(n.ancestors()).addClass("dim");
    n.addClass("sel");
    if (!cy.extent() || !n.renderedBoundingBox()) return;
    const bb = n.renderedBoundingBox();
    if (bb.x1 < 0 || bb.y1 < 0 || bb.x2 > cy.width() || bb.y2 > cy.height()) cy.center(n);
    setAnnounce(describe(selected));
  }, [selected, elements, describe]);

  const zoom = (f: number) => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.zoom({ level: cy.zoom() * f, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
  };

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const cy = cyRef.current;
    if (!cy) return;
    const dir = KEY_DIR[e.key];
    if (dir) {
      e.preventDefault();
      const nodes = cy.nodes().toArray() as cytoscape.NodeSingular[];
      const all = nodes.map((n) => ({ id: n.id(), ...n.renderedPosition() }));
      const pos = nodes.filter((n) => !n.isParent()).map((n) => ({ id: n.id(), ...n.renderedPosition() }));
      const next = nextInDirection(pos.length ? pos : all, selected, dir) ?? nextInDirection(all, selected, dir);
      if (next) handlers.current.onSelect(next);
      return;
    }
    if (e.key === "Enter" && selected) {
      e.preventDefault();
      handlers.current.onExpand(selected);
    } else if (e.key === "Escape") {
      handlers.current.onSelect(null);
    } else if (e.key === "+" || e.key === "=") {
      zoom(1.25);
    } else if (e.key === "-") {
      zoom(0.8);
    } else if (e.key === "0") {
      cy.fit(undefined, 24);
    }
  };

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-2" role="toolbar" aria-label="Graph view controls">
        <Button onClick={() => zoom(1.25)} aria-label="Zoom in">
          +
        </Button>
        <Button onClick={() => zoom(0.8)} aria-label="Zoom out">
          −
        </Button>
        <Button onClick={() => cyRef.current?.fit(undefined, 24)}>Fit</Button>
        <span className="text-xs text-muted">Keys: arrows move, Enter expands, Escape clears, + and − zoom, 0 fits</span>
      </div>
      <div
        ref={box}
        tabIndex={0}
        role="application"
        aria-roledescription="graph"
        aria-label="Architecture graph. Use arrow keys to move between nodes, Enter to expand, Escape to clear. The list and cards views show the same data."
        onKeyDown={onKeyDown}
        className="h-[min(72dvh,44rem)] min-h-80 w-full touch-none rounded-lg border border-line bg-[#070b0a]"
        data-testid="graph-canvas"
      />
      <p className="sr-only" aria-live="polite" data-testid="graph-announce">
        {announce}
      </p>
    </div>
  );
}
