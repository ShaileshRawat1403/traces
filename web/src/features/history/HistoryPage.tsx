import * as Tabs from "@radix-ui/react-tabs";
import { useQuery } from "@tanstack/react-query";
import { useId, useState, type FormEvent, type ReactNode } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { api, type ClaimPage, type ClaimSummary } from "../../api/client";
import { snapshotBase } from "../../app/nav";
import { Button, Empty, ErrorState, Loading, PageHeader } from "../../ui/States";
import { EvidenceDrawer } from "../evidence/EvidenceDrawer";
import { BarChart, type Bar } from "./BarChart";
import { Criteria } from "./Criteria";
import { HistoryItem, PageMeta, shortSha, useHistoryRecords, visibleItems } from "./HistoryItems";
import { metric, type HistoryExtras } from "./historyRecord";

export const HISTORY_TABS = [
  { id: "timeline", label: "Timeline" },
  { id: "hotspots", label: "Hotspots" },
  { id: "cochange", label: "Co-change" },
  { id: "milestones", label: "Milestones" },
  { id: "compare", label: "Compare" },
] as const;
type TabId = (typeof HISTORY_TABS)[number]["id"];
const PAGE = 50;
const SHA40 = /^[0-9a-f]{40}$/;

function useParam() {
  const [sp, setSp] = useSearchParams();
  const set = (patch: Record<string, string | null>) =>
    setSp((p) => {
      const n = new URLSearchParams(p);
      for (const [k, v] of Object.entries(patch)) {
        if (v) n.set(k, v);
        else n.delete(k);
      }
      return n;
    });
  return [sp, set] as const;
}

interface PanelProps {
  repoId: string;
  sha: string;
  onEvidence: (id: string) => void;
}

/** Shared frame: real request, honest 501, criteria echo, hidden counts, then the panel's own renderer. */
function Frame({
  q,
  what,
  endpoint,
  repoId,
  sha,
  children,
}: {
  q: { isPending: boolean; isError: boolean; error: unknown; data: ClaimPage | undefined };
  what: string;
  endpoint: string;
  repoId: string;
  sha: string;
  children: (shown: ClaimSummary[], records: Map<string, HistoryExtras>) => ReactNode;
}) {
  const page = q.data;
  const { shown, hidden } = page ? visibleItems(page) : { shown: [], hidden: {} };
  const rec = useHistoryRecords(repoId, sha, page ? shown : undefined);
  if (q.isPending) return <Loading label={`Loading ${what}`} />;
  if (q.isError || !page) return <ErrorState error={q.error} what={what} />;
  return (
    <div className="flex flex-col gap-3">
      <PageMeta page={page} hidden={hidden} reviewHref={`${snapshotBase(repoId, sha)}/review`} />
      <Criteria endpoint={endpoint} records={shown.map((i) => rec.byId.get(i.claim_id))} loading={rec.loading} />
      {rec.failed ? <p className="text-xs text-muted">{rec.failed} records could not be read in full; their citations and metrics are not shown.</p> : null}
      {shown.length === 0 ? <Empty title={`No ${what.toLowerCase()} records`}>The API returned no records for these criteria.</Empty> : children(shown, rec.byId)}
    </div>
  );
}

