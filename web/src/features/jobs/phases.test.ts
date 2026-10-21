import { describe, expect, it } from "vitest";
import type { Job } from "../../api/client";
import { STEPS, isTerminal, stepViews } from "./phases";

const job = (over: Partial<Job>): Job => ({
  id: "j1",
  repo_id: "r",
  snapshot_id: null,
  kind: "index",
  state: "running",
  phase: "queued",
  progress: 0,
  version: 1,
  created_at: "2026-10-21T10:00:00Z",
  updated_at: "2026-10-21T10:00:00Z",
  events: [],
  ...over,
});
const states = (j: Job) => stepViews(j).map((s) => s.state);

describe("index stepper", () => {
  it("uses the contract's seven phases in order", () => {
    expect(STEPS.map((s) => s.phase)).toEqual(["fetching", "checking_out", "indexing", "adapting", "validating", "storing", "history"]);
    expect(STEPS.map((s) => s.title)).toEqual(["Fetch", "Pin", "Extract", "Adapt", "Validate", "Store", "History"]);
  });
  it("queued: all pending", () => {
    expect(states(job({ state: "queued" }))).toEqual(Array(7).fill("pending"));
  });
  it("running in validating: earlier done, current active, later pending", () => {
    expect(states(job({ phase: "validating" }))).toEqual(["done", "done", "done", "done", "active", "pending", "pending"]);
  });
  it("failed: the failing step comes from the last event phase", () => {
    const j = job({
      state: "failed",
      phase: "failed",
      events: [
        { at: "t1", phase: "fetching", level: "info", message: "ok" },
        { at: "t2", phase: "indexing", level: "error", message: "boom" },
        { at: "t3", phase: "failed", level: "error", message: "stopped" },
      ],
    });
    expect(states(j)).toEqual(["done", "done", "failed", "skipped", "skipped", "skipped", "skipped"]);
    expect(stepViews(j)[2]!.events).toHaveLength(1);
  });
  it("succeeded: all done; terminal states", () => {
    const j = job({ state: "succeeded", phase: "done", progress: 1 });
    expect(states(j)).toEqual(Array(7).fill("done"));
    expect(isTerminal(j)).toBe(true);
    expect(isTerminal(job({ state: "running" }))).toBe(false);
    expect(isTerminal(job({ state: "cancelled" }))).toBe(true);
  });
});
