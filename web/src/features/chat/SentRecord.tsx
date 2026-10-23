import { useEffect, useState } from "react";
import { Button } from "../../ui/States";
import { clearLog, readLog, type SentEntry } from "./sentLog";

function useLog(): SentEntry[] {
  const [log, setLog] = useState(readLog);
  useEffect(() => {
    const f = () => setLog(readLog());
    window.addEventListener("traces-sent-log", f);
    window.addEventListener("storage", f);
    return () => {
      window.removeEventListener("traces-sent-log", f);
      window.removeEventListener("storage", f);
    };
  }, []);
  return log;
}

export function SentEntryView({ e }: { e: SentEntry }) {
  return (
    <div className="flex flex-col gap-2 text-sm" data-testid="sent-entry">
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
        <dt className="text-muted">When</dt>
        <dd>{new Date(e.at).toLocaleString()}</dd>
        <dt className="text-muted">Provider</dt>
        <dd>{e.provider}</dd>
        <dt className="text-muted">Sent to</dt>
        <dd className="break-all font-mono text-xs">{e.url}</dd>
        <dt className="text-muted">Model</dt>
        <dd className="break-all font-mono text-xs">{e.model}</dd>
        <dt className="text-muted">Snapshot</dt>
        <dd className="break-all font-mono text-xs">
          {e.repoId} @{e.sha.slice(0, 7)}
        </dd>
        <dt className="text-muted">Outcome</dt>
        <dd>{e.outcome.detail}</dd>
        {e.removed.length ? (
          <>
            <dt className="text-muted">Removed before sending</dt>
            <dd className="break-all font-mono text-xs">{e.removed.join(", ")}</dd>
          </>
        ) : null}
      </dl>
      <details>
        <summary className="tap flex cursor-pointer items-center">Headers and body, exactly as sent (key replaced)</summary>
        <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-all rounded-md border border-line bg-sunken p-2 text-xs" tabIndex={0} aria-label="Sent request">
          {JSON.stringify({ headers: e.headers, body: e.body }, null, 2)}
        </pre>
      </details>
    </div>
  );
}

/** Everything this browser has sent to a provider, newest first. Stored on this device only. */
export function SentRecord() {
  const log = useLog();
  return (
    <section aria-label="What has been sent" data-testid="sent-record">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="mr-auto font-semibold">What has been sent</h2>
        <Button type="button" onClick={clearLog} disabled={!log.length}>
          Clear this record
        </Button>
      </div>
      <p className="mt-1 text-sm text-ink-2">
        A record kept only in this browser of every request sent to an AI provider, up to the last 50. Keys are never recorded.
      </p>
      {log.length ? (
        <ol className="mt-2 flex flex-col gap-2">
          {log.map((e) => (
            <li key={e.id} className="rounded-md border border-line p-3">
              <SentEntryView e={e} />
            </li>
          ))}
        </ol>
      ) : (
        <p className="mt-2 text-sm text-muted">Nothing has been sent from this browser.</p>
      )}
    </section>
  );
}
