import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { explainBundleSample, explainSample } from "../../testing/samples";
import { ExplainView, sentenceStanding } from "./ExplainView";

const wrap = (r: typeof explainSample) =>
  render(
    <MemoryRouter>
      <ExplainView r={r} base="/r/x/s/y" />
    </MemoryRouter>,
  );

describe("ExplainView", () => {
  it("keeps the answer order and tags every sentence", async () => {
    const { container } = wrap(explainSample);
    const items = screen.getAllByTestId("answer-sentence");
    expect(items.map((li) => li.getAttribute("data-standing"))).toEqual(explainSample.answer.map(sentenceStanding));
    expect(items.map((li) => li.getAttribute("data-standing"))).toEqual(["unknown", "interpretation", "grounded", "interpretation", "grounded"]);
    expect(within(items[2]!).getAllByTestId("citation")).toHaveLength(1);
    expect(within(items[0]!).queryAllByTestId("citation")).toHaveLength(0);
    // long citation lists are capped with a count
    expect(within(items[4]!).getAllByTestId("citation")).toHaveLength(12);
    expect(items[4]!.textContent).toContain("and 3 more");
    expect(screen.getByTestId("answer-summary").textContent).toContain("2 grounded, 2 interpretation, 1 unknown");
    await userEvent.click(screen.getByText("Where the cited evidence comes from"));
    expect(screen.getByTestId("categories").textContent).toContain("Runtime observations");
    expect(screen.queryByTestId("outbound")).toBeNull();
    const r = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(r.violations.map((v) => v.id)).toEqual([]);
  });

  it("treats an uncited fact as unknown, never grounded", () => {
    expect(sentenceStanding({ kind: "fact", text: "x", claim_ids: [] })).toBe("unknown");
  });

  it("shows exactly what a bundle would send, and that nothing was sent", async () => {
    const { container } = wrap(explainBundleSample);
    const out = screen.getByTestId("outbound");
    expect(out.textContent).toContain("Nothing has been sent");
    expect(within(out).getAllByRole("row")).toHaveLength(1 + explainBundleSample.outbound_manifest.length);
    expect(within(out).getByLabelText("Prompt text").textContent).toContain("<evidence>");
    const r = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(r.violations.map((v) => v.id)).toEqual([]);
  });
});
