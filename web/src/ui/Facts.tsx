import { Link } from "react-router-dom";
import type { Schemas } from "../api/client";

export type Fact = Schemas["OverviewFact"];
export type FactKind = Fact["kind"];

/** Grounded facts must cite at least one claim; a "fact" without citations is shown as unsupported, never as grounded. */
export function factStanding(f: Fact): "grounded" | "uncited" | "interpretation" | "unknown" {
  if (f.kind === "fact") return (f.claim_ids ?? []).length > 0 ? "grounded" : "uncited";
  return f.kind;
}

/** Splits facts into the three bands the UI always keeps apart. */
export function partitionFacts(facts: readonly Fact[]) {
  const grounded: Fact[] = [];
  const interpretation: Fact[] = [];
  const unknown: Fact[] = [];
  for (const f of facts) {
    const s = factStanding(f);
    if (s === "grounded") grounded.push(f);
    else if (s === "interpretation") interpretation.push(f);
    else unknown.push(f); // unknown and uncited facts
  }
  return { grounded, interpretation, unknown };
}

const STANDING = {
  grounded: { text: "Grounded", cls: "border-verified/40 bg-verified-soft text-verified", help: "Stated by cited evidence records." },
  uncited: { text: "Unsupported", cls: "border-unknown/40 bg-unknown-soft text-unknown", help: "Marked as a fact but carries no citation, so it is not treated as grounded." },
  interpretation: { text: "Interpretation", cls: "border-inferred/50 border-dashed bg-inferred-soft text-inferred", help: "A reading of the evidence, not a verified fact." },
  unknown: { text: "Unknown", cls: "border-line-strong bg-sunken text-ink-2", help: "Traces could not determine this from code or documentation." },
} as const;

export function StandingChip({ fact }: { fact: Fact }) {
  const s = STANDING[factStanding(fact)];
  return (
    <span className={`inline-flex items-center rounded-sm border px-1.5 py-0.5 text-xs font-semibold leading-none ${s.cls}`} title={s.help} data-testid="fact-standing">
      {s.text}
      <span className="sr-only">. {s.help}</span>
    </span>
  );
}

export function CitationLinks({ claimIds, base }: { claimIds: readonly string[]; base: string }) {
  if (claimIds.length === 0) return null;
  return (
    <span className="inline-flex flex-wrap gap-1" aria-label={`${claimIds.length} citations`}>
      {claimIds.map((id, i) => (
        <Link
          key={id}
          to={`${base}/claim/${id}`}
          className="tap-sm inline-flex items-center rounded-sm border border-line bg-surface px-1.5 font-mono text-xs no-underline hover:border-accent"
          aria-label={`Citation ${i + 1}: claim ${id.slice(0, 10)}`}
          data-testid="citation"
        >
          [{i + 1}]
        </Link>
      ))}
    </span>
  );
}

export function FactItem({ fact, base }: { fact: Fact; base: string }) {
  const standing = factStanding(fact);
  return (
    <li className="flex flex-col gap-1 rounded-md border border-line bg-surface p-3" data-standing={standing} data-testid="fact">
      <div className="flex flex-wrap items-center gap-2">
        <StandingChip fact={fact} />
        <CitationLinks claimIds={fact.claim_ids ?? []} base={base} />
      </div>
      <p className={`break-words ${standing === "interpretation" ? "italic text-ink-2" : ""}`}>{fact.text}</p>
    </li>
  );
}

/** Grounded facts, interpretations and unknowns in separate, labelled groups. */
export function FactGroups({ facts, base, emptyText }: { facts: readonly Fact[]; base: string; emptyText: string }) {
  const { grounded, interpretation, unknown } = partitionFacts(facts);
  if (facts.length === 0) return <p className="text-sm text-muted">{emptyText}</p>;
  const group = (title: string, items: Fact[], note: string) =>
    items.length ? (
      <div role="group" className="flex flex-col gap-2" aria-label={title}>
        <h3 className="text-sm font-semibold">
          {title} <span className="font-normal text-muted">({items.length})</span>
        </h3>
        <p className="-mt-1 text-xs text-muted">{note}</p>
        <ul className="flex flex-col gap-2">
          {items.map((f, i) => (
            <FactItem key={i} fact={f} base={base} />
          ))}
        </ul>
      </div>
    ) : null;
  return (
    <div className="flex flex-col gap-4">
      {group("Grounded in evidence", grounded, "Each statement cites the evidence records it rests on.")}
      {group("Interpretation", interpretation, "Readings of the evidence. Useful orientation, not verified facts.")}
      {group("Unknown or unsupported", unknown, "Not established from code or documentation.")}
    </div>
  );
}
