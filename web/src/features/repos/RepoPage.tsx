import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { keys, useHead, useRepo, useSnapshots } from "../../api/queries";
import { snapshotBase } from "../../app/nav";
import { isTerminal, stepViews } from "../jobs/phases";
import { useJob } from "../jobs/useJob";
import { Button, Empty, ErrorState, Loading, PageHeader } from "../../ui/States";

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

function CompareNewest({ repoId, snaps }: { repoId: string; snaps: { sha: string; state: string; indexed_at?: string | null; created_at: string }[] }) {
  const ready = snaps.filter((s) => s.state === "ready").sort((a, b) => (b.indexed_at ?? b.created_at).localeCompare(a.indexed_at ?? a.created_at));
  if (ready.length < 2) return null;
  const head = ready[0]!;
  const older = ready[1]!;
  return (
    <p className="mt-3 text-sm">
      <Link to={`${snapshotBase(repoId, head.sha)}/history?tab=compare&base=${older.sha}&head=${head.sha}`}>
        Compare @{head.sha.slice(0, 7)} with @{older.sha.slice(0, 7)}
      </Link>
      <span className="mt-1 block text-[13px] text-muted">Records stored as added or removed between these commits. This is not a description of what the code does.</span>
    </p>
  );
}

function jobStoreKey(repoId: string) {
  return `traces-index-job:${repoId}`;
}

function IndexRun({ repoId, jobId }: { repoId: string; jobId: string }) {
  const qc = useQueryClient();
  const q = useJob(jobId);
  const job = q.data?.job;
  useEffect(() => {
    if (job && isTerminal(job)) void qc.invalidateQueries({ queryKey: keys.snapshots(repoId) });
  }, [job, qc, repoId]);
  if (q.isPending) return <p className="mt-3 text-sm text-muted">Reading the index job.</p>;
  if (q.isError || !job) return <ErrorState error={q.error} what="Index job" />;
  const steps = stepViews(job);
  const current = steps.find((s) => s.state === "active") ?? steps.find((s) => s.state === "failed");
  const [idRepo, sha] = (job.snapshot_id ?? "").split("@");
  const done = job.state === "succeeded" && idRepo && sha;
  return (
    <div className="mt-4" aria-live="polite">
      <p className="text-sm font-medium">{done ? "Indexing finished" : job.state === "failed" ? "Indexing failed" : job.state === "cancelled" ? "Indexing cancelled" : `Indexing: ${current?.title ?? job.phase}`}</p>
      <ol className="mt-2 flex gap-1" aria-label="Index steps">
        {steps.map((s) => (
          <li key={s.phase} className="min-w-0 flex-1">
            <span
              className={`block h-1.5 rounded-full ${s.state === "done" ? "bg-verified" : s.state === "active" ? "bg-ink" : s.state === "failed" ? "bg-rejected" : "bg-white/10"}`}
            />
            <span className="sr-only">
              {s.title}, {s.state}
            </span>
          </li>
        ))}
      </ol>
      <p className="mt-2 text-[13px] text-muted">{current?.help ?? (done ? "The snapshot is pinned to this commit. Opening it does not re-run the repository." : job.message ?? "")}</p>
      {job.error ? (
        <p className="mt-2 text-sm text-rejected" role="alert">
          {job.error.code}: {job.error.message}
        </p>
      ) : null}
      {done ? (
        <p className="mt-3">
          <Link to={snapshotBase(idRepo, sha)} className="tap inline-flex items-center rounded-md bg-ink px-3 text-sm font-medium text-canvas no-underline hover:no-underline">
            Open the snapshot
          </Link>
        </p>
      ) : null}
    </div>
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
  const repo = useRepo(repoId);
  const snaps = useSnapshots(repoId);
  const [jobId, setJobId] = useState<string | null>(() => {
    try {
      return sessionStorage.getItem(jobStoreKey(repoId));
    } catch {
      return null;
    }
  });
  const start = useMutation({
    mutationFn: () => api.startIndex(repoId, { reindex: false }),
    onSuccess: (job) => {
      try {
        sessionStorage.setItem(jobStoreKey(repoId), job.id);
      } catch {
        /* the progress still shows for this visit */
      }
      setJobId(job.id);
    },
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

      <div className="grid gap-8">
        <section aria-labelledby="snap-h">
          <h2 id="snap-h" className="text-sm font-medium tracking-[-0.02em] text-ink-2">
            Snapshots
          </h2>
          <p className="mt-1 max-w-xl text-sm text-ink-2">A snapshot is this repository at one commit. Open a ready one to see the architecture, follow a path, and ask from the stored evidence.</p>
          {snaps.isPending ? (
            <Loading label="Loading snapshots" />
          ) : snaps.isError ? (
            <ErrorState error={snaps.error} what="Snapshots" />
          ) : snaps.data.length === 0 ? (
            <Empty title="No snapshots yet">Index the repository to create one. Indexing does not run the repository's own code.</Empty>
          ) : (
            <ul className="mt-2" data-testid="snapshot-list">
              {snaps.data.map((s) => {
                const by = (s.stats as { by_status?: Record<string, number> }).by_status;
                const records = by ? Object.values(by).reduce((a, b) => a + b, 0) : null;
                return (
                  <li key={s.id} className="border-b border-white/8">
                    <Link to={snapshotBase(repoId, s.sha)} className="flex flex-col py-3.5 text-ink no-underline hover:no-underline">
                      <span className="flex items-baseline justify-between gap-3">
                        <span className="font-mono text-sm">@{s.sha.slice(0, 12)}</span>
                        <span className="text-[13px] text-muted">{s.state === "ready" ? "Open" : s.state}</span>
                      </span>
                      <span className="mt-1 text-[13px] text-muted">
                        {s.state}
                        {" · "}
                        {s.evidence_schema}
                        {records !== null ? ` · ${records.toLocaleString("en-US")} records` : ""}
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
          {snaps.data && snaps.data.filter((s) => s.state === "ready").length >= 2 ? <CompareNewest repoId={repoId} snaps={snaps.data} /> : null}
        </section>

        <section aria-labelledby="index-h">
          <h2 id="index-h" className="text-sm font-medium tracking-[-0.02em] text-ink-2">
            Index
          </h2>
          <p className="mt-1 max-w-xl text-sm text-ink-2">
            {snaps.data?.some((s) => s.state === "ready")
              ? "Index the latest commit when the default branch has moved. A snapshot you already have stays pinned to its commit."
              : "Indexing reads the repository at one commit and stores the evidence. The repository's own code is never run."}
          </p>
          <div className="mt-3">
            <HeadStatus repoId={repoId} />
          </div>
          <div className="mt-3">
            <Button variant={snaps.data?.some((s) => s.state === "ready") ? "secondary" : "primary"} onClick={() => start.mutate()} disabled={start.isPending}>
              {start.isPending ? "Starting" : "Index latest commit"}
            </Button>
          </div>
          {jobId ? <IndexRun repoId={repoId} jobId={jobId} /> : null}
          {start.isError ? (
            <div className="mt-3">
              <ErrorState error={start.error} what="Indexing" />
            </div>
          ) : null}
          <details className="mt-4">
            <summary className="cursor-pointer text-sm text-muted">Already have a job id?</summary>
            <OpenJob />
          </details>
        </section>
      </div>
    </main>
  );
}
