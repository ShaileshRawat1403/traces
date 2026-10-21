import { describe, expect, it } from "vitest";
import type { Schemas } from "../../api/client";
import { traceSample } from "../../testing/samples";
import { orderedHops, presentHop, traceSummary } from "./traceModel";

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
});
