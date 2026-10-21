import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { sourceSample } from "../../testing/samples";
import { SourceLinesView, windowFacts } from "./SourceLines";

describe("windowFacts", () => {
  it("is not shortened when the window reaches the end of the file", () => {
    expect(windowFacts(sourceSample("a.ts", 35, 60, 40), { start: 35, end: 60 }).shortened).toBe(false);
  });
  it("is shortened when the API returned fewer lines than requested and available", () => {
    const v = { ...sourceSample("a.ts", 1, 10, 400) };
    expect(windowFacts(v, { start: 1, end: 200 }).shortened).toBe(true);
  });
});

describe("SourceLinesView", () => {
  it("shows the pinned path, sha, total and highlighted lines as text", () => {
    const v = { ...sourceSample("web/src/a.tsx", 4, 9), lines: ["<b>not html</b>", ...sourceSample("x", 5, 9).lines], generated: true };
    render(<SourceLinesView v={v} highlight={{ start: 6, end: 7 }} requested={{ start: 4, end: 9 }} />);
    const fig = screen.getByTestId("source-lines");
    expect(fig.textContent).toContain("web/src/a.tsx");
    expect(fig.textContent).toContain("lines 4 to 9 of 40");
    expect(fig.textContent).toContain(`@${v.sha.slice(0, 7)}`);
    expect(fig.textContent).toContain("generated file");
    expect(fig.querySelectorAll("[data-hit]")).toHaveLength(2);
    expect(fig.querySelector("b")).toBeNull();
    expect(fig.textContent).toContain("<b>not html</b>");
  });
});
