import { render, screen, within } from "@testing-library/react";
import axe from "axe-core";
import { describe, expect, it } from "vitest";
import { cochangeSample, hotspotsSample, HISTORY_SHAS, historyRecords, milestonesSample, timelineSample } from "../../testing/samples";
import { BarChart } from "./BarChart";
import { Criteria } from "./Criteria";
import { HistoryEvidence } from "./HistoryEvidence";
import { HistoryItem, visibleItems } from "./HistoryItems";
import { cochangeText, metricKeys, milestoneSha } from "./HistoryPage";
import { distinctParameters, historyNote, metric, readHistoryExtras } from "./historyRecord";

const rec = (id: string) => readHistoryExtras(historyRecords[id]);

describe("history record reading", () => {
  it("reads citations, parameters, metrics and review state defensively", () => {
    const x = rec(timelineSample.items[1]!.claim_id);
    expect(x.citations[0]!.paths[0]).toEqual({ path: "api/tasks.py", old_path: "src/tasks.py", status: "R", similarity: 87 });
    expect(x.parameters?.values).toEqual({ rename_threshold: 50, copy_threshold: 50, rename_limit: 10000 });
    expect(readHistoryExtras({ citations: [{ nope: 1 }, "x"], metrics: [1], parameters: "x" })).toEqual({ parameters: null, metrics: null, citations: [], review_state: null });
    expect(metric(rec(cochangeSample.items[0]!.claim_id), "support")).toBe(18);
    expect(metric({ ...rec(cochangeSample.items[0]!.claim_id), metrics: { support: "18" } }, "support")).toBeNull();
  });
  it("groups distinct parameter sets by digest", () => {
    const sets = distinctParameters(timelineSample.items.map((i) => rec(i.claim_id)));
    expect(sets).toHaveLength(1);
    expect(sets[0]!.count).toBe(2);
  });
  it("uses the contract wording for history statuses", () => {
    expect(historyNote("history_pattern", "observed")).toMatch(/Count checked against Git, not a confirmed relationship/);
    expect(historyNote("documented_rationale", "observed")).toBe("Quoted rationale, not proof of intent.");
    expect(historyNote("analyzer_inference", "verified")).toBeNull();
  });
});

describe("history helpers", () => {
  it("phrases co-change as N of M commits from metrics, else the qualifier", () => {
    const i = cochangeSample.items[0]!;
    expect(cochangeText(i, rec(i.claim_id))).toBe("changed together in 18 of 19 commits");
    expect(cochangeText(i, undefined)).toBe(i.qualifier);
  });
  it("finds the milestone commit from citations or the commit endpoint", () => {
    const i = milestonesSample.items[0]!;
    expect(milestoneSha(i, rec(i.claim_id))).toBe(HISTORY_SHAS.C1);
    expect(milestoneSha(i, undefined)).toBe(HISTORY_SHAS.C1);
    expect(milestoneSha({ ...i, from_symbol: "commit::abc" }, undefined)).toBeNull();
  });
  it("lists numeric metric keys with preferred ones first", () => {
    expect(metricKeys(hotspotsSample.items.map((i) => rec(i.claim_id)), ["hotspot_score", "revisions"])).toEqual(["hotspot_score", "revisions", "authors", "churn"]);
  });
  it("hides rejected items in the default view and counts them", () => {
    const v = visibleItems(timelineSample);
    expect(v.shown.map((i) => i.status)).not.toContain("rejected");
    expect(v.hidden).toEqual({ rejected: 1 });
  });
});

describe("history renderers", () => {
  it("gives every chart value a table equivalent and hides the drawing from assistive tech", async () => {
    const { container } = render(
      <BarChart
        title="Degree"
        unit="Changed together"
        max={1}
        bars={[
          { id: "a", label: "a and b", value: 0.95, display: "changed together in 18 of 19 commits" },
          { id: "b", label: "c and d", value: null, display: "" },
        ]}
      />,
    );
    const fig = screen.getByRole("figure", { name: "Degree" });
    expect(fig.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
    const rows = within(fig).getAllByRole("row");
    expect(rows[1]!.textContent).toContain("18 of 19 commits");
    expect(rows[2]!.textContent).toContain("not reported");
    expect((await axe.run(container)).violations.map((v) => v.id)).toEqual([]);
  });
  it("prints record parameters verbatim as the criteria echo", () => {
    render(<Criteria endpoint="GET history/cochange" records={cochangeSample.items.map((i) => rec(i.claim_id))} loading={false} />);
    const pre = screen.getByLabelText("Parameters, verbatim");
    expect(JSON.parse(pre.textContent!)).toEqual((historyRecords[cochangeSample.items[0]!.claim_id]!.parameters as { values: unknown }).values);
  });
  it("renders a history item with the pattern note, commits and review state", async () => {
    const alias = timelineSample.items[3]!;
    const { container } = render(
      <ul>
        <HistoryItem item={alias} x={rec(alias.claim_id)} onEvidence={() => undefined} />
      </ul>,
    );
    expect(container.textContent).toContain("Suggested from history, not established by Git.");
    expect(container.textContent).toContain("suggested, not confirmed");
    expect(screen.getByTestId("history-commits").textContent).toContain(HISTORY_SHAS.C3.slice(0, 7));
    expect((await axe.run(container, { rules: { "color-contrast": { enabled: false } } })).violations.map((v) => v.id)).toEqual([]);
  });
  it("shows a history record's citations and parameters in the evidence view", () => {
    render(<HistoryEvidence raw={historyRecords[timelineSample.items[1]!.claim_id]} />);
    expect(screen.getByTestId("history-citations").textContent).toContain("Git similarity 87%");
    expect(screen.getByLabelText("Record parameters").textContent).toContain("rename_threshold");
  });
  it("renders nothing extra for code records", () => {
    const { container } = render(<HistoryEvidence raw={{ claim_id: "c_1", locations: [] }} />);
    expect(container.innerHTML).toBe("");
  });
});
