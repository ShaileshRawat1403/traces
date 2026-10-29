import { describe, expect, it } from "vitest";
import { starterQuestions } from "./starters";

describe("starterQuestions", () => {
  it("uses a stored route and skips mounts and unknown methods", () => {
    const qs = starterQuestions("b1125d883948", [
      { method: "USE", path: "/api" },
      { method: "UNKNOWN", path: "/settings" },
      { method: "POST", path: "/api/v1/items/" },
    ]);
    expect(qs[0]).toBe("What does POST /api/v1/items/ do?");
    expect(qs).toContain("Which routes are declared?");
    expect(qs).toContain("How is data persisted?");
    expect(qs).toContain("Which files changed together?");
    expect(qs).toContain("What changed in commit b1125d883948?");
    expect(qs.join(" ")).not.toContain("USE");
  });

  it("still offers the questions that do not need a route", () => {
    expect(starterQuestions("abc", [])).toEqual(["Which routes are declared?", "How is data persisted?", "Which files changed together?"]);
  });
});
