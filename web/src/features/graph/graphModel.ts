import type { GraphEdge, GraphResponse } from "../../api/client";
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
