// Generic, schema-typed sample responses for renderer tests ONLY (unit tests and Playwright route interception).
// Never imported by app code. Names are neutral and not taken from any analyzed repository.
import type { Schemas } from "../api/client";

export const SHA = "0123456789abcdef0123456789abcdef01234567";
export const SNAPSHOT_ID = `github.com__example__app@${SHA}`;
export const cid = (n: number) => `c_${n.toString(16).padStart(64, "0")}`;

export const overviewSample: Schemas["Overview"] = {
  snapshot_id: SNAPSHOT_ID,
  business: [
    { kind: "fact", text: "The README describes a task tracking service with sign-in.", claim_ids: [cid(1)] },
    { kind: "interpretation", text: "The main user flow appears to be creating and listing tasks.", claim_ids: [cid(2), cid(3)] },
    { kind: "unknown", text: "Billing or payment capability could not be determined.", claim_ids: [] },
  ],
  architecture: [
    { kind: "fact", text: "A web client calls an HTTP API through a generated SDK.", claim_ids: [cid(4)] },
    { kind: "fact", text: "This statement is marked as a fact but has no citation.", claim_ids: [] },
  ],
  implementation: [{ kind: "fact", text: "The API is written in Python; the client in TypeScript.", claim_ids: [cid(5)] }],
  entry_points: [{ kind: "fact", text: "POST /api/tasks handled by api/tasks.py::create_task", claim_ids: [cid(6)] }],
  start_here: [{ kind: "interpretation", text: "Start with the tasks page and follow its submit handler.", claim_ids: [cid(7)] }],
  languages: { Python: 40, TypeScript: 120 },
  counts: { verified: 900, observed: 1500, inferred: 30 },
};
