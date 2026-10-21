import { useMeta } from "../../api/queries";
import { Card, ErrorState, Loading, PageHeader } from "../../ui/States";

export function SettingsPage() {
  const meta = useMeta();
  return (
    <main id="main" tabIndex={-1} className="mx-auto max-w-3xl px-4 py-6 focus:outline-none">
      <PageHeader title="Settings" />
      <div className="grid gap-4">
        <Card>
          <h2 className="mb-1 font-semibold">AI provider (optional)</h2>
          <p className="text-sm text-ink-2">
            Traces works without any AI key. Optional chat will use a key you provide. The key stays in this browser (session storage by default, or this device if you choose
            "Remember on this device"), is sent only to the provider you configure, and never reaches the Traces API or its logs. Before anything leaves the browser you will see
            exactly which snippets would be sent.
          </p>
          <p className="mt-2 text-sm text-muted">Explain on a snapshot already answers from stored evidence and needs no key. A chat key is not collected in this build.</p>
        </Card>
        <Card>
          <h2 className="mb-2 font-semibold">This build</h2>
          {meta.isPending ? (
            <Loading />
          ) : meta.isError ? (
            <ErrorState error={meta.error} what="Build information" />
          ) : (
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
              <dt className="text-muted">Version</dt>
              <dd>{meta.data.version}</dd>
              <dt className="text-muted">Evidence schema</dt>
              <dd>{meta.data.evidence_schema}</dd>
              <dt className="text-muted">Isolation</dt>
              <dd>{meta.data.isolation}</dd>
              <dt className="text-muted">Available</dt>
              <dd data-testid="capabilities">
                {Object.entries(meta.data.capabilities)
                  .filter(([, v]) => v)
                  .map(([k]) => k)
                  .join(", ") || "none"}
              </dd>
              <dt className="text-muted">Not available yet</dt>
              <dd>
                {Object.entries(meta.data.capabilities)
                  .filter(([, v]) => !v)
                  .map(([k]) => k)
                  .join(", ") || "none"}
              </dd>
            </dl>
          )}
        </Card>
      </div>
    </main>
  );
}
