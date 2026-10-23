import * as Dialog from "@radix-ui/react-dialog";
import type { OutboundItem } from "../../api/client";
import { StatusChip } from "../../ui/StatusChip";
import { Button } from "../../ui/States";
import { keptManifest, outgoing, type Bundle } from "./bundle";
import { shortId } from "./citations";
import { PROVIDERS, buildRequest, hostOf, type ProviderConfig } from "./providers";

export interface Pending {
  question: string;
  bundle: Bundle;
  manifest: OutboundItem[];
}

/** Per-send consent. Shows the destination, every evidence item, the manifest and the exact request body. Nothing is sent
 * until the user presses Send; Cancel or Escape sends nothing. */
export function ConsentDialog({
  pending,
  cfg,
  removed,
  onToggle,
  onCancel,
  onSend,
}: {
  pending: Pending | null;
  cfg: ProviderConfig;
  removed: ReadonlySet<string>;
  onToggle: (claimId: string) => void;
  onCancel: () => void;
  onSend: () => void;
}) {
  const b = pending?.bundle;
  const out = b ? outgoing(b, removed) : null;
  // A placeholder stands in for the key so the preview shows which header will carry it; the real key is only added
  // when Send is pressed, and shownHeaders never contain it.
  const preview = out ? buildRequest(cfg, PROVIDERS[cfg.kind].needsKey ? "placeholder" : "", out.prompt) : null;
  const host = preview ? hostOf(preview.url) : "";
  const kept = pending ? keptManifest(pending.manifest, removed) : [];
  const total = kept.reduce((n, m) => n + m.chars, 0);
  const shownHeaders = preview?.shownHeaders ?? {};
  return (
    <Dialog.Root open={!!pending} onOpenChange={(o) => !o && onCancel()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-ink/30" />
        <Dialog.Content
          className="fixed inset-x-0 bottom-0 z-50 flex max-h-[92dvh] flex-col rounded-t-lg border-t border-line bg-canvas shadow-xl focus:outline-none md:inset-x-auto md:left-1/2 md:top-1/2 md:bottom-auto md:max-h-[88dvh] md:w-[min(760px,94vw)] md:-translate-x-1/2 md:-translate-y-1/2 md:rounded-lg md:border"
          data-testid="consent-dialog"
        >
          <div className="border-b border-line bg-surface px-4 py-3">
            <Dialog.Title className="text-base font-semibold">Review what will be sent</Dialog.Title>
            <Dialog.Description className="mt-1 text-sm text-ink-2">
              Nothing has left this browser yet. If you press Send, this browser sends the text below directly to {host}. Traces does not see your key or the answer.
            </Dialog.Description>
          </div>
          {pending && b && out && preview ? (
            <div className="flex flex-col gap-4 overflow-y-auto p-4 text-sm">
              <section aria-label="Destination">
                <h3 className="font-semibold">Destination</h3>
                <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
                  <dt className="text-muted">Provider</dt>
                  <dd>{PROVIDERS[cfg.kind].name}</dd>
                  <dt className="text-muted">Endpoint</dt>
                  <dd className="break-all font-mono text-xs" data-testid="consent-url">
                    {preview.url}
                  </dd>
                  <dt className="text-muted">Model</dt>
                  <dd className="break-all font-mono text-xs">{cfg.model}</dd>
                  <dt className="text-muted">Headers</dt>
                  <dd className="break-all font-mono text-xs">
                    {Object.entries(shownHeaders)
                      .map(([k, v]) => `${k}: ${v}`)
                      .join("; ")}
                  </dd>
                </dl>
              </section>

              <section aria-label="Evidence items">
                <h3 className="font-semibold">
                  Evidence items ({out.claimIds.length} of {b.evidence.length} will be sent)
                </h3>
                <p className="mt-1 text-xs text-muted">
                  {b.rebuildable
                    ? "Untick an item to leave it out. The prompt below updates to exactly what will be sent."
                    : "This bundle cannot be rebuilt in the browser, so items cannot be removed. It is sent exactly as the server prepared it, or not at all."}
                </p>
                <ul className="mt-2 flex flex-col gap-2">
                  {b.evidence.map((e) => (
                    <li key={e.claim_id} className="rounded-md border border-line bg-surface p-2" data-testid="consent-item">
                      <label className="flex items-start gap-2">
                        <input type="checkbox" className="mt-1" checked={!removed.has(e.claim_id)} disabled={!b.rebuildable} onChange={() => onToggle(e.claim_id)} />
                        <span className="flex min-w-0 flex-col gap-1">
                          <span className="flex flex-wrap items-center gap-2">
                            <StatusChip status={e.status} label={e.label} />
                            <code className="break-all text-xs">{e.where}</code>
                          </span>
                          <span className="break-words">{e.statement}</span>
                          <span className="break-all font-mono text-xs text-muted">{e.claim_id}</span>
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
              </section>

              <section aria-label="Manifest">
                <h3 className="font-semibold">Manifest</h3>
                <p className="mt-1 text-xs text-muted">
                  {kept.length} items, {total.toLocaleString("en-US")} characters, with the server's SHA-256 of each.
                </p>
                <div className="mt-1 overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="text-muted">
                      <tr>
                        <th scope="col" className="py-1 pr-3 font-medium">
                          Item
                        </th>
                        <th scope="col" className="py-1 pr-3 font-medium">
                          Source
                        </th>
                        <th scope="col" className="py-1 pr-3 text-right font-medium">
                          Characters
                        </th>
                        <th scope="col" className="py-1 font-medium">
                          SHA-256
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {kept.map((m, i) => (
                        <tr key={i} className="border-t border-line align-top" data-testid="consent-manifest-row">
                          <td className="py-1 pr-3">{m.kind.replace(/_/g, " ")}</td>
                          <td className="break-all py-1 pr-3 font-mono">{m.claim_id ? `${shortId(m.claim_id)} ${m.file ?? ""}` : "none"}</td>
                          <td className="py-1 pr-3 text-right tabular-nums">{m.chars.toLocaleString("en-US")}</td>
                          <td className="py-1 font-mono">{m.sha256.slice(0, 12)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              <section aria-label="Exact request body">
                <h3 className="font-semibold">Exact request body</h3>
                <pre className="mt-1 max-h-72 overflow-auto whitespace-pre-wrap break-all rounded-md border border-line bg-sunken p-2 text-xs" tabIndex={0} aria-label="Request body" data-testid="consent-body">
                  {JSON.stringify(preview.body, null, 2)}
                </pre>
              </section>
            </div>
          ) : null}
          <div className="flex flex-wrap justify-end gap-2 border-t border-line bg-surface px-4 py-3">
            <Dialog.Close asChild>
              <Button type="button">Cancel, send nothing</Button>
            </Dialog.Close>
            {out && out.claimIds.length === 0 ? <p className="mr-auto self-center text-xs text-rejected">Keep at least one evidence item, or cancel.</p> : null}
            <Button type="button" variant="primary" onClick={onSend} disabled={!out || out.claimIds.length === 0}>
              Send to {host}
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
