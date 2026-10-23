import type { ReactNode } from "react";
import { readHistoryExtras } from "./historyRecord";

function Box({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-line bg-surface p-4" aria-label={title}>
      <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted">{title}</h2>
      {children}
    </section>
  );
}

/** Citations, parameters and metrics of a history or documented record, shown as stored. Renders nothing for code records. */
export function HistoryEvidence({ raw }: { raw: unknown }) {
  const x = readHistoryExtras(raw);
  if (x.citations.length === 0 && !x.parameters && !x.metrics) return null;
  return (
    <>
      {x.citations.length ? (
        <Box title={`Cited commits (${x.citations.length})`}>
          <ol className="flex flex-col gap-2 text-sm" data-testid="history-citations">
            {x.citations.map((c) => (
              <li key={c.commit} className="flex flex-col gap-0.5">
                <code className="break-all">{c.commit}</code>
                {c.parents.length ? <span className="text-xs text-muted">parents {c.parents.map((p) => p.slice(0, 7)).join(", ")}</span> : null}
                {c.pr?.number ? <span className="text-xs">PR #{c.pr.number}{c.pr.fetched_at ? `, cached ${c.pr.fetched_at}` : ""}</span> : null}
                {c.paths.map((p) => (
                  <span key={p.path} className="break-all font-mono text-xs">
                    {p.status ?? "?"} {p.old_path ? `${p.old_path} to ` : ""}
                    {p.path}
                    {p.similarity !== null ? ` (Git similarity ${p.similarity}%)` : ""}
                  </span>
                ))}
              </li>
            ))}
          </ol>
        </Box>
      ) : null}
      {x.parameters ? (
        <Box title="Parameters (criteria), verbatim">
          {x.parameters.digest ? <p className="mb-1 break-all font-mono text-xs text-muted">digest {x.parameters.digest}</p> : null}
          <pre className="overflow-x-auto rounded-md bg-sunken p-2 text-xs" tabIndex={0} aria-label="Record parameters">
            {JSON.stringify(x.parameters.values, null, 2)}
          </pre>
        </Box>
      ) : null}
      {x.metrics ? (
        <Box title="Metrics, as recorded">
          <pre className="overflow-x-auto rounded-md bg-sunken p-2 text-xs" tabIndex={0} aria-label="Record metrics">
            {JSON.stringify(x.metrics, null, 2)}
          </pre>
        </Box>
      ) : null}
    </>
  );
}
