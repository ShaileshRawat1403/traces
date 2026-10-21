import { distinctParameters, type HistoryExtras } from "./historyRecord";

/**
 * Criteria echo. Each history record carries the exact parameters that produced it (history.md sections 5 and 12);
 * they are printed verbatim. The page-level criteria object (IA.md section 15, Q10) is not in the response shape yet.
 */
export function Criteria({ endpoint, records, loading }: { endpoint: string; records: readonly (HistoryExtras | null | undefined)[]; loading: boolean }) {
  const sets = distinctParameters(records);
  return (
    <details className="rounded-lg border border-line bg-surface" data-testid="criteria" open>
      <summary className="tap flex cursor-pointer flex-wrap items-center gap-x-1 px-3 text-sm font-semibold">
        Criteria used <code className="min-w-0 break-all font-normal text-xs">{endpoint}</code>
      </summary>
      <div className="flex flex-col gap-2 border-t border-line p-3 text-sm">
        <p className="text-xs text-ink-2">
          This response has no page-level criteria object yet. Below are the parameters each shown record states it was computed with, printed exactly as stored.
        </p>
        {loading ? (
          <p className="text-xs text-muted">Reading record parameters.</p>
        ) : sets.length === 0 ? (
          <p className="text-xs text-muted">The shown records carry no parameters.</p>
        ) : (
          sets.map((s) => (
            <div key={s.key} data-testid="criteria-set">
              <p className="text-xs text-muted">
                {s.count} record{s.count === 1 ? "" : "s"}
                {s.digest ? (
                  <>
                    , digest <code>{s.digest.slice(0, 16)}</code>
                  </>
                ) : null}
              </p>
              <pre className="mt-1 overflow-x-auto rounded-md border border-line bg-sunken p-2 text-xs" tabIndex={0} aria-label="Parameters, verbatim">
                {JSON.stringify(s.values, null, 2)}
              </pre>
            </div>
          ))
        )}
      </div>
    </details>
  );
}
