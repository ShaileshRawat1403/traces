import { describe, expect, it } from "vitest";
import { decodeSubject, encodeSubject, subjectLabel, withAt, type Subject } from "./subject";

const route: Subject = { kind: "route", method: "POST", path: "/api/v1/items/", handler: "items.py::create_item" };

describe("subject", () => {
  it("round-trips a route, a component, a symbol and a file", () => {
    const all: Subject[] = [
      route,
      { kind: "component", id: "component::backend/app", label: "backend/app" },
      { kind: "symbol", id: "items.py::create_item", label: "create_item" },
      { kind: "file", path: "backend/app/api/routes/items.py" },
    ];
    for (const s of all) expect(decodeSubject(encodeSubject(s))).toEqual(s);
  });

  it("drops a value that is not a subject", () => {
    expect(decodeSubject(null)).toBeNull();
    expect(decodeSubject("nope")).toBeNull();
    expect(decodeSubject("component\n")).toBeNull();
  });

  it("adds at without dropping the link's own query", () => {
    const href = withAt("/r/a/s/b/graph?focus=component::x", route);
    const q = new URL(href, "http://local").searchParams;
    expect(q.get("focus")).toBe("component::x");
    expect(decodeSubject(q.get("at"))).toEqual(route);
    expect(subjectLabel(route)).toBe("POST /api/v1/items/");
  });
});
