import { render, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { Component, RouteItem } from "../../api/client";
import { cid } from "../../testing/samples";
import { ComponentsView, filterComponents, splitCounts } from "./ComponentsPage";
import { RoutesView, filterRoutes } from "./RoutesPage";
import { windowFor, WINDOW } from "../source/SourcePage";

// Generic schema-typed samples for renderer tests only.
const routes: RouteItem[] = [
  { method: "GET", path: "/tasks", handler_symbol: "api/tasks.py::list_tasks", operation_id: null, file: "api/tasks.py", line: 10, status: "verified", claim_id: cid(1), flags: [] },
  { method: "UNKNOWN", path: "/settings", handler_symbol: null, operation_id: null, file: "web/src/routes/settings.tsx", line: 4, status: "observed", claim_id: cid(2), flags: ["method_not_recorded"] },
];
const components: Component[] = [
  { id: "c1", name: "src/pkg", layer: "backend", kind: "directory", paths: ["src/pkg/a.py", "src/pkg/b.py"], rule: "dir-v1:container-strip", claim_counts: { verified: 3, observed: 2, rejected: 4 } },
  { id: "c2", name: "docs", layer: "docs", kind: "directory", paths: ["docs/index.md"], rule: "dir-v1:container-strip", claim_counts: {} },
];

describe("routes view", () => {
  it("filters by text and method", () => {
    expect(filterRoutes(routes, "task", "")).toHaveLength(1);
    expect(filterRoutes(routes, "", "UNKNOWN").map((r) => r.path)).toEqual(["/settings"]);
    expect(filterRoutes(routes, "settings.tsx", "GET")).toHaveLength(0);
  });

  it("renders labels, a not-recorded method, hidden counts and evidence buttons", async () => {
    const onEvidence = vi.fn();
    const { container } = render(
      <MemoryRouter>
        <RoutesView items={routes} base="/r/x/s/y" onEvidence={onEvidence} hidden={{ rejected: 2 }} />
      </MemoryRouter>,
    );
    const v = within(container);
    expect(v.getAllByTestId("route-item")).toHaveLength(2);
    expect(v.getAllByTestId("route-method")[1]!.textContent).toBe("method not recorded");
    expect(v.getAllByTestId("status-chip").map((c) => c.getAttribute("data-label"))).toEqual(["verified", "observed"]);
    expect(v.getByTestId("hidden-counts").textContent).toContain("2 rejected");
    await userEvent.click(v.getAllByRole("button", { name: /Open evidence/ })[0]!);
    expect(onEvidence).toHaveBeenCalledWith(cid(1));
    const r = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(r.violations.map((x) => x.id)).toEqual([]);
  });
});

describe("components view", () => {
  it("splits rejected out of the counts and filters by layer and path", () => {
    expect(splitCounts(components[0]!.claim_counts)).toEqual({ shown: [["observed", 2], ["verified", 3]], rejected: 4 });
    expect(filterComponents(components, "b.py", "")).toHaveLength(1);
    expect(filterComponents(components, "", "docs").map((c) => c.id)).toEqual(["c2"]);
  });

  it("shows the API's layer with its rule and never draws rejected claims", async () => {
    const { container } = render(
      <MemoryRouter>
        <ComponentsView items={components} base="/r/x/s/y" />
      </MemoryRouter>,
    );
    const v = within(container);
    expect(v.getAllByTestId("component-layer").map((d) => d.textContent)).toEqual(["backend", "docs"]);
    expect(v.getByTestId("layer-note").textContent).toContain("library's source folder can be labelled backend");
    expect(container.querySelectorAll('[data-status="rejected"]')).toHaveLength(0);
    expect(v.getByTestId("hidden-counts").textContent).toContain("4 rejected");
    expect(v.getAllByRole("link", { name: "src/pkg/a.py" })[0]!.getAttribute("href")).toBe("/r/x/s/y/source?path=src%2Fpkg%2Fa.py");
    const r = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(r.violations.map((x) => x.id)).toEqual([]);
  });
});

describe("source window", () => {
  it("reads at most the API cap and centres on a highlighted line", () => {
    expect(windowFor(undefined, undefined)).toEqual({ start: 1, end: WINDOW });
    expect(windowFor(undefined, 500)).toEqual({ start: 450, end: 450 + WINDOW - 1 });
    expect(windowFor(801, 500).start).toBe(801);
  });
});
