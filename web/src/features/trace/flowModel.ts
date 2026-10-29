import type { ClaimSummary, TraceHop, TraceResponse } from "../../api/client";

/** File plus the top-level name, so `file.tsx::Widget::onSubmit` belongs to `file.tsx::Widget`. */
export function componentSymbol(symbol: string): string | null {
  const i = symbol.indexOf("::");
  if (i <= 0) return null;
  const file = symbol.slice(0, i);
  const name = symbol.slice(i + 2).split("::")[0];
  if (!name) return null;
  return `${file}::${name}`;
}

/** Prefer a complete path, then the one that keeps the most library steps. */
export function pickFlowTrace(traces: readonly TraceResponse[]): TraceResponse | null {
  const usable = traces.filter((t) => t.hops.some((h) => h.type !== "gap"));
  const pool = usable.length ? usable : traces;
  if (pool.length === 0) return null;
  const score = (t: TraceResponse) => {
    const library = t.hops.filter((h) => h.type === "library_contract").length;
    return (t.complete ? 100 : 0) + library * 10 + t.hops.length;
  };
  return [...pool].sort((a, b) => score(b) - score(a) || a.from_symbol.localeCompare(b.from_symbol))[0] ?? null;
}

/** A verified render into the component, not a render the component itself makes. */
export function incomingRender(items: readonly ClaimSummary[], component: string): ClaimSummary | null {
  const hits = items.filter((i) => i.to_symbol === component && i.from_symbol && i.from_symbol !== component && i.status !== "rejected");
  hits.sort((a, b) => Number(b.status === "verified") - Number(a.status === "verified") || a.claim_id.localeCompare(b.claim_id));
  return hits[0] ?? null;
}

/** Persistence claim on the same symbols as a hop. The hop itself may be a different kind, such as depends_on. */
export function persistenceOnHop(hop: TraceHop, claims: readonly ClaimSummary[]): ClaimSummary | null {
  return claims.find((c) => c.kind === "persistence_path" && c.from_symbol === hop.from_symbol && c.to_symbol === hop.to_symbol) ?? null;
}

export function claimOnHop(hop: TraceHop, claims: readonly ClaimSummary[], kind: string): ClaimSummary | null {
  return claims.find((c) => c.kind === kind && c.from_symbol === hop.from_symbol && c.to_symbol === hop.to_symbol) ?? null;
}

/** One sentence a reader can follow. The symbols stay on the step; this does not add a relationship the hop does not have. */
export function flowLine(kind: string, fromName: string, toName: string): string {
  switch (kind) {
    case "renders":
      return `${fromName} shows ${toName}.`;
    case "binds_handler":
      return `${fromName} connects the form to ${toName}.`;
    case "calls":
      return `${fromName} calls ${toName}.`;
    case "library_contract":
      return `A library step connects ${fromName} to ${toName}. The library source was not checked.`;
    case "implements_operation":
      return `${fromName} matches the API operation ${toName}.`;
    case "routes_to":
      return `That operation is handled by ${toName}.`;
    case "depends_on":
      return `${fromName} depends on ${toName}.`;
    case "persistence_path":
      return `${fromName} has a static persistence path through ${toName}.`;
    case "uses_model":
      return `${fromName} uses the model ${toName}.`;
    case "returns_model":
      return `${fromName} returns ${toName}.`;
    case "gap":
      return `No recorded relationship connects ${fromName} to ${toName}.`;
    default:
      return `${fromName} ${kind.replaceAll("_", " ")} ${toName}.`;
  }
}

export function flagNote(flags: readonly string[] | undefined): string | null {
  if (!flags?.length) return null;
  const bits: string[] = [];
  if (flags.includes("generated_file")) bits.push("The file is generated.");
  if (flags.includes("runtime_config_dependent")) bits.push("The match depends on runtime configuration, which was not executed.");
  return bits.length ? bits.join(" ") : null;
}
