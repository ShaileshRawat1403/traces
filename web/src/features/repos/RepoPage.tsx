import { useMutation } from "@tanstack/react-query";
import { useId, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { useHead, useRepo, useSnapshots } from "../../api/queries";
import { snapshotBase } from "../../app/nav";
import { Button, Card, Empty, ErrorState, Loading, PageHeader } from "../../ui/States";

function HeadStatus({ repoId }: { repoId: string }) {
  const head = useHead(repoId);
  if (head.isPending) return <Loading label="Checking latest commit" />;
  if (head.isError) return <ErrorState error={head.error} what="Latest-commit check" />;
  const h = head.data;
  return (
    <p className="text-sm">
      Default branch {h.default_branch ?? "unknown"}, latest {h.latest_sha ? <code>{h.latest_sha.slice(0, 7)}</code> : "unknown"}
      {h.behind ? " (newer than the displayed snapshot)" : ""}.
    </p>
  );
}

function OpenJob() {
  const nav = useNavigate();
  const [id, setId] = useState("");
  const fid = useId();
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (id.trim()) nav(`/jobs/${encodeURIComponent(id.trim())}`);
  };
  return (
    <form onSubmit={submit} className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-end">
      <div className="flex flex-1 flex-col">
        <label htmlFor={fid} className="text-sm font-medium">
          Follow an existing job by id
        </label>
        <input id={fid} value={id} onChange={(e) => setId(e.target.value)} className="tap rounded-md border border-line-strong px-3 font-mono text-sm" autoComplete="off" />
      </div>
      <Button type="submit" disabled={!id.trim()}>
        Open job
      </Button>
    </form>
  );
}

export function RepoPage() {
  const { repoId = "" } = useParams();
  const nav = useNavigate();
  const repo = useRepo(repoId);
  const snaps = useSnapshots(repoId);
  const start = useMutation({
    mutationFn: () => api.startIndex(repoId, { reindex: false }),
    onSuccess: (job) => nav(`/jobs/${encodeURIComponent(job.id)}`),
  });

  return (
    <main id="main" tabIndex={-1} className="mx-auto max-w-3xl px-4 py-6 focus:outline-none">
      <p className="mb-2 text-sm">
        <Link to="/">Repositories</Link>
      </p>
      {repo.isError ? (
        <ErrorState error={repo.error} what="Repository" />
      ) : (
        <PageHeader title={repo.data ? `${repo.data.owner}/${repo.data.name}` : "Repository"}>
          {repo.data ? (
            <a href={repo.data.url} rel="noreferrer noopener" target="_blank">
              {repo.data.url}
              <span className="sr-only"> (opens GitHub in a new tab)</span>
            </a>
          ) : null}
        </PageHeader>
      )}

      <div className="grid gap-4">
        <Card>
          <h2 className="mb-2 font-semibold">Freshness</h2>
          <HeadStatus repoId={repoId} />
        </Card>

        <Card>
          <h2 className="mb-2 font-semibold">Index</h2>
          <p className="text-sm text-ink-2">Indexing fetches the repository at a pinned commit and runs the extractor and validators in an isolated sandbox. The repository's own code is never run.</p>
          <div className="mt-3">
            <Button variant="primary" onClick={() => start.mutate()} disabled={start.isPending}>
              {start.isPending ? "Starting" : "Index latest commit"}
            </Button>
          </div>
          {start.isError ? (
            <div className="mt-3">
              <ErrorState error={start.error} what="Indexing" />
            </div>
          ) : null}
          <OpenJob />
        </Card>

        <section aria-labelledby="snap-h">
          <h2 id="snap-h" className="mb-2 text-lg font-semibold">
            Snapshots
          </h2>
          {snaps.isPending ? (
            <Loading label="Loading snapshots" />
          ) : snaps.isError ? (
            <ErrorState error={snaps.error} what="Snapshots" />
          ) : snaps.data.length === 0 ? (
            <Empty title="No snapshots yet">Index the repository to create one.</Empty>
          ) : (
            <ul className="flex flex-col gap-2" data-testid="snapshot-list">
              {snaps.data.map((s) => {
                const by = (s.stats as { by_status?: Record<string, number> }).by_status;
                return (
                  <li key={s.id}>
                    <Link
                      to={snapshotBase(repoId, s.sha)}
                      className="tap flex flex-col rounded-lg border border-line bg-surface px-4 py-3 text-ink no-underline hover:border-line-strong hover:no-underline"
                    >
                      <span className="font-mono text-sm">@{s.sha.slice(0, 12)}</span>
                      <span className="text-sm text-muted">
                        {s.state} · {s.evidence_schema}
                        {by ? ` · ${Object.values(by).reduce((a, b) => a + b, 0).toLocaleString("en-US")} records` : ""}
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}
