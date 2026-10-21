import { describe, expect, it } from "vitest";
import { presentStatus, statusName } from "./status";

describe("presentStatus: allowed pairs (CONTRACTS.md 2)", () => {
  it("verified shows Verified, solid", () => {
    const p = presentStatus({ status: "verified", label: "verified" });
    expect(p).toMatchObject({ text: "Verified", tone: "verified", line: "solid", hidden: false, inconsistent: false, note: null });
  });
  it("observed shows Observed, thin, and says it is not runtime", () => {
    const p = presentStatus({ status: "observed", label: "observed" });
    expect(p).toMatchObject({ text: "Observed", tone: "observed", line: "thin", inconsistent: false });
    expect(p.description).toMatch(/Not a runtime observation/);
  });
  it("unvalidated shows Inferred, dashed", () => {
    expect(presentStatus({ status: "unvalidated", label: "inferred" })).toMatchObject({ text: "Inferred", tone: "inferred", line: "dashed", inconsistent: false });
  });
  it("missing_location shows its own label plus No source location, dotted", () => {
    const p = presentStatus({ status: "missing_location", label: "inferred", flags: ["no_source_location"] });
    expect(p).toMatchObject({ text: "Inferred", line: "dotted", note: "No source location", inconsistent: false });
  });
  it("no_source_location flag alone adds the note", () => {
    expect(presentStatus({ status: "unvalidated", label: "inferred", flags: ["no_source_location"] }).note).toBe("No source location");
  });
});

describe("presentStatus: rejected is reviewer-only", () => {
  it("is hidden in default contexts", () => {
    const p = presentStatus({ status: "rejected", label: "rejected" });
    expect(p.hidden).toBe(true);
    expect(p.line).toBe("none");
  });
  it("shows Rejected in reviewer contexts, never Inferred", () => {
    const p = presentStatus({ status: "rejected", label: "rejected" }, "reviewer");
    expect(p).toMatchObject({ hidden: false, text: "Rejected", tone: "rejected" });
  });
  it("hides a record whose label alone says rejected", () => {
    expect(presentStatus({ status: "unvalidated", label: "rejected" }).hidden).toBe(true);
  });
});

describe("presentStatus: never promotes", () => {
  it("missing_location labelled verified is flagged inconsistent and not given the verified tone", () => {
    const p = presentStatus({ status: "missing_location", label: "verified" });
    expect(p.inconsistent).toBe(true);
    expect(p.tone).toBe("unknown");
    expect(p.line).toBe("dotted");
    expect(p.note).toMatch(/does not match/);
  });
  it("unvalidated labelled verified keeps the API's word but warns", () => {
    const p = presentStatus({ status: "unvalidated", label: "verified" });
    expect(p.text).toBe("Verified");
    expect(p.tone).toBe("unknown");
    expect(p.inconsistent).toBe(true);
  });
  it("unknown values are shown raw and flagged", () => {
    const p = presentStatus({ status: "x-new", label: "x-label" });
    expect(p).toMatchObject({ text: "x-label", tone: "unknown", inconsistent: true });
  });
  it("0.3 style rejected labelled inferred is still hidden by default", () => {
    const p = presentStatus({ status: "rejected", label: "inferred" });
    expect(p.hidden).toBe(true);
    expect(p.inconsistent).toBe(true);
  });
});

describe("statusName", () => {
  it("names statuses in hidden-count summaries", () => {
    expect(statusName("unvalidated")).toBe("inferred (unvalidated)");
    expect(statusName("rejected")).toBe("rejected");
    expect(statusName("x-other")).toBe("x-other");
  });
});
