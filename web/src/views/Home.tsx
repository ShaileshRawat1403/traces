import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, type Repo } from "../api/client";
import { ErrorState } from "./common";

export function Home() {
  const [repos, setRepos] = useState<Repo[] | null>(null);
  const [url, setUrl] = useState("");
  const [error, setError] = useState<unknown>(null);

  const load = () => api.repos().then(setRepos, setError);
  useEffect(() => {
    void load();
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await api.registerRepo(url.trim());
      setUrl("");
      await load();
    } catch (err) {
      setError(err);
    }
  };

  return (
    <main>
      <h1>Traces</h1>
      <p>Evidence-backed maps of public GitHub repositories. Static analysis only.</p>
      <form onSubmit={submit}>
        <label htmlFor="repo-url">Public GitHub repository URL</label>
        <input id="repo-url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://github.com/owner/repo" />
        <button type="submit" disabled={!url.trim()}>
          Add repository
        </button>
      </form>
      {error ? <ErrorState error={error} /> : null}
      <h2>Repositories</h2>
      {repos === null ? (
        <p>Loading</p>
      ) : repos.length === 0 ? (
        <p>No repositories yet.</p>
      ) : (
        <ul>
          {repos.map((r) => (
            <li key={r.id}>
              <Link to={`/r/${encodeURIComponent(r.id)}`}>
                {r.owner}/{r.name}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
