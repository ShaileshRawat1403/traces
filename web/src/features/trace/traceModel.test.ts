import { describe, expect, it } from "vitest";
import type { Schemas } from "../../api/client";
import { traceSample } from "../../testing/samples";
import { incompleteText, orderedHops, presentHop, traceSummary, unresolvedCalls } from "./traceModel";

const base = traceSample.hops.find((h) => h.type === "gap")!;

describe("trace model", () => {
  it("orders hops by index", () => {
    expect(orderedHops(traceSample).map((v) => v.hop.index)).toEqual([0, 1, 2, 3, 4]);
  });
  it("summarizes by hop type", () => {
    expect(traceSummary(traceSample)).toEqual({ total: 5, edges: 3, gaps: 1, library: 1, hidden: 0 });
  });
  it("shows gaps as inferred with their reason and no evidence link", () => {
    const v = presentHop(base);
    expect(v.kind).toBe("gap");
    expect(v.status.text).toBe("Inferred");
    expect(v.reason).toMatch(/No recorded relationship/);
    expect(v.claimId).toBeNull();
  });
  it("keeps library contract hops inferred and linked to their claim", () => {
    const lib = traceSample.hops.find((h) => h.type === "library_contract")!;
    const v = presentHop(lib);
    expect(v.status.text).toBe("Inferred");
    expect(v.claimId).toBe(lib.claim_id);
    expect(v.reasonMissing).toBe(false);
  });
  it("flags a missing reason and a non-inferred label instead of trusting them", () => {
    const bad: Schemas["TraceHop"] = { ...base, reason: "  ", label: "verified", status: "verified" };
    const v = presentHop(bad);
    expect(v.reasonMissing).toBe(true);
    expect(v.labelMismatch).toBe(true);
    expect(v.status.text).toBe("Inferred");
  });
  it("hides rejected edge hops in place", () => {
    const rejected: Schemas["TraceHop"] = { ...traceSample.hops[1]!, status: "rejected", label: "rejected" };
    expect(presentHop(rejected).kind).toBe("hidden");
  });

  it("F-9: names gaps and weak steps separately when saying why a trace is incomplete", () => {
    expect(incompleteText(traceSample)).toBe(
      "Incomplete: this trace has 1 gap where no accepted static evidence connects two steps. A gap is not evidence that a call does or does not happen. 1 step rests on a relationship that is not verified or observed.",
    );
    const weakOnly = { hops: traceSample.hops.filter((h) => h.type !== "gap") };
    expect(incompleteText(weakOnly)).toBe("Incomplete: 1 step rests on a relationship that is not verified or observed.");
    expect(incompleteText({ hops: [] })).toBe("Incomplete: the API marks this trace incomplete.");
  });
  it("F-9: an unresolved-calls gap gets its own title and lists the call names", () => {
    const u = { ...base, to_symbol: "(unresolved)", unresolved_calls: ["mutation.mutate", "reset"] };
    expect(unresolvedCalls(u)).toEqual(["mutation.mutate", "reset"]);
    expect(unresolvedCalls(base)).toBeNull();
    expect(unresolvedCalls({ ...base, unresolved_calls: [] })).toBeNull();
    expect(presentHop(u).title).toBe("Gap: calls the trace cannot follow");
    expect(presentHop(base).title).toBe("Gap: no static evidence connects these steps");
    expect(incompleteText({ hops: [u] })).toBe(
      "Incomplete: this trace has 1 step with calls the trace cannot follow. A gap is not evidence that a call does or does not happen.",
    );
  });
});
