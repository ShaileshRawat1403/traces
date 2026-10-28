import { describe, expect, it } from "vitest";
import { COMPONENT_IDS, componentsSample, graphComponentsSample, graphSymbolsSample } from "../../testing/samples";
import { componentForFile, componentRollup, columnLayout, countsFor, depthLayout, drawableEdges, fileRollup, graphQuery, nextGraphLimit, nextInDirection, openingDiagram, readGraphState, symbolsInFile, toElements, writeGraphState } from "./graphModel";

describe("graph URL state and query", () => {
  it("defaults to verified and observed, depth 1, no focus", () => {
    const s = readGraphState(new URLSearchParams());
    expect(s.status).toEqual(["verified", "observed"]);
    expect(s.depth).toBe(1);
    expect(s.focus).toBeNull();
    const q = new URLSearchParams(graphQuery(s).slice(1));
    expect(q.getAll("status")).toEqual(["verified", "observed"]);
    expect(q.has("focus")).toBe(false);
    expect(q.has("depth")).toBe(false);
    expect(q.has("include_rejected")).toBe(false);
  });
  it("never requests rejected, even from a hand-written URL", () => {
    const s = readGraphState(new URLSearchParams("status=rejected&status=verified&include_rejected=true"));
    expect(s.status).toEqual(["verified"]);
    expect(graphQuery(s)).not.toContain("rejected");
  });
  it("round-trips through the URL, keeps view and claim, and distinguishes an empty status selection", () => {
    const s = { focus: "a.ts::A", depth: 3, layer: ["frontend", "api"], rel: ["renders"], status: [] as never[], q: "task", limit: 300 };
    const keep = new URLSearchParams("view=list&claim=c_1&junk=1");
    const sp = writeGraphState(s, keep);
    expect(sp.get("view")).toBe("list");
    expect(sp.get("claim")).toBe("c_1");
    expect(sp.has("junk")).toBe(false);
    expect(readGraphState(sp)).toEqual(s);
    const q = new URLSearchParams(graphQuery(s).slice(1));
    expect(q.getAll("layer")).toEqual(["frontend", "api"]);
    expect(q.get("depth")).toBe("3");
  });
  it("raises the page cap without passing the API maximum", () => {
    expect(nextGraphLimit(300)).toBe(800);
    expect(nextGraphLimit(800)).toBe(2000);
    expect(nextGraphLimit(2000)).toBeNull();
    expect(readGraphState(new URLSearchParams("limit=9000")).limit).toBe(2000);
    expect(graphQuery(readGraphState(new URLSearchParams("limit=800")))).toContain("limit=800");
  });
  it("clamps depth to the contract range", () => {
    expect(readGraphState(new URLSearchParams("depth=9")).depth).toBe(4);
    expect(readGraphState(new URLSearchParams("depth=-2")).depth).toBe(0);
    expect(readGraphState(new URLSearchParams("depth=x")).depth).toBe(1);
  });
});

describe("compound grouping", () => {
  it("picks the longest path prefix and ignores partial name matches", () => {
    const nested = [...componentsSample, { ...componentsSample[0]!, id: "cmp_nested", paths: ["web/src/widgets"] }];
    expect(componentForFile("web/src/widgets/x.tsx", nested)?.id).toBe("cmp_nested");
    expect(componentForFile("web/src/a.tsx", nested)?.id).toBe(COMPONENT_IDS.web);
    expect(componentForFile("api2/a.py", nested)).toBeNull();
    expect(componentForFile(null, nested)).toBeNull();
  });
  it("nests symbols under component nodes only when the component is in the response", () => {
    const merged = { ...graphSymbolsSample, nodes: [...graphComponentsSample.nodes.slice(0, 1), ...graphSymbolsSample.nodes] };
    const els = toElements(merged, componentsSample);
    const web = els.find((e) => e.data.id.endsWith("::TaskList"));
    const api = els.find((e) => e.data.id.endsWith("::list_tasks"));
    expect(web?.data.parent).toBe(COMPONENT_IDS.web);
    expect(api?.data.parent).toBeUndefined();
  });
  it("never draws rejected edges and styles inferred as dashed", () => {
    const els = toElements(graphSymbolsSample, componentsSample);
    const edges = els.filter((e) => e.data.source);
    expect(edges.map((e) => e.data.id)).not.toContain(graphSymbolsSample.edges.find((e) => e.status === "rejected")!.id);
    const inferred = edges.find((e) => e.data.id === graphSymbolsSample.edges.find((x) => x.status === "unvalidated")!.id);
    expect(inferred?.data.line).toBe("dashed");
    expect(drawableEdges(graphSymbolsSample).hidden).toEqual({ rejected: 1 });
  });
  it("reads component counts by id", () => {
    expect(countsFor(COMPONENT_IDS.api, componentsSample)).toEqual(componentsSample[1]!.claim_counts);
    expect(countsFor("nope", componentsSample)).toBeNull();
  });
  it("rolls cross-component edges up and hides rejected and same-component edges", () => {
    const edges = componentRollup(graphSymbolsSample, componentsSample);
    expect(edges).toHaveLength(1);
    expect(edges[0]!.data.source).toBe(COMPONENT_IDS.web);
    expect(edges[0]!.data.target).toBe(COMPONENT_IDS.api);
    expect(edges[0]!.data.line).toBe("dashed");
    expect(edges[0]!.data.label).toContain("http call");
    expect(edges[0]!.data.id.startsWith("rollup::")).toBe(true);
  });
  it("counts a component-to-component edge once, at its own status", () => {
    const edges = componentRollup(graphComponentsSample, componentsSample);
    expect(edges).toHaveLength(1);
    expect(edges[0]!.data.line).toBe("thin");
    expect(edges[0]!.data.label).toBe("1 calls");
  });
  it("draws every stored component on the opening diagram", () => {
    const els = openingDiagram(componentsSample, graphSymbolsSample);
    expect(els.filter((e) => !e.data.source).map((e) => e.data.id).sort()).toEqual([COMPONENT_IDS.api, COMPONENT_IDS.web].sort());
    expect(els.some((e) => String(e.data.id).startsWith("rollup::"))).toBe(true);
    const fallback = openingDiagram([], graphComponentsSample);
    expect(fallback.filter((e) => !e.data.source).map((e) => e.data.id).sort()).toEqual([COMPONENT_IDS.api, COMPONENT_IDS.web].sort());
  });
});

