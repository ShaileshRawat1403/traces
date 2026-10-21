import type { ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { snapshotBase } from "../../app/nav";
import { ErrorState, Loading, PageHeader } from "../../ui/States";
import { isTerminal, stepViews, type StepState } from "./phases";
import { useJob } from "./useJob";

const STEP_STYLE: Record<StepState, { mark: string; cls: string; text: string }> = {
  pending: { mark: "○", cls: "text-muted", text: "Waiting" },
  active: { mark: "◉", cls: "text-accent", text: "In progress" },
  done: { mark: "✓", cls: "text-verified", text: "Done" },
  failed: { mark: "✕", cls: "text-rejected", text: "Failed" },
  skipped: { mark: "–", cls: "text-muted", text: "Not run" },
};

export function JobPage() {
  const { jobId = "" } = useParams();
  const q = useJob(jobId);
  if (q.isPending) return <Wrap><Loading label="Loading job" /></Wrap>;
  if (q.isError) return <Wrap><ErrorState error={q.error} what="Job" /></Wrap>;
  const { job } = q.data;
  const steps = stepViews(job);
  const pct = Math.round(Math.max(0, Math.min(1, job.progress)) * 100);
  const [repoId, sha] = (job.snapshot_id ?? "").split("@");
  return (
    <Wrap>
      <PageHeader title="Index job">
        <span className="font-mono text-sm">{job.id}</span>
      </PageHeader>
      <div className="mb-4 rounded-lg border border-line bg-surface p-4">
        <p className="font-medium" aria-live="polite">
          {job.state === "succeeded" ? "Indexing finished" : job.state === "failed" ? "Indexing failed" : job.state === "cancelled" ? "Indexing cancelled" : `Running: ${job.phase}`}
        </p>
        <div className="mt-2 h-2 w-full overflow-hidden rounded bg-sunken" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} aria-label="Overall progress">
          <div className="h-full bg-accent" style={{ width: `${pct}%` }} />
        </div>
        <p className="mt-1 text-sm text-muted">
          {pct}% · version {job.version} · updated {new Date(job.updated_at).toLocaleString()}
          {!isTerminal(job) ? " · checking every 1.5 s" : ""}
        </p>
        {job.message ? <p className="mt-2 text-sm">{job.message}</p> : null}
        {job.error ? (
          <p className="mt-2 text-sm text-rejected" role="alert">
            {job.error.code}: {job.error.message}
          </p>
        ) : null}
        {job.state === "succeeded" && repoId && sha ? (
          <p className="mt-2">
            <Link to={snapshotBase(repoId, sha)}>Open the snapshot</Link>
          </p>
        ) : null}
      </div>
      <ol className="flex flex-col gap-2" aria-label="Index steps" data-testid="job-steps">
        {steps.map((s) => {
          const st = STEP_STYLE[s.state];
          return (
            <li key={s.phase} className="rounded-lg border border-line bg-surface p-3" data-state={s.state}>
              <div className="flex items-center gap-2">
                <span aria-hidden="true" className={`w-5 text-center ${st.cls}`}>
                  {st.mark}
                </span>
                <span className="font-medium">{s.title}</span>
                <span className={`ml-auto text-sm ${st.cls}`}>{st.text}</span>
              </div>
              <p className="ml-7 text-sm text-muted">{s.help}</p>
              {s.events.length ? (
                <details className="ml-7 mt-1 text-sm">
                  <summary className="cursor-pointer">{s.events.length} events</summary>
                  <ul className="mt-1 flex flex-col gap-0.5">
                    {s.events.map((e, i) => (
                      <li key={i} className={e.level === "error" ? "text-rejected" : "text-ink-2"}>
                        <time className="font-mono text-xs text-muted">{e.at}</time> {e.message}
                      </li>
                    ))}
                  </ul>
                </details>
              ) : null}
            </li>
          );
        })}
      </ol>
    </Wrap>
  );
}

function Wrap({ children }: { children: ReactNode }) {
  return (
    <main id="main" tabIndex={-1} className="mx-auto max-w-3xl px-4 py-6 focus:outline-none">
      {children}
    </main>
  );
}
