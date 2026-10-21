import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type Snapshot } from "../api/client";
import { ErrorState } from "./common";

export function RepoPage() {
  const { repoId = "" } = useParams();
  const [snaps, setSnaps] = useState<Snapshot[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    api.snapshots(repoId).then(setSnaps, setError);
  }, [repoId]);
  return (
    <main>
      <p>
        <Link to="/">Traces</Link>
      </p>
      <h1>{repoId}</h1>
      {error ? <ErrorState error={error} /> : null}
      {snaps?.length === 0 ? <p>No snapshots. Indexing is not implemented in this build.</p> : null}
      <ul>
        {snaps?.map((s) => (
          <li key={s.id}>
            <Link to={`/r/${encodeURIComponent(repoId)}/s/${s.sha}`}>{s.sha.slice(0, 12)}</Link> {s.state}
          </li>
        ))}
      </ul>
    </main>
  );
}