function Timeline({ repoId, sha, onEvidence }: PanelProps) {
  const [sp, set] = useParam();
  const path = sp.get("path") ?? "";
  const component = sp.get("component") ?? "";
  const offset = Math.max(0, Number(sp.get("offset")) || 0);
  const [p, setP] = useState(path);
  const [c, setC] = useState(component);
  const ids = { p: useId(), c: useId() };
  const q = useQuery({
    queryKey: ["history", "timeline", repoId, sha, path, component, offset],
    queryFn: () => api.historyTimeline(repoId, sha, { path: path || undefined, component: component || undefined, offset, limit: PAGE }),
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    set({ path: p.trim() || null, component: c.trim() || null, offset: null });
  };
  return (
    <div className="flex flex-col gap-3">
      <form onSubmit={submit} className="grid gap-2 rounded-lg border border-line bg-surface p-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end" aria-label="Timeline filters">
        <div className="flex flex-col">
          <label htmlFor={ids.p} className="text-sm font-medium">
            Path
          </label>
          <input id={ids.p} value={p} onChange={(e) => setP(e.target.value)} placeholder="backend/app/main.py" className="tap rounded-md border border-line-strong px-2 font-mono text-sm" />
        </div>
        <div className="flex flex-col">
          <label htmlFor={ids.c} className="text-sm font-medium">
            Component
          </label>
          <input id={ids.c} value={c} onChange={(e) => setC(e.target.value)} placeholder="component id" className="tap rounded-md border border-line-strong px-2 font-mono text-sm" />
        </div>
        <Button type="submit">Apply</Button>
      </form>
      <Frame q={q} what="Timeline" endpoint="GET history/timeline" repoId={repoId} sha={sha}>
        {(shown, recs) => (
          <>
            <ol className="history-spine" aria-label="Timeline records in API order">
              {shown.map((i) => (
                <HistoryItem key={i.claim_id} item={i} x={recs.get(i.claim_id)} onEvidence={onEvidence} />
              ))}
            </ol>
            <nav className="flex items-center gap-2" aria-label="Timeline pages">
              <Button disabled={offset === 0} onClick={() => set({ offset: offset - PAGE > 0 ? String(offset - PAGE) : null })}>
                Previous
              </Button>
              <Button disabled={!q.data || offset + PAGE >= q.data.total} onClick={() => set({ offset: String(offset + PAGE) })}>
                Next
              </Button>
            </nav>
          </>
        )}
      </Frame>
    </div>
  );
}

function LevelToggle({ level, onChange }: { level: "file" | "component"; onChange: (l: "file" | "component") => void }) {
  return (
    <div role="group" aria-label="Level" className="inline-flex self-start rounded-md border border-line-strong">
      {(["file", "component"] as const).map((l) => (
        <button key={l} type="button" aria-pressed={level === l} onClick={() => onChange(l)} className={`tap px-3 text-sm ${level === l ? "bg-accent text-accent-ink" : "bg-surface"}`}>
          {l === "file" ? "Files" : "Components"}
        </button>
      ))}
    </div>
  );
}

const subject = (i: ClaimSummary) => (i.from_symbol ?? i.claim_id).replace(/^(file|component|commit|dep|repo)::/, "");

/** Numeric metric keys present across records, in a stable order; the preferred key first when present. */
export function metricKeys(records: readonly (HistoryExtras | undefined)[], prefer: readonly string[]) {
  const ks = new Set<string>();
  for (const r of records) for (const [k, v] of Object.entries(r?.metrics ?? {})) if (typeof v === "number") ks.add(k);
  const rest = [...ks].filter((k) => !prefer.includes(k)).sort();
  return [...prefer.filter((k) => ks.has(k)), ...rest];
}

function Hotspots({ repoId, sha, onEvidence }: PanelProps) {
  const [sp, set] = useParam();
  const level = sp.get("level") === "component" ? "component" : "file";
  const q = useQuery({ queryKey: ["history", "hotspots", repoId, sha, level], queryFn: () => api.historyHotspots(repoId, sha, level) });
  const [key, setKey] = useState<string | null>(null);
  const selId = useId();
  return (
    <div className="flex flex-col gap-3">
      <LevelToggle level={level} onChange={(l) => set({ level: l === "file" ? null : l })} />
      <p className="text-sm text-ink-2">Hotspots combine how often a file changed with an indentation-based complexity proxy. This is a history pattern, not a measure of quality or of runtime behavior.</p>
      <Frame q={q} what="Hotspots" endpoint={`GET history/hotspots?level=${level}`} repoId={repoId} sha={sha}>
        {(shown, recs) => {
          const ks = metricKeys(shown.map((i) => recs.get(i.claim_id)), ["hotspot_score", "revisions", "churn", "authors"]);
          const k = key && ks.includes(key) ? key : (ks[0] ?? null);
          const bars: Bar[] = shown.map((i) => {
            const v = k ? metric(recs.get(i.claim_id), k) : null;
            return { id: i.claim_id, label: subject(i), value: v, display: v === null ? "" : v.toLocaleString("en-US", { maximumFractionDigits: 4 }) };
          });
          return (
            <>
              {ks.length > 1 ? (
                <div className="flex items-center gap-2 text-sm">
                  <label htmlFor={selId}>Chart metric</label>
                  <select id={selId} value={k ?? ""} onChange={(e) => setKey(e.target.value)} className="tap rounded-md border border-line-strong px-2">
                    {ks.map((x) => (
                      <option key={x} value={x}>
                        {x}
                      </option>
                    ))}
                  </select>
                </div>
              ) : null}
              {k ? <BarChart title={`${k} by ${level}, history pattern`} unit={k} bars={bars} /> : <p className="text-sm text-muted">The records carry no numeric metrics to chart.</p>}
              <ol className="history-spine" aria-label="Hotspot records">
                {shown.map((i) => (
                  <HistoryItem key={i.claim_id} item={i} x={recs.get(i.claim_id)} onEvidence={onEvidence} />
                ))}
              </ol>
            </>
          );
        }}
      </Frame>
    </div>
  );
}

/** "changed together in N of M commits" (history.md section 17): from the record's qualifier, or its own metrics. */
export function cochangeText(i: ClaimSummary, x: HistoryExtras | undefined): string {
  const support = metric(x, "support");
  const union = metric(x, "union_commits");
  if (support !== null && union !== null) return `changed together in ${support} of ${union} commits`;
  return i.qualifier ?? "count not reported";
}

function Cochange({ repoId, sha, onEvidence }: PanelProps) {
  const [sp, set] = useParam();
  const level = sp.get("level") === "component" ? "component" : "file";
  const target = sp.get("target") ?? "";
  const [t, setT] = useState(target);
  const tid = useId();
  const q = useQuery({ queryKey: ["history", "cochange", repoId, sha, target, level], queryFn: () => api.historyCochange(repoId, sha, { target: target || undefined, level }) });
  return (
    <div className="flex flex-col gap-3">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          set({ target: t.trim() || null });
        }}
        className="flex flex-col gap-2 rounded-lg border border-line bg-surface p-3 sm:flex-row sm:items-end"
        aria-label="Co-change filters"
      >
        <div className="flex min-w-0 flex-1 flex-col">
          <label htmlFor={tid} className="text-sm font-medium">
            Target (optional)
          </label>
          <input id={tid} value={t} onChange={(e) => setT(e.target.value)} placeholder="frontend/src/routes/items.tsx" className="tap rounded-md border border-line-strong px-2 font-mono text-sm" />
        </div>
        <Button type="submit">Apply</Button>
      </form>
      <LevelToggle level={level} onChange={(l) => set({ level: l === "file" ? null : l })} />
      <p className="text-sm text-ink-2" data-testid="cochange-caveat">
        Changing together is a history pattern. It is not evidence of a code dependency, and its absence is not evidence of independence.
      </p>
      <Frame q={q} what="Co-change" endpoint={`GET history/cochange?level=${level}${target ? `&target=${target}` : ""}`} repoId={repoId} sha={sha}>
        {(shown, recs) => {
          const bars: Bar[] = shown.map((i) => {
            const x = recs.get(i.claim_id);
            return { id: i.claim_id, label: `${subject(i)} and ${(i.to_symbol ?? "").replace(/^(file|component)::/, "")}`, value: metric(x, "degree"), display: cochangeText(i, x) };
          });
          return (
            <>
              <BarChart title="Co-change degree, history pattern" unit="Changed together" bars={bars} max={1} />
              <ol className="history-spine" aria-label="Co-change records">
                {shown.map((i) => {
                  const other = (i.to_symbol ?? "").replace(/^(file|component)::/, "");
                  return (
                    <HistoryItem
                      key={i.claim_id}
                      item={i}
                      x={recs.get(i.claim_id)}
                      onEvidence={onEvidence}
                      eyebrow={
                        <div className="history-pair">
                          <span className="history-pill">{subject(i)}</span>
                          <span className="text-xs text-muted">changed together with</span>
                          <span className="history-pill">{other || "unknown"}</span>
                        </div>
                      }
                    >
                      <p className="text-xs" data-testid="cochange-text">
                        {cochangeText(i, recs.get(i.claim_id))}. History pattern.
                      </p>
                    </HistoryItem>
                  );
                })}
              </ol>
            </>
          );
        }}
      </Frame>
    </div>
  );
}

