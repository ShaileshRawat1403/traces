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
    expect(steps[3]!.textContent).toContain("What this gap means");
    expect(steps[3]!.textContent).toContain("No static evidence that Traces accepts connects these two steps");
    expect(steps[3]!.textContent).not.toMatch(/no outgoing|is not called|never calls/i);
    expect(steps[3]!.textContent).toContain("API note");
    expect(steps[3]!.textContent).toContain("no evidence to open");
    expect(within(steps[3]!).queryByRole("button")).toBeNull();
    expect(steps[2]!.textContent).toContain("Library contract step");
    expect(screen.getByTestId("trace-incomplete")).toBeTruthy();
    await userEvent.click(within(steps[2]!).getByRole("button", { name: "Open evidence" }));
    expect(onEvidence).toHaveBeenCalledWith(traceSample.hops.find((h) => h.type === "library_contract")!.claim_id);
    const r = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(r.violations.map((v) => v.id)).toEqual([]);
  });

  it("says a rejected relationship may sit behind a gap when rejected ones are hidden (O-2)", () => {
    const t = { ...traceSample, hidden_counts: { rejected: 47 } };
    const { container } = render(
      <MemoryRouter>
        <TraceView t={t} reviewHref="/review" onEvidence={() => {}} />
      </MemoryRouter>,
    );
    expect(within(container).getAllByTestId("gap-hidden")[0]!.textContent).toContain("47 rejected relationships are hidden from this trace");
  });

  it("F-9: shows unresolved calls as their own gap, never as a symbol, and gives the API reasons", async () => {
    const start = traceSample.hops.find((h) => h.index === 1)!;
    const t = {
      ...traceSample,
      to_symbol: null,
      hops: [
        { ...start, index: 0 },
        { ...start, index: 1, type: "gap" as const, to_symbol: "(unresolved)", claim_id: null, status: null, label: "inferred" as const, reason: "2 outgoing call(s) from this step are recorded only as unresolved references", unresolved_calls: ["mutation.mutate", "reset"] },
      ],
      complete: false,
      incomplete_reasons: ["gaps: 1"],
    };
    const { container } = render(
      <MemoryRouter>
        <TraceView t={t} reviewHref="/review" onEvidence={() => {}} />
      </MemoryRouter>,
    );
    const steps = within(within(container).getByRole("list", { name: "Trace steps in order" })).getAllByRole("listitem");
    expect(steps[1]!.textContent).toContain("Gap: calls the trace cannot follow");
    expect(within(steps[1]!).getByTestId("unresolved-calls").textContent).toBe("Unresolved calls:mutation.mutatereset");
    expect(steps[1]!.textContent).not.toContain("(unresolved)");
    expect(steps[1]!.textContent).toContain("did not resolve them to a declaration");
    expect(steps[1]!.textContent).not.toContain("connects these two steps");
    expect(within(container).getByTestId("trace-incomplete").textContent).toContain("1 step with calls the trace cannot follow");
    expect(within(container).getByTestId("trace-incomplete-reasons").textContent).toBe("API reasons: gaps: 1");
    const r = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(r.violations.map((v) => v.id)).toEqual([]);
  });

  it("F-9: a trace without gaps can still be incomplete because a step is not verified or observed", () => {
    const t = { ...traceSample, hops: traceSample.hops.filter((h) => h.type !== "gap"), complete: false, incomplete_reasons: ["1 step(s) rest on relationships that are not verified or observed"] };
    const { container } = render(
      <MemoryRouter>
        <TraceView t={t} reviewHref="/review" onEvidence={() => {}} />
      </MemoryRouter>,
    );
    const v = within(container);
    expect(v.getByTestId("trace-incomplete").textContent).toBe("Incomplete: 1 step rests on a relationship that is not verified or observed.");
    expect(within(container).getByTestId("trace-incomplete").textContent).not.toContain("gap");
  });
});
