import { describe, expect, it } from "vitest";
import { recordedQuestion } from "../ask/recordedQuestion";
import { findInSnapshot } from "./find";
import { decodeSubject } from "../subject/subject";

function at(href: string) {
  return decodeSubject(new URL(href, "http://local").searchParams.get("at"));
}

const base = "/r/repo/s/abc";
const components = [
  { id: "component::frontend/src", name: "frontend/src", layer: "frontend", paths: ["frontend/src/main.tsx", "frontend/src/routes"] },
  { id: "component::backend/app", name: "backend/app", layer: "backend", paths: ["backend/app/api/routes/items.py"] },
];
const routes = [
  { method: "POST", path: "/api/v1/items/", file: "backend/app/api/routes/items.py", line: 20, handler_symbol: "backend/app/api/routes/items.py::create_item" },
  { method: "USE", path: "/api", file: "backend/app/main.py", line: 4, handler_symbol: null },
];

describe("recordedQuestion", () => {
  it("asks a symbol what it depends on and a file what changes with it", () => {
    expect(recordedQuestion("create_item")).toBe("What does create_item depend on?");
    expect(recordedQuestion("backend/app/api/routes/items.py::create_item")).toBe("What does backend/app/api/routes/items.py::create_item depend on?");
    expect(recordedQuestion("backend/app/api/routes/items.py")).toBe("Which files changed together with backend/app/api/routes/items.py?");
  });

  it("does not invent a question for a directory or a component id", () => {
    expect(recordedQuestion("frontend/src")).toBeNull();
    expect(recordedQuestion("component::frontend/src")).toBeNull();
  });
});

describe("findInSnapshot", () => {
  it("returns nothing until there are two characters", () => {
    expect(findInSnapshot("a", components, routes, base)).toEqual([]);
  });

  it("opens a component on the map, a file in source, and a route as a question", () => {
    const hits = findInSnapshot("items", components, routes, base);
    expect(hits.find((h) => h.kind === "route")?.href.startsWith(`${base}/ask?q=${encodeURIComponent("What does POST /api/v1/items/ do?")}`)).toBe(true);
    expect(at(hits.find((h) => h.kind === "route")!.href)?.kind).toBe("route");
    expect(hits.find((h) => h.kind === "file")?.href.startsWith(`${base}/source?path=${encodeURIComponent("backend/app/api/routes/items.py")}`)).toBe(true);
    expect(hits.find((h) => h.kind === "handler")?.title).toContain("create_item");
    const mount = findInSnapshot("/api", components, routes, base).find((h) => h.title === "USE /api");
    expect(mount?.href.startsWith(`${base}/routes?q=${encodeURIComponent("/api")}`)).toBe(true);
  });

  it("focuses a matching component and does not invent a hit", () => {
    const hit = findInSnapshot("frontend/src", components, routes, base).find((h) => h.kind === "component");
    expect(hit?.href.startsWith(`${base}/graph?focus=${encodeURIComponent("component::frontend/src")}`)).toBe(true);
    expect(at(hit!.href)?.kind).toBe("component");
    expect(findInSnapshot("not-in-the-snapshot", components, routes, base)).toEqual([]);
  });
});
