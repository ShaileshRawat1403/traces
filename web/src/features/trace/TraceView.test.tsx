import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import axe from "axe-core";
import { traceSample } from "../../testing/samples";
import { TraceView } from "./TraceView";

describe("TraceView", () => {
  it("renders ordered steps with gaps and library contract steps as distinct inferred items", async () => {
    const onEvidence = vi.fn();
    const { container } = render(
      <MemoryRouter>
        <TraceView t={traceSample} reviewHref="/review" onEvidence={onEvidence} />
      </MemoryRouter>,
    );
    const steps = within(screen.getByRole("list", { name: "Trace steps in order" })).getAllByRole("listitem");
    expect(steps.map((li) => li.getAttribute("data-hop"))).toEqual(["edge", "edge", "library_contract", "gap", "edge"]);
    expect(steps[3]!.textContent).toContain("Why this is inferred");
    expect(steps[3]!.textContent).toContain("no evidence to open");
    expect(within(steps[3]!).queryByRole("button")).toBeNull();
    expect(steps[2]!.textContent).toContain("Library contract step");
    expect(screen.getByTestId("trace-incomplete")).toBeTruthy();
    await userEvent.click(within(steps[2]!).getByRole("button", { name: "Open evidence" }));
    expect(onEvidence).toHaveBeenCalledWith(traceSample.hops.find((h) => h.type === "library_contract")!.claim_id);
    const r = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(r.violations.map((v) => v.id)).toEqual([]);
  });
});
