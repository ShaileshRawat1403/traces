import cytoscape from "cytoscape";
import { useEffect, useRef, useState } from "react";
import { api, type GraphResponse } from "../api/client";
import { ErrorState } from "./common";

// Renders GraphResponse from the API. Until the graph endpoint is implemented this shows its explicit 501 state.
export function GraphView({ repoId, sha }: { repoId: string; sha: string }) {
  const box = useRef<HTMLDivElement>(null);
  const [data, setData] = useState<GraphResponse | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    api.graph(repoId, sha).then(setData, setError);
  }, [repoId, sha]);

  useEffect(() => {
    if (!data || !box.current) return;
    const cy = cytoscape({
      container: box.current,
      elements: [
        ...data.nodes.map((n) => ({ data: { id: n.id, label: n.label } })),
        ...data.edges.map((e) => ({ data: { id: e.id, source: e.source, target: e.target, label: e.label } })),
      ],
      layout: { name: "breadthfirst" },
    });
    return () => cy.destroy();
  }, [data]);

  if (error) return <ErrorState error={error} />;
  return (
    <>
      {data && Object.keys(data.hidden_counts).length > 0 ? (
        <p>Hidden: {Object.entries(data.hidden_counts).map(([s, c]) => `${c} ${s}`).join(", ")}</p>
      ) : null}
      <div ref={box} className="graph" aria-label="Architecture graph" />
    </>
  );
}