describe("keyboard navigation", () => {
  const grid = [
    { id: "a", x: 0, y: 0 },
    { id: "b", x: 100, y: 10 },
    { id: "c", x: 0, y: 100 },
    { id: "d", x: 100, y: 100 },
    { id: "far", x: 400, y: -5 },
  ];
  it("starts top-left without a selection", () => expect(nextInDirection(grid, null, "right")).toBe("a"));
  it("moves to the nearest aligned node", () => {
    expect(nextInDirection(grid, "a", "right")).toBe("b");
    expect(nextInDirection(grid, "a", "down")).toBe("c");
    expect(nextInDirection(grid, "d", "up")).toBe("b");
    expect(nextInDirection(grid, "d", "left")).toBe("c");
  });
  it("returns null at an edge", () => {
    expect(nextInDirection(grid, "a", "left")).toBeNull();
    expect(nextInDirection([], "a", "left")).toBeNull();
  });
});

describe("column and depth layout", () => {
  it("puts the frontend column to the left of the api column, on the same row when each has one node", () => {
    const pos = columnLayout(
      [
        { id: "web", label: "web", layer: "frontend" },
        { id: "api", label: "api", layer: "api" },
      ],
      [{ source: "web", target: "api" }],
    );
    expect(pos.web!.x).toBeLessThan(pos.api!.x);
    expect(pos.web!.y).toBe(pos.api!.y);
  });

  it("wraps a tall layer into a second column and keeps support layers below the primary row", () => {
    const nodes = Array.from({ length: 7 }, (_, i) => ({ id: `f${i}`, label: `f${i}`, layer: "frontend" }));
    nodes.push({ id: "docs", label: "docs", layer: "docs" });
    const pos = columnLayout(nodes, []);
    expect(pos.f0!.x).toBeLessThan(pos.f6!.x);
    expect(pos.docs!.y).toBeGreaterThan(pos.f0!.y);
  });

  it("orders a column so a node sits nearer the neighbor it records", () => {
    const pos = columnLayout(
      [
        { id: "top", label: "a", layer: "frontend" },
        { id: "bottom", label: "b", layer: "frontend" },
        { id: "api-a", label: "a", layer: "api" },
        { id: "api-b", label: "b", layer: "api" },
      ],
      [
        { source: "bottom", target: "api-a" },
        { source: "top", target: "api-b" },
      ],
    );
    expect(pos.bottom!.y).toBeLessThan(pos.top!.y);
    expect(pos["api-a"]!.y).toBeLessThan(pos["api-b"]!.y);
  });

  it("places a caller to the left of the symbol it records a call to", () => {
    const pos = depthLayout(
      [
        { id: "caller", label: "caller" },
        { id: "callee", label: "callee" },
      ],
      [{ source: "caller", target: "callee" }],
    );
    expect(pos.caller!.x).toBeLessThan(pos.callee!.x);
  });
});

describe("file rollup", () => {
  it("counts edges between files and drops same-file edges and rejected ones already removed", () => {
    const els = [
      { data: { id: "a", label: "A", entity: "symbol", file: "web/a.tsx", layer: "frontend", tone: undefined } },
      { data: { id: "b", label: "B", entity: "symbol", file: "web/a.tsx", layer: "frontend" } },
      { data: { id: "c", label: "C", entity: "symbol", file: "api/c.py", layer: "api" } },
      { data: { id: "e1", label: "renders", source: "a", target: "b", tone: "verified", line: "solid" } },
      { data: { id: "e2", label: "calls", source: "a", target: "c", tone: "inferred", line: "dashed" } },
    ];
    const rolled = fileRollup(els);
    const files = rolled.filter((e) => !e.data.source);
    expect(files.map((f) => f.data.file).sort()).toEqual(["api/c.py", "web/a.tsx"]);
    expect(files.find((f) => f.data.file === "web/a.tsx")?.data.count).toBe(2);
    const edges = rolled.filter((e) => e.data.source);
    expect(edges).toHaveLength(1);
    expect(edges[0]!.data.line).toBe("dashed");
    expect(edges[0]!.data.label).toBe("1");
    const open = symbolsInFile(els, "web/a.tsx");
    expect(open.filter((e) => !e.data.source).map((e) => e.data.id).sort()).toEqual(["a", "b", "c"]);
    expect(open.filter((e) => e.data.source)).toHaveLength(2);
  });

  it("leaves a graph alone when each symbol already has its own file", () => {
    const els = toElements(graphSymbolsSample, componentsSample);
    expect(fileRollup(els)).toHaveLength(els.length);
  });
});
