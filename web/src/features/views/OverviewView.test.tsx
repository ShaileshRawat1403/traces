import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import type { Overview } from "../../api/client";
import { overviewSample } from "../../testing/samples";
import { factStanding, partitionFacts } from "../../ui/Facts";
import { OverviewView } from "./OverviewView";

afterEach(cleanup);
const base = "/r/x/s/y";
const renderView = (data: Overview) =>
  render(
    <MemoryRouter>
      <OverviewView data={data} base={base} />
    </MemoryRouter>,
  );

describe("fact standing", () => {
  it("a fact is grounded only with a citation", () => {
    expect(factStanding({ kind: "fact", text: "a", claim_ids: ["c_1"] })).toBe("grounded");
    expect(factStanding({ kind: "fact", text: "a", claim_ids: [] })).toBe("uncited");
    expect(factStanding({ kind: "interpretation", text: "a", claim_ids: ["c_1"] })).toBe("interpretation");
    expect(factStanding({ kind: "unknown", text: "a", claim_ids: [] })).toBe("unknown");
  });
  it("uncited facts land with unknowns, never with grounded", () => {
    const p = partitionFacts(overviewSample.architecture);
    expect(p.grounded).toHaveLength(1);
    expect(p.unknown).toHaveLength(1);
  });
});

describe("OverviewView", () => {
  it("separates grounded, interpretation and unknown in the business layer", () => {
    renderView(overviewSample);
    const panel = screen.getByRole("tabpanel");
    expect(within(panel).getByRole("group", { name: "Grounded in evidence" })).toBeTruthy();
    const interp = within(panel).getByRole("group", { name: "Interpretation" });
    expect(within(interp).getByText(/appears to be/)).toBeTruthy();
    expect(within(panel).getByRole("group", { name: "Unknown or unsupported" })).toBeTruthy();
  });
  it("links citations to evidence pages", () => {
    renderView(overviewSample);
    const links = screen.getAllByTestId("citation");
    expect(links.length).toBeGreaterThan(0);
    expect(links[0]!.getAttribute("href")).toMatch(/^\/r\/x\/s\/y\/claim\/c_/);
  });
  it("switches layers with the keyboard and shows uncited facts as Unsupported", async () => {
    renderView(overviewSample);
    const user = userEvent.setup();
    await user.click(screen.getByRole("tab", { name: /Business/ }));
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: /Architecture/ }).getAttribute("aria-selected")).toBe("true");
    expect(within(screen.getByRole("tabpanel")).getByText("Unsupported")).toBeTruthy();
  });
  it("shows languages and counts on the implementation tab", async () => {
    renderView(overviewSample);
    await userEvent.setup().click(screen.getByRole("tab", { name: /Implementation/ }));
    const langs = screen.getByRole("group", { name: "Languages" });
    expect(within(langs).getByText("TypeScript")).toBeTruthy();
  });
  it("handles an empty overview", () => {
    renderView({ ...overviewSample, business: [], architecture: [], implementation: [], entry_points: [], start_here: [], languages: {}, counts: {} });
    expect(screen.getByText("No entry points reported.")).toBeTruthy();
    expect(screen.getByText(/No business facts reported/)).toBeTruthy();
  });
  it("has no axe violations (structure rules; contrast is checked in Playwright)", async () => {
    const { container } = renderView(overviewSample);
    const r = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(r.violations.map((v) => v.id)).toEqual([]);
  });
});
