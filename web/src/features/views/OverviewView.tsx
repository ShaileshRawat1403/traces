import * as Tabs from "@radix-ui/react-tabs";
import type { Overview } from "../../api/client";
import { FactGroups, partitionFacts, type Fact } from "../../ui/Facts";
import { Card } from "../../ui/States";

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
                <span className="block h-2 rounded bg-accent/70" style={{ width: `${(n / max) * 100}%` }} />
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
      <div className="grid gap-4 lg:grid-cols-2">
        <Lead title="Entry points" facts={data.entry_points} base={base} empty="No entry points reported." />
        <Lead title="Where to start" facts={data.start_here} base={base} empty="No starting points reported." />
      </div>
      <Tabs.Root defaultValue="business" className="rounded-lg border border-line bg-surface">
        <Tabs.List aria-label="Overview layers" className="flex border-b border-line">
          {LAYERS.map((l) => (
            <Tabs.Trigger
              key={l.key}
              value={l.key}
              className="tap min-w-0 flex-1 border-b-2 border-transparent px-1 text-sm text-ink-2 data-[state=active]:border-accent data-[state=active]:font-semibold data-[state=active]:text-accent"
            >
              {l.title}
              <span className="ml-1 hidden text-xs text-muted sm:inline">({data[l.key].length})</span>
            </Tabs.Trigger>
          ))}
        </Tabs.List>
        {LAYERS.map((l) => (
          <Tabs.Content key={l.key} value={l.key} className="p-4 focus-visible:outline-offset-[-3px]">
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
