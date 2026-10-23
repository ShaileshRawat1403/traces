import { useQuery } from "@tanstack/react-query";
import { useId } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type Component } from "../../api/client";
import { keys } from "../../api/queries";
import { snapshotBase } from "../../app/nav";
import { EXPECTED_LABEL, isStatus } from "../../status/status";
import { HiddenCounts } from "../../ui/HiddenCounts";
import { Empty, ErrorState, Loading, PageHeader } from "../../ui/States";
import { StatusChip } from "../../ui/StatusChip";
import { LAYERS, LAYER_COLOR } from "../layers";
import { useParam } from "./useDrawer";

const PATHS_SHOWN = 40;

/** Shown when the API gives no layer reason (snapshots indexed before reasons existed). */
export const PATH_RULE_NOTE =
  "Components and layers are assigned by the API from file paths with a named rule (shown on each component). The layer is the API's label, not a reading of what the code does, so a library's source folder can be labelled backend.";
export const REASON_NOTE = "Components and layers are assigned by the API. Each component shows the API's own reason for its layer: the files it counted and the rule it applied.";

/** The page note: the API's reasons when every component has one, otherwise the path-rule note. */
export function layerNote(items: readonly Component[]): string {
  return items.length > 0 && items.every((c) => !!c.reason) ? REASON_NOTE : PATH_RULE_NOTE;
}

export function filterComponents(items: readonly Component[], text: string, layer: string): Component[] {
  const t = text.trim().toLowerCase();
  return items.filter((c) => (!layer || c.layer === layer) && (!t || c.name.toLowerCase().includes(t) || c.paths.some((p) => p.toLowerCase().includes(t))));
}

/** Claim counts by status, rejected split out: it is counted as hidden, never shown as part of the component. */
export function splitCounts(counts: Record<string, number>): { shown: [string, number][]; rejected: number } {
  const shown = Object.entries(counts)
    .filter(([s, n]) => s !== "rejected" && n > 0)
    .sort(([a], [b]) => a.localeCompare(b));
  return { shown, rejected: counts.rejected ?? 0 };
}

export function ComponentsView({ items, base }: { items: Component[]; base: string }) {
  const [text, setText] = useParam("q");
  const [layer, setLayer] = useParam("layer");
  const ids = { q: useId(), l: useId() };
  const present = new Set(items.map((c) => c.layer));
  const layers = LAYERS.filter((l) => present.has(l));
  const shown = filterComponents(items, text, layer);
  const rejected = items.reduce((n, c) => n + (c.claim_counts.rejected ?? 0), 0);
  return (
    <section aria-label="Components" data-testid="components">
      <p className="mb-3 rounded-md border border-line bg-surface p-3 text-sm text-ink-2" data-testid="layer-note">
        {layerNote(items)}
      </p>
      <form role="search" className="mb-3 flex flex-wrap items-end gap-3 rounded-lg border border-line bg-surface p-3" onSubmit={(e) => e.preventDefault()}>
        <label htmlFor={ids.q} className="flex min-w-0 flex-1 flex-col gap-1 text-sm">
          <span className="font-medium">Filter components</span>
          <input id={ids.q} type="search" value={text} onChange={(e) => setText(e.target.value)} placeholder="Name or file path" className="tap rounded-md border border-line-strong px-2" />
        </label>
        <label htmlFor={ids.l} className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Layer</span>
          <select id={ids.l} value={layer} onChange={(e) => setLayer(e.target.value)} className="tap rounded-md border border-line-strong px-2">
            <option value="">All</option>
            {layers.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
        </label>
      </form>
      <p className="mb-2 text-sm text-ink-2" role="status" data-testid="components-count">
        Showing {shown.length} of {items.length} components.
      </p>
      <div className="mb-3">
        <HiddenCounts counts={rejected ? { rejected } : {}} reviewHref={`${base}/review`} />
      </div>
      {shown.length === 0 ? (
        <Empty title={items.length ? "No component matches the filter" : "No components recorded"}>
          {items.length ? "Clear the filter to see every component." : "The API returned no components for this snapshot."}
        </Empty>
      ) : (
        <ul className="grid gap-2 md:grid-cols-2" aria-label="Component list">
          {shown.map((c) => {
            const counts = splitCounts(c.claim_counts);
            return (
              <li key={c.id} className="min-w-0 rounded-lg border border-line bg-surface p-3" data-testid="component-item">
                <h2 className="break-all font-mono text-sm font-semibold">{c.name}</h2>
                <dl className="mt-1 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-0.5 text-sm">
                  <dt className="text-muted">Layer</dt>
                  <dd className="inline-flex items-center gap-1.5">
                    <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: LAYER_COLOR[c.layer] }} aria-hidden="true" />
                    <span data-testid="component-layer">{c.layer}</span>
                  </dd>
                  {c.reason ? (
                    <>
                      <dt className="text-muted">Why</dt>
                      <dd className="break-words text-xs" data-testid="component-reason">
                        {c.reason}
                      </dd>
                    </>
                  ) : (
                    <>
                      <dt className="text-muted">Rule</dt>
                      <dd className="break-all text-xs" data-testid="component-rule">
                        <span className="font-mono">{c.rule}</span>
                        <span className="block text-muted">Path rule only; the API gave no reason for this layer.</span>
                      </dd>
                    </>
                  )}
                  <dt className="text-muted">Files</dt>
                  <dd>{c.paths.length}</dd>
                </dl>
                {counts.shown.length ? (
                  <ul className="mt-2 flex flex-wrap gap-2" aria-label={`Claims touching ${c.name}, by label`}>
                    {counts.shown.map(([s, n]) => (
                      <li key={s} className="inline-flex items-center gap-1 text-xs">
                        <StatusChip status={s} label={isStatus(s) ? EXPECTED_LABEL[s] : undefined} />
                        <span className="tabular-nums">{n.toLocaleString("en-US")}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 text-xs text-muted">No claims touch this component.</p>
                )}
                {counts.rejected ? <p className="mt-1 text-xs text-muted">{counts.rejected} rejected claims hidden.</p> : null}
                <details className="mt-2 text-sm">
                  <summary className="tap flex cursor-pointer items-center">Files ({c.paths.length})</summary>
                  <ul className="mt-1 flex flex-col gap-1">
                    {c.paths.slice(0, PATHS_SHOWN).map((p) => (
                      <li key={p} className="min-w-0">
                        <Link to={`${base}/source?path=${encodeURIComponent(p)}`} className="tap-sm inline-flex break-all font-mono text-xs">
                          {p}
                        </Link>
                      </li>
                    ))}
                  </ul>
                  {c.paths.length > PATHS_SHOWN ? <p className="mt-1 text-xs text-muted">and {c.paths.length - PATHS_SHOWN} more files.</p> : null}
                </details>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

export function ComponentsPage() {
  const { repoId = "", sha = "" } = useParams();
  const q = useQuery({ queryKey: keys.view("components", repoId, sha), queryFn: () => api.components(repoId, sha) });
  return (
    <>
      <PageHeader title="Components">Deterministic components and layers from the API, with claim counts by label. Open a file to read it at the pinned commit.</PageHeader>
      {q.isPending ? <Loading label="Loading components" /> : q.isError ? <ErrorState error={q.error} what="Components" /> : <ComponentsView items={q.data} base={snapshotBase(repoId, sha)} />}
    </>
  );
}