/** The commit a milestone record names: its first citation, else a commit:: endpoint. */
export function milestoneSha(i: ClaimSummary, x: HistoryExtras | undefined): string | null {
  const c = x?.citations[0]?.commit;
  if (c && SHA40.test(c)) return c;
  const m = /^commit::([0-9a-f]{40})$/.exec(i.from_symbol ?? "");
  return m ? m[1]! : null;
}

function Milestones({ repoId, sha, onEvidence }: PanelProps) {
  const [, set] = useParam();
  const q = useQuery({ queryKey: ["history", "milestones", repoId, sha], queryFn: () => api.historyMilestones(repoId, sha) });
  return (
    <Frame q={q} what="Milestones" endpoint="GET history/milestones" repoId={repoId} sha={sha}>
      {(shown, recs) => (
        <ol className="history-spine" aria-label="Milestones in API order">
          {shown.map((i) => {
            const m = milestoneSha(i, recs.get(i.claim_id));
            return (
              <HistoryItem key={i.claim_id} item={i} x={recs.get(i.claim_id)} onEvidence={onEvidence}>
                {m ? (
                  <span className="flex flex-wrap gap-2">
                    <Button onClick={() => set({ tab: "compare", base: m })}>Compare from {shortSha(m)}</Button>
                    <Button onClick={() => set({ tab: "compare", head: m })}>Compare to {shortSha(m)}</Button>
                  </span>
                ) : null}
              </HistoryItem>
            );
          })}
        </ol>
      )}
    </Frame>
  );
}

