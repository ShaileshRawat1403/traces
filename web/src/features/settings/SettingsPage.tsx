import { useMeta } from "../../api/queries";
import { Card, ErrorState, Loading, PageHeader } from "../../ui/States";
import { ProviderSettings } from "../chat/ProviderSettings";
import { SentRecord } from "../chat/SentRecord";

export function SettingsPage() {
  const meta = useMeta();
  return (
    <main id="main" tabIndex={-1} className="mx-auto max-w-3xl px-4 py-6 focus:outline-none">
      <PageHeader title="Settings" />
      <div className="grid gap-4">
        <Card>
          <h2 className="mb-1 font-semibold">AI provider for chat (optional)</h2>
          <p className="mb-3 text-sm text-ink-2">
            Traces works without any AI key. Chat sends a scoped set of evidence from this browser directly to the provider below, after you approve exactly what is sent. The key
            stays in this browser and is never sent to the Traces API or written to any log. Providers that do not accept requests from a web page (CORS) are not supported:
            Traces does not relay requests.
          </p>
          <ProviderSettings />
        </Card>
        <Card>
          <SentRecord />
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
