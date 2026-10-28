import * as Tabs from "@radix-ui/react-tabs";
import { Link } from "react-router-dom";
import type { Overview } from "../../api/client";
import { FactGroups, partitionFacts, type Fact } from "../../ui/Facts";
import { Card } from "../../ui/States";

const LAYER_HELP = "Three readings of the same snapshot. A fact without a citation is not treated as grounded.";

function SystemStrip({ data, base }: { data: Overview; base: string }) {
  const langs = Object.entries(data.languages).sort((a, b) => b[1] - a[1]);
  const total = langs.reduce((a, [, n]) => a + n, 0) || 1;
  const jumps = [
    { to: `${base}/graph`, label: "Graph", hint: "Components and relationships" },
    { to: `${base}/trace`, label: "Trace", hint: "One path, including gaps" },
    { to: `${base}/history`, label: "History", hint: "What Git actually changed" },
    { to: `${base}/ask`, label: "Ask", hint: "Answer from stored evidence" },
  ];
  return (
    <section className="border-t border-white/10 pt-5" aria-label="System at a glance">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-sm font-medium tracking-[-0.02em]">See the system</h2>
          <p className="mt-1 max-w-xl text-[13px] text-muted">{LAYER_HELP}</p>
        </div>
        <ul className="flex flex-wrap gap-x-4 gap-y-1">
          {jumps.map((j) => (
            <li key={j.to}>
              <Link to={j.to} className="inline-flex items-baseline gap-2 text-sm text-ink no-underline hover:no-underline" title={j.hint}>
                <span className="font-medium tracking-[-0.02em]">{j.label}</span>
                <span className="hidden text-[12px] text-muted md:inline">{j.hint}</span>
              </Link>
            </li>
          ))}
        </ul>
      </div>
      {langs.length > 0 ? (
        <div className="mt-4" role="img" aria-label={`Languages by file count: ${langs.map(([k, n]) => `${k} ${n}`).join(", ")}`}>
          <div className="flex h-3 overflow-hidden rounded-full bg-sunken">
            {langs.map(([k, n], i) => (
              <span key={k} className="h-3" style={{ width: `${(n / total) * 100}%`, background: LANG_COLORS[i % LANG_COLORS.length] }} />
            ))}
          </div>
          <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-ink-2">
            {langs.map(([k, n], i) => (
              <li key={k} className="inline-flex items-center gap-1">
                <span className="inline-block h-2 w-2 rounded-full" style={{ background: LANG_COLORS[i % LANG_COLORS.length] }} aria-hidden="true" />
                {k}
                <span className="tabular-nums text-muted">{n.toLocaleString("en-US")}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="mt-3 text-sm text-muted">No language counts were stored for this snapshot.</p>
      )}
    </section>
  );
}

const LANG_COLORS = ["#2fafa4", "#7eb6ff", "#e2b16a", "#c4b4ea", "#ef8d86", "#b7c4ce"];

function Lead({ title, facts, base, empty }: { title: string; facts: readonly Fact[]; base: string; empty: string }) {
  const p = partitionFacts(facts);
  return (
    <Card className="flex flex-col gap-2">
      <h2 className="font-semibold">{title}</h2>
      <FactGroups facts={[...p.grounded, ...p.interpretation, ...p.unknown]} base={base} emptyText={empty} />
    </Card>
  );
}

function NumberList({ title, data, unit }: { title: string; data: Record<string, number>; unit: string }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...entries.map(([, n]) => n));
  return (
    <div role="group" aria-label={title}>
      <h3 className="mb-2 text-sm font-semibold">{title}</h3>
      {entries.length === 0 ? (
        <p className="text-sm text-muted">None reported.</p>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {entries.map(([k, n]) => (
            <li key={k} className="grid grid-cols-[minmax(6rem,10rem)_1fr_auto] items-center gap-2 text-sm">
              <span className="truncate" title={k}>
                {k}
              </span>
              <span className="h-2 rounded bg-sunken" aria-hidden="true">
                <span className="block h-1.5 rounded-full bg-ink/80" style={{ width: `${(n / max) * 100}%` }} />
              </span>
              <span className="tabular-nums text-ink-2">
                {n.toLocaleString("en-US")}
                <span className="sr-only"> {unit}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const LAYERS = [
  { key: "business", title: "Business", help: "Capabilities and user flows." },
  { key: "architecture", title: "Architecture", help: "Major components and how they connect." },
  { key: "implementation", title: "Implementation", help: "Languages, files, dependencies and evidence." },
] as const;

/** Pure renderer for GET .../overview (openapi Overview). Facts, interpretations and unknowns are always kept apart. */
export function OverviewView({ data, base }: { data: Overview; base: string }) {
  return (
    <div className="flex flex-col gap-4" data-testid="overview">
      <SystemStrip data={data} base={base} />
      <div className="grid gap-4 lg:grid-cols-2">
        <Lead title="Entry points" facts={data.entry_points} base={base} empty="No entry points reported." />
        <Lead title="Where to start" facts={data.start_here} base={base} empty="No starting points reported." />
      </div>
      <Tabs.Root defaultValue="business" className="border-t border-white/10">
        <Tabs.List aria-label="Overview layers" className="flex">
          {LAYERS.map((l) => (
            <Tabs.Trigger
              key={l.key}
              value={l.key}
              className="min-h-11 min-w-0 flex-1 border-b border-transparent px-1 text-sm text-muted data-[state=active]:border-ink data-[state=active]:font-medium data-[state=active]:text-ink"
            >
              {l.title}
              <span className="ml-1 hidden text-xs text-muted sm:inline">({data[l.key].length})</span>
            </Tabs.Trigger>
          ))}
        </Tabs.List>
        {LAYERS.map((l) => (
          <Tabs.Content key={l.key} value={l.key} className="py-4 focus-visible:outline-offset-[-3px]">
            <p className="mb-3 text-sm text-muted">{l.help}</p>
            <FactGroups facts={data[l.key]} base={base} emptyText={`No ${l.title.toLowerCase()} facts reported for this snapshot.`} />
            {l.key === "implementation" ? (
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <NumberList title="Languages" data={data.languages} unit="files" />
                <NumberList title="Counts" data={data.counts} unit="" />
              </div>
            ) : null}
          </Tabs.Content>
        ))}
      </Tabs.Root>
    </div>
  );
}
