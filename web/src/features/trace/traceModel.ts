import type { TraceHop, TraceResponse } from "../../api/client";
import { presentStatus, type StatusPresentation } from "../../status/status";

/** Plain wording for a trace gap (acceptance note O-2). It says what the evidence lacks, never whether a call happens. */
export const GAP_MEANING =
  "No static evidence that Traces accepts connects these two steps. This does not mean a call happens here, and it does not mean one never does.";

/** Rejected relationships are hidden from traces; when there are any, a gap may sit where one of them was. */
export function gapHiddenNote(hidden: Record<string, number> | null | undefined): string | null {
  const n = hidden?.rejected ?? 0;
  if (!n) return null;
  return `${n.toLocaleString("en-US")} rejected relationship${n === 1 ? " is" : "s are"} hidden from this trace, so a rejected one may touch this step. The API's note below does not count them.`;
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
    title: hop.type === "gap" ? "Gap: no static evidence connects these steps" : "Library contract step",
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
