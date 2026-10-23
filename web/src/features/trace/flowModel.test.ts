import { describe, expect, it } from "vitest";
import type { ClaimSummary, TraceResponse } from "../../api/client";
import { componentSymbol, flagNote, flowLine, incomingRender, persistenceOnHop, pickFlowTrace } from "./flowModel";

const hop = (type: TraceResponse["hops"][number]["type"], kind: string, from: string, to: string): TraceResponse["hops"][number] => ({
  index: 0,
  type,
  kind,
  from_symbol: from,
  to_symbol: to,
  status: type === "edge" ? "verified" : "unvalidated",
  label: type === "edge" ? "verified" : "inferred",
  evidence_scope: "static",
});

const trace = (from: string, hops: TraceResponse["hops"], complete: boolean): TraceResponse => ({
  snapshot_id: "s",
  from_symbol: from,
  to_symbol: "end",
  hops,
  hidden_counts: {},
  complete,
  disclaimer: "Static analysis only. No runtime behavior has been observed.",
});

const claim = (partial: Partial<ClaimSummary> & Pick<ClaimSummary, "claim_id" | "from_symbol" | "to_symbol" | "kind">): ClaimSummary => ({
  claim_kind: "relationship",
  class: "statically_derived",
  evidence_scope: "static",
  flags: [],
  label: "verified",
  statement: "s",
  status: "verified",
  ...partial,
});

describe("flow model", () => {
  it("keeps the complete path that still shows library steps", () => {
    const short = trace("a", [hop("edge", "calls", "a", "b")], true);
    const story = trace("form", [hop("library_contract", "library_contract", "form", "onSubmit"), hop("edge", "calls", "onSubmit", "db")], true);
    const gapped = trace("x", [hop("gap", "gap", "x", "db")], false);
    expect(pickFlowTrace([short, gapped, story])?.from_symbol).toBe("form");
    expect(pickFlowTrace([])).toBeNull();
    expect(pickFlowTrace([gapped])?.from_symbol).toBe("x");
  });

  it("reads the component that owns a nested symbol", () => {
    expect(componentSymbol("frontend/src/AddItem.tsx::AddItem::onSubmit")).toBe("frontend/src/AddItem.tsx::AddItem");
    expect(componentSymbol("nope")).toBeNull();
  });

  it("picks the render into the component, not the ones it makes", () => {
    const items = [
      claim({ claim_id: "c2", kind: "renders", from_symbol: "page.tsx::Items", to_symbol: "AddItem.tsx::AddItem" }),
      claim({ claim_id: "c1", kind: "renders", from_symbol: "AddItem.tsx::AddItem", to_symbol: "button.tsx::Button" }),
    ];
    expect(incomingRender(items, "AddItem.tsx::AddItem")?.claim_id).toBe("c2");
    expect(incomingRender(items, "missing")).toBeNull();
  });

  it("attaches a persistence claim only when the symbols match the hop", () => {
    const h = hop("edge", "depends_on", "items.py::create_item", "deps.py::get_db");
    const yes = claim({ claim_id: "p", kind: "persistence_path", from_symbol: h.from_symbol, to_symbol: h.to_symbol, statement: "session_commit" });
    const no = claim({ claim_id: "q", kind: "persistence_path", from_symbol: "other", to_symbol: h.to_symbol });
    expect(persistenceOnHop(h, [no, yes])?.claim_id).toBe("p");
    expect(flowLine("depends_on", "create_item", "get_db")).toBe("create_item depends on get_db.");
    expect(flowLine("library_contract", "handleSubmit", "onSubmit")).toContain("library source was not checked");
    expect(flagNote(["generated_file", "runtime_config_dependent"])).toContain("generated");
    expect(flagNote(["runtime_config_dependent"])).toContain("not executed");
    expect(flagNote([])).toBeNull();
  });
});
