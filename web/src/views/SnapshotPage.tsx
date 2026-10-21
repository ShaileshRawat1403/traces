import { useEffect, useState } from "react";
import { Link, NavLink, useParams } from "react-router-dom";
import { api, type ClaimPage } from "../api/client";
import { ErrorState, LABEL_TEXT } from "./common";
import { GraphView } from "./GraphView";

const VIEWS = ["overview", "components", "routes", "graph", "trace", "history", "ask", "claims", "review"] as const;
type View = (typeof VIEWS)[number];
const ENDPOINT: Partial<Record<View, string>> = {
  overview: "overview",
  components: "components",
  routes: "routes",
  trace: "trace?from=",
  history: "history/timeline",
};

function Claims({ repoId, sha, reviewer }: { repoId: string; sha: string; reviewer: boolean }) {
  const [page, setPage] = useState<ClaimPage | null>(null);
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    api.claims(repoId, sha, reviewer).then(setPage, setError);
  }, [repoId, sha, reviewer]);
  if (error) return <ErrorState error={error} />;
  if (!page) return <p>Loading</p>;
  const hidden = Object.entries(page.hidden_counts);
  return (
    <>
      <p>
        {page.total} claims{hidden.length ? `; hidden: ${hidden.map(([s, c]) => `${c} ${s}`).join(", ")}` : ""}
      </p>
      <table>
        <thead>
          <tr>
            <th>Label</th>
            <th>Kind</th>
            <th>Statement</th>
          </tr>
        </thead>
        <tbody>
          {page.items.map((c) => (
            <tr key={c.claim_id}>
              <td>
                {LABEL_TEXT[c.label] ?? c.label}
                {c.flags?.includes("no_source_location") ? " (no source location)" : ""}
              </td>
              <td>{c.kind}</td>
              <td>{c.statement}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function Stub({ repoId, sha, endpoint }: { repoId: string; sha: string; endpoint: string }) {
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    setError(null);
    api.view<unknown>(repoId, sha, endpoint).then(() => setError(new Error("unexpected response: view not wired in this build")), setError);
  }, [repoId, sha, endpoint]);
  return error ? <ErrorState error={error} /> : <p>Loading</p>;
}

export function SnapshotPage() {
  const { repoId = "", sha = "", view = "overview" } = useParams();
  const v = (VIEWS as readonly string[]).includes(view) ? (view as View) : "overview";
  const base = `/r/${encodeURIComponent(repoId)}/s/${sha}`;
  return (
    <main>
      <p>
        <Link to={`/r/${encodeURIComponent(repoId)}`}>{repoId}</Link> at <code>{sha.slice(0, 12)}</code>
      </p>
      <p className="disclaimer">Static analysis only. No runtime behavior has been observed.</p>
      <nav>
        {VIEWS.map((x) => (
          <NavLink key={x} to={`${base}/${x}`}>
            {x}
          </NavLink>
        ))}
      </nav>
      {v === "claims" || v === "review" ? (
        <Claims repoId={repoId} sha={sha} reviewer={v === "review"} />
      ) : v === "graph" ? (
        <GraphView repoId={repoId} sha={sha} />
      ) : v === "ask" ? (
        <p>Explain is not implemented in this build. Provider keys stay in your browser and are never sent to Traces.</p>
      ) : (
        <Stub repoId={repoId} sha={sha} endpoint={ENDPOINT[v] ?? v} />
      )}
    </main>
  );
}
