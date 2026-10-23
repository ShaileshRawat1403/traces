import type { TraceHop, TraceResponse } from "../../api/client";
import { presentStatus, type StatusPresentation } from "../../status/status";

/** Plain wording for a trace gap (acceptance note O-2). It says what the evidence lacks, never whether a call happens. */
export const GAP_MEANING =
  "No static evidence that Traces accepts connects these two steps. This does not mean a call happens here, and it does not mean one never does.";

/** F-9: a gap the API adds when a step's outgoing calls are stored only as unresolved references (traces without `to`). */
export const UNRESOLVED_MEANING =
  "The extractor recorded these calls by name only and did not resolve them to a declaration, so the trace cannot follow them. They may lead to other code. This is not evidence that they do or do not.";

export function unresolvedCalls(hop: Pick<TraceHop, "type" | "unresolved_calls">): string[] | null {
  return hop.type === "gap" && Array.isArray(hop.unresolved_calls) && hop.unresolved_calls.length > 0 ? hop.unresolved_calls : null;
}

const STRONG = new Set(["verified", "observed"]);

/**
 * Why the trace is incomplete, in plain words (F-9). Gaps and edge steps that are not verified or observed both make a
 * trace incomplete. Counts come from the hops themselves; the API's incomplete_reasons are shown as given alongside.
 */
export function incompleteText(t: Pick<TraceResponse, "hops">): string {
  const gaps = t.hops.filter((h) => h.type === "gap");
  const unresolved = gaps.filter((h) => unresolvedCalls(h)).length;
  const weak = t.hops.filter((h) => h.type === "edge" && !STRONG.has(String(h.status))).length;
  const parts: string[] = [];
  if (gaps.length) {
    const plain = gaps.length - unresolved;
    const bits = [
      plain ? `${plain} gap${plain === 1 ? "" : "s"} where no accepted static evidence connects two steps` : "",
      unresolved ? `${unresolved} step${unresolved === 1 ? "" : "s"} with calls the trace cannot follow` : "",
    ].filter(Boolean);
    parts.push(`this trace has ${bits.join(" and ")}. A gap is not evidence that a call does or does not happen.`);
  }
  if (weak) parts.push(`${weak} step${weak === 1 ? " rests" : "s rest"} on a relationship that is not verified or observed.`);
  if (!parts.length) return "Incomplete: the API marks this trace incomplete.";
  const [first, ...rest] = parts;
  const head = first!.startsWith("this") ? first! : first!.charAt(0).toUpperCase() + first!.slice(1);
  return ["Incomplete: " + head, ...rest].join(" ");
}

/** Rejected relationships are hidden from traces; when there are any, a gap may sit where one of them was. */
export function gapHiddenNote(hidden: Record<string, number> | null | undefined): string | null {
  const n = hidden?.rejected ?? 0;
  if (!n) return null;
  return `${n.toLocaleString("en-US")} rejected relationship${n === 1 ? " is" : "s are"} hidden from this trace, so a rejected one may touch this step. The API's note below does not count them.`;
}

/** The per-step hidden count the API gives on a gap hop (hidden_rejected), or null when it gives none. */
export function stepHiddenRejected(hop: Pick<TraceHop, "type" | "hidden_rejected">): number | null {
  return hop.type === "gap" && typeof hop.hidden_rejected === "number" && hop.hidden_rejected >= 0 ? hop.hidden_rejected : null;
}

export function stepHiddenText(n: number): string {
  return `${n.toLocaleString("en-US")} rejected claim${n === 1 ? "" : "s"} hidden here.`;
}

export type HopKind = "edge" | "gap" | "library_contract" | "hidden";

export interface HopView {
  hop: TraceHop;
  kind: HopKind;
  /** Status presentation; gap and library_contract hops always read as Inferred (CONTRACTS.md, TraceHop.reason). */
  status: StatusPresentation;
  /** Plain-language name of the hop type. */
  title: string;
  reason: string | null;
  /** The contract requires a reason for gap and library_contract hops; the UI says so when the API omits it. */
  reasonMissing: boolean;
  /** True when the API labelled a gap or library_contract hop as something other than inferred. */
  labelMismatch: boolean;
  claimId: string | null;
}

const INFERRED_FALLBACK = { status: "unvalidated", label: "inferred" } as const;

export function presentHop(hop: TraceHop): HopView {
  const reason = hop.reason?.trim() ? hop.reason.trim() : null;
  if (hop.type === "edge") {
    const status = presentStatus({ status: hop.status, label: hop.label });
    return {
      hop,
      kind: status.hidden ? "hidden" : "edge",
      status,
      title: "Relationship",
      reason,
      reasonMissing: false,
      labelMismatch: false,
      claimId: hop.claim_id ?? null,
    };
  }
  // gap or library_contract: shown as Inferred whatever the API says, with the mismatch made visible.
  const labelMismatch = hop.label !== "inferred";
  const status = presentStatus(hop.status && !labelMismatch ? { status: hop.status, label: hop.label } : INFERRED_FALLBACK);
  return {
    hop,
    kind: hop.type,
    status,
    title: hop.type === "gap" ? (unresolvedCalls(hop) ? "Gap: calls the trace cannot follow" : "Gap: no static evidence connects these steps") : "Library contract step",
    reason,
    reasonMissing: reason === null,
    labelMismatch,
    claimId: hop.type === "gap" ? null : (hop.claim_id ?? null),
  };
}

/** Hops in their index order (the API's order is the contract; sorting guards against an unordered array). */
export function orderedHops(t: Pick<TraceResponse, "hops">): HopView[] {
  return [...t.hops].sort((a, b) => a.index - b.index).map(presentHop);
}

export function traceSummary(t: TraceResponse) {
  const hops = orderedHops(t);
  const count = (k: HopKind) => hops.filter((h) => h.kind === k).length;
  return { total: hops.length, edges: count("edge"), gaps: count("gap"), library: count("library_contract"), hidden: count("hidden") };
}
