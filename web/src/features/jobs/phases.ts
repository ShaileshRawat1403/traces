// Index job stepper model. Phase names are the contract's (CONTRACTS.md 3.2, Job.phase in openapi.json).
import type { Job } from "../../api/client";

export type JobPhase = Job["phase"];
export type JobState = Job["state"];

export const STEPS: ReadonlyArray<{ phase: JobPhase; title: string; help: string }> = [
  { phase: "fetching", title: "Fetch", help: "Fetch the public repository with hardened git (hooks, symlinks and LFS off)." },
  { phase: "checking_out", title: "Pin", help: "Check out and pin the exact commit SHA." },
  { phase: "indexing", title: "Extract", help: "Run the pinned extractor in the network-isolated sandbox." },
  { phase: "adapting", title: "Adapt", help: "Convert extractor output into Traces evidence records." },
  { phase: "validating", title: "Validate", help: "Independent Python and TypeScript validators check each claim." },
  { phase: "storing", title: "Store", help: "Write evidence records to the local store." },
  { phase: "history", title: "History", help: "Derive Git history records for the snapshot." },
];

export type StepState = "pending" | "active" | "done" | "failed" | "skipped";

export interface StepView {
  phase: JobPhase;
  title: string;
  help: string;
  state: StepState;
  events: NonNullable<Job["events"]>;
}

export const TERMINAL_STATES: ReadonlySet<JobState> = new Set<JobState>(["succeeded", "failed", "cancelled"]);

export function isTerminal(job: Pick<Job, "state">): boolean {
  return TERMINAL_STATES.has(job.state);
}

const stepIndex = (p: string) => STEPS.findIndex((s) => s.phase === p);

/** The step a failed or cancelled job stopped in: the last event phase that is a step. */
function lastStepPhase(job: Job): number {
  const fromPhase = stepIndex(job.phase);
  if (fromPhase >= 0) return fromPhase;
  const events = job.events ?? [];
  for (let i = events.length - 1; i >= 0; i--) {
    const idx = stepIndex(events[i]!.phase);
    if (idx >= 0) return idx;
  }
  return -1;
}

export function stepViews(job: Job): StepView[] {
  const events = job.events ?? [];
  const reached = lastStepPhase(job);
  return STEPS.map((s, i) => {
    let state: StepState;
    if (job.state === "succeeded") state = "done";
    else if (job.state === "failed") state = i < reached ? "done" : i === reached ? "failed" : "skipped";
    else if (job.state === "cancelled") state = i < reached ? "done" : "skipped";
    else if (job.state === "queued" || reached < 0) state = "pending";
    else state = i < reached ? "done" : i === reached ? "active" : "pending";
    return { ...s, state, events: events.filter((e) => e.phase === s.phase) };
  });
}