function Compare({ repoId, sha, onEvidence }: PanelProps) {
  const [sp, set] = useParam();
  const base = sp.get("base") ?? "";
  const head = sp.get("head") ?? sha;
  const [b, setB] = useState(base);
  const [h, setH] = useState(head);
  const ids = { b: useId(), h: useId() };
  const ready = SHA40.test(base) && SHA40.test(head);
  const q = useQuery({ queryKey: ["history", "compare", repoId, base, head], queryFn: () => api.compare(repoId, base, head), enabled: ready });
  const bad = (v: string) => v !== "" && !SHA40.test(v);
  return (
    <div className="flex flex-col gap-3">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          set({ base: b.trim() || null, head: h.trim() || null });
        }}
        className="grid gap-2 rounded-lg border border-line bg-surface p-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end"
        aria-label="Compare two commits"
      >
        <div className="flex min-w-0 flex-col">
          <label htmlFor={ids.b} className="text-sm font-medium">
            Base commit (40-hex SHA)
          </label>
          <input id={ids.b} value={b} onChange={(e) => setB(e.target.value.trim())} aria-invalid={bad(b)} className="tap rounded-md border border-line-strong px-2 font-mono text-xs" />
        </div>
        <div className="flex min-w-0 flex-col">
          <label htmlFor={ids.h} className="text-sm font-medium">
            Head commit (40-hex SHA)
          </label>
          <input id={ids.h} value={h} onChange={(e) => setH(e.target.value.trim())} aria-invalid={bad(h)} className="tap rounded-md border border-line-strong px-2 font-mono text-xs" />
        </div>
        <Button type="submit" variant="primary" disabled={!SHA40.test(b) || !SHA40.test(h)}>
          Compare
        </Button>
      </form>
      <p className="text-sm text-ink-2">Pick milestones from the Milestones tab, or paste full SHAs. Only full 40-character SHAs are accepted, so every result is pinned.</p>
      {!ready ? null : (
        <Frame q={q} what="Snapshot compare" endpoint={`GET compare?base=${base}&head=${head}`} repoId={repoId} sha={sha}>
          {(shown, recs) => {
            const added = shown.filter((i) => i.kind === "snapshot_added");
            const removed = shown.filter((i) => i.kind === "snapshot_removed");
            const other = shown.filter((i) => i.kind !== "snapshot_added" && i.kind !== "snapshot_removed");
            const group = (title: string, list: ClaimSummary[], testid: string) => (
              <section aria-label={title} data-testid={testid}>
                <h3 className="mb-1 text-sm font-semibold">
                  {title} ({list.length})
                </h3>
                {list.length === 0 ? (
                  <p className="text-sm text-muted">None.</p>
                ) : (
                  <ul className="flex flex-col gap-2">
                    {list.map((i) => (
                      <HistoryItem key={i.claim_id} item={i} x={recs.get(i.claim_id)} onEvidence={onEvidence} />
                    ))}
                  </ul>
                )}
              </section>
            );
            return (
              <>
                <BarChart
                  title={`Evidence differences from ${shortSha(base)} to ${shortSha(head)}`}
                  unit="Records"
                  bars={[
                    { id: "added", label: "Present at head, absent at base", value: added.length, display: String(added.length) },
                    { id: "removed", label: "Present at base, absent at head", value: removed.length, display: String(removed.length) },
                  ]}
                />
                {group("Present at head, absent at base", added, "compare-added")}
                {group("Present at base, absent at head", removed, "compare-removed")}
                {other.length ? group("Other records", other, "compare-other") : null}
              </>
            );
          }}
        </Frame>
      )}
    </div>
  );
}

