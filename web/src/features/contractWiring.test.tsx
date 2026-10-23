import { render, within } from "@testing-library/react";
import axe from "axe-core";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type { Component, RouteItem, TraceHop } from "../api/client";
import { cid } from "../testing/samples";
import { ComponentsView, layerNote, PATH_RULE_NOTE, REASON_NOTE } from "./inventory/ComponentsPage";
import { RoutesView, filterRoutes, routeName } from "./inventory/RoutesPage";
import { CODE_LAYERS, LAYERS, LAYER_COLOR, layerColor, type Layer } from "./layers";
import { GapHidden } from "./trace/GapHidden";
import { stepHiddenRejected } from "./trace/traceModel";

// Generic schema-typed samples for renderer tests only.
const route = (extra: Partial<RouteItem>): RouteItem => ({
  method: "GET", path: "/tasks", handler_symbol: "api/tasks.py::list_tasks", operation_id: null, file: "api/tasks.py", line: 10, status: "verified", claim_id: cid(1), flags: [], ...extra,
});
const comp = (extra: Partial<Component>): Component => ({
  id: "c1", name: "src/pkg", layer: "library", kind: "directory", paths: ["src/pkg/a.py"], rule: "dir-v1:container-strip", claim_counts: { verified: 1 }, ...extra,
});
const gap = (extra: Partial<TraceHop>): TraceHop => ({
  index: 0, type: "gap", kind: "unknown", evidence_scope: "static", from_symbol: "a.py::f", to_symbol: "b.py::g", status: "unvalidated", label: "inferred", claim_id: null, reason: "no accepted outgoing static relationship", ...extra,
});

async function noViolations(el: HTMLElement) {
  const r = await axe.run(el, { rules: { region: { enabled: false } } });
  expect(r.violations.map((v) => v.id)).toEqual([]);
}

describe("RouteItem.label", () => {
  it("shows the extractor's name when present and nothing when null; never builds one", async () => {
    expect(routeName({ label: "list tasks" })).toBe("list tasks");
    expect(routeName({ label: null })).toBeNull();
    expect(routeName({ label: "  " })).toBeNull();
    expect(routeName({})).toBeNull();
    const { container } = render(
      <MemoryRouter>
        <RoutesView items={[route({ label: "list tasks" }), route({ label: null, path: "/other", claim_id: cid(2) })]} base="/r/x/s/y" onEvidence={() => {}} />
      </MemoryRouter>,
    );
    const v = within(container);
    const names = v.getAllByTestId("route-name");
    expect(names).toHaveLength(1);
    expect(names[0]!.textContent).toContain("list tasks");
    // The status chip stays separate from the name.
    const items = v.getAllByTestId("route-item");
    expect(within(items[0]!).getByTestId("status-chip").textContent).not.toContain("list tasks");
    expect(within(items[1]!).queryByTestId("route-name")).toBeNull();
    expect(items[1]!.textContent).not.toContain("GET /other");
    await noViolations(container);
  });

  it("filters on the name", () => {
    expect(filterRoutes([route({ label: "list tasks" }), route({ label: null, path: "/x" })], "list tasks", "")).toHaveLength(1);
  });
});

describe("trace gap hidden_rejected", () => {
  it("shows a per-step count with a reviewer link when present", async () => {
    expect(stepHiddenRejected(gap({ hidden_rejected: 3 }))).toBe(3);
    expect(stepHiddenRejected(gap({}))).toBeNull();
    expect(stepHiddenRejected(gap({ type: "edge", hidden_rejected: 3 }))).toBeNull();
    const { container } = render(
      <MemoryRouter>
        <ol>
          <li>
            <GapHidden hop={gap({ hidden_rejected: 3 })} snapshotHidden={{ rejected: 40 }} reviewHref="/r/x/s/y/review" />
          </li>
        </ol>
      </MemoryRouter>,
    );
    const v = within(container);
    expect(v.getByTestId("gap-hidden-step").textContent).toContain("3 rejected claims hidden here.");
    expect(v.getByRole("link", { name: "Open the reviewer view" }).getAttribute("href")).toBe("/r/x/s/y/review");
    expect(v.queryByTestId("gap-hidden")).toBeNull();
    await noViolations(container);
  });

  it("says nothing for zero and keeps the snapshot note when the count is absent", () => {
    const zero = render(
      <MemoryRouter>
        <GapHidden hop={gap({ hidden_rejected: 0 })} snapshotHidden={{ rejected: 40 }} reviewHref="/r" />
      </MemoryRouter>,
    );
    expect(zero.container.textContent).toBe("");
    const absent = render(
      <MemoryRouter>
        <GapHidden hop={gap({ hidden_rejected: null })} snapshotHidden={{ rejected: 1 }} reviewHref="/r" />
      </MemoryRouter>,
    );
    expect(within(absent.container).getByTestId("gap-hidden").textContent).toContain("1 rejected relationship is hidden");
  });
});

describe("Component.reason and the library layer", () => {
  it("shows the API's reason in place of the path-rule note", async () => {
    const items = [comp({ reason: "12 Python files under src/pkg; the repository declares a package and has no application entrypoint" })];
    expect(layerNote(items)).toBe(REASON_NOTE);
    const { container } = render(
      <MemoryRouter>
        <ComponentsView items={items} base="/r/x/s/y" />
      </MemoryRouter>,
    );
    const v = within(container);
    expect(v.getByTestId("layer-note").textContent).toBe(REASON_NOTE);
    expect(v.getByTestId("component-reason").textContent).toContain("declares a package");
    expect(v.queryByTestId("component-rule")).toBeNull();
    expect(v.getByTestId("component-layer").textContent).toBe("library");
    expect(v.getByRole("option", { name: "library" })).toBeTruthy();
    await noViolations(container);
  });

  it("falls back to the rule and the path-rule note when reason is absent", () => {
    const items = [comp({ layer: "backend", reason: null }), comp({ id: "c2", name: "src/lib", reason: "a reason" })];
    expect(layerNote(items)).toBe(PATH_RULE_NOTE);
    const { container } = render(
      <MemoryRouter>
        <ComponentsView items={items} base="/r/x/s/y" />
      </MemoryRouter>,
    );
    const v = within(container);
    expect(v.getByTestId("layer-note").textContent).toBe(PATH_RULE_NOTE);
    expect(v.getAllByTestId("component-rule")).toHaveLength(1);
    expect(v.getAllByTestId("component-reason")).toHaveLength(1);
  });

  it("every layer, library included, has an order, a colour and a code flag", () => {
    const all: Layer[] = ["frontend", "api", "backend", "library", "data", "infra", "docs", "tests", "other"];
    expect([...LAYERS].sort()).toEqual([...all].sort());
    expect(Object.keys(LAYER_COLOR).sort()).toEqual([...all].sort());
    expect(new Set(Object.values(LAYER_COLOR)).size).toBe(all.length);
    expect(CODE_LAYERS.library).toBe(true);
    expect(layerColor("library")).toBe(LAYER_COLOR.library);
    expect(layerColor("not-a-layer")).toBe(LAYER_COLOR.other);
  });
});
