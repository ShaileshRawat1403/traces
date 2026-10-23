import { describe, expect, it } from "vitest";
import { readRecord, splitSymbol } from "./record";

describe("readRecord", () => {
  it("reads the fields the evidence page uses and ignores malformed entries", () => {
    const r = readRecord({
      claim_id: "c_1",
      statement: "A renders B",
      status: "verified",
      label: "verified",
      claim_kind: "relationship",
      relationship_kind: "renders",
      locations: [{ file: "a.tsx", start_line: 3, end_line: 4, role: "site" }, { file: "bad" }],
      checks: [{ check_id: "k_1", method: "syntax_structure", result: "pass", independent: true, validator: { family: "typescript-compiler" } }, { nope: 1 }],
      status_history: [{ from: null, to: "unvalidated" }, { from: "unvalidated", to: "verified" }],
      flags: ["generated_file", 3],
    });
    expect(r.kind).toBe("renders");
    expect(r.locations).toHaveLength(1);
    expect(r.checks).toHaveLength(1);
    expect(r.status_history.map((h) => h.to)).toEqual(["unvalidated", "verified"]);
    expect(r.flags).toEqual(["generated_file"]);
  });
  it("rejects records without claim_id", () => {
    expect(() => readRecord({})).toThrow();
    expect(() => readRecord(null)).toThrow();
  });
});

describe("splitSymbol", () => {
  it("splits file and name, and names file-level symbols by basename", () => {
    expect(splitSymbol("frontend/a/Items.tsx::Items")).toEqual({ file: "frontend/a/Items.tsx", name: "Items" });
    expect(splitSymbol("backend/x.py::backend/x.py")).toEqual({ file: "backend/x.py", name: "x.py" });
    expect(splitSymbol("plain")).toEqual({ file: null, name: "plain" });
  });
});