export function HistoryPage() {
  const { repoId = "", sha = "" } = useParams();
  const [sp, set] = useParam();
  const tab: TabId = (HISTORY_TABS.find((t) => t.id === sp.get("tab"))?.id ?? "timeline") as TabId;
  const claim = sp.get("claim");
  const props: PanelProps = { repoId, sha, onEvidence: (id) => set({ claim: id }) };
  return (
    <>
      <PageHeader title="History">
        How the repository changed, from Git objects at the pinned commit. Patterns such as co-change and hotspots are not proof of intent or causation, and nothing here describes runtime behavior.
      </PageHeader>
      <Tabs.Root value={tab} onValueChange={(v) => set({ tab: v === "timeline" ? null : v, offset: null })}>
        <Tabs.List aria-label="History views" className="mb-3 flex overflow-x-auto border-b border-line">
          {HISTORY_TABS.map((t) => (
            <Tabs.Trigger key={t.id} value={t.id} className="tap shrink-0 border-b-2 border-transparent px-3 text-sm data-[state=active]:border-accent data-[state=active]:font-semibold">
              {t.label}
            </Tabs.Trigger>
          ))}
        </Tabs.List>
        <Tabs.Content value="timeline">{tab === "timeline" ? <Timeline {...props} /> : null}</Tabs.Content>
        <Tabs.Content value="hotspots">{tab === "hotspots" ? <Hotspots {...props} /> : null}</Tabs.Content>
        <Tabs.Content value="cochange">{tab === "cochange" ? <Cochange {...props} /> : null}</Tabs.Content>
        <Tabs.Content value="milestones">{tab === "milestones" ? <Milestones {...props} /> : null}</Tabs.Content>
        <Tabs.Content value="compare">{tab === "compare" ? <Compare {...props} /> : null}</Tabs.Content>
      </Tabs.Root>
      <EvidenceDrawer repoId={repoId} sha={sha} claimId={claim} onClose={() => set({ claim: null })} />
    </>
  );
}
