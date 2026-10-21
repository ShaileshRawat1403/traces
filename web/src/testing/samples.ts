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

const sym = (file: string, name: string) => `${file}::${name}`;
export const COMPONENT_IDS = { web: "cmp_web", api: "cmp_api" } as const;

export const componentsSample: Schemas["Component"][] = [
  { id: COMPONENT_IDS.web, name: "web", layer: "frontend", kind: "package", paths: ["web/src"], rule: "top-level package directory", claim_counts: { verified: 12, observed: 30, inferred: 4 } },
  { id: COMPONENT_IDS.api, name: "api", layer: "api", kind: "package", paths: ["api"], rule: "top-level package directory", claim_counts: { verified: 8, observed: 21, inferred: 2 } },
];

export const graphComponentsSample: Schemas["GraphResponse"] = {
  snapshot_id: SNAPSHOT_ID,
  nodes: [
    { id: COMPONENT_IDS.web, label: "web", entity: "component", layer: "frontend", file: null, degree: 1 },
    { id: COMPONENT_IDS.api, label: "api", entity: "component", layer: "api", file: null, degree: 1 },
  ],
  edges: [{ id: cid(20), source: COMPONENT_IDS.web, target: COMPONENT_IDS.api, kind: "calls", status: "observed", label: "observed", flags: [], qualifier: null }],
  hidden_counts: { unvalidated: 3, rejected: 1 },
  truncated: false,
  limit: 300,
};

export const graphSymbolsSample: Schemas["GraphResponse"] = {
  snapshot_id: SNAPSHOT_ID,
  nodes: [
    { id: sym("web/src/TaskList.tsx", "TaskList"), label: "TaskList", entity: "symbol", layer: "frontend", file: "web/src/TaskList.tsx", degree: 2 },
    { id: sym("web/src/TaskItem.tsx", "TaskItem"), label: "TaskItem", entity: "symbol", layer: "frontend", file: "web/src/TaskItem.tsx", degree: 1 },
    { id: sym("web/src/client.ts", "listTasks"), label: "listTasks", entity: "symbol", layer: "frontend", file: "web/src/client.ts", degree: 2 },
    { id: sym("api/tasks.py", "list_tasks"), label: "list_tasks", entity: "symbol", layer: "api", file: "api/tasks.py", degree: 1 },
  ],
  edges: [
    { id: cid(21), source: sym("web/src/TaskList.tsx", "TaskList"), target: sym("web/src/TaskItem.tsx", "TaskItem"), kind: "renders", status: "verified", label: "verified", flags: [], qualifier: null },
    { id: cid(22), source: sym("web/src/TaskList.tsx", "TaskList"), target: sym("web/src/client.ts", "listTasks"), kind: "calls", status: "observed", label: "observed", flags: [], qualifier: null },
    { id: cid(23), source: sym("web/src/client.ts", "listTasks"), target: sym("api/tasks.py", "list_tasks"), kind: "http_call", status: "unvalidated", label: "inferred", flags: [], qualifier: "matched by route string" },
    { id: cid(24), source: sym("api/tasks.py", "list_tasks"), target: sym("web/src/TaskItem.tsx", "TaskItem"), kind: "renders", status: "rejected", label: "rejected", flags: [], qualifier: null },
  ],
  hidden_counts: { missing_location: 1 },
  truncated: false,
  limit: 300,
};

/** A SourceView for any requested window: numbered placeholder lines, capped at total_lines (shortened when past the end). */
export function sourceSample(path: string, start: number, end: number, total_lines = 40): Schemas["SourceView"] {
  const last = Math.min(end, total_lines);
  const lines = Array.from({ length: Math.max(0, last - start + 1) }, (_, i) => `const line${start + i} = ${start + i}; // sample`);
  return { snapshot_id: SNAPSHOT_ID, sha: SHA, path, blob_sha: "f".repeat(40), start_line: start, end_line: last, total_lines, lines, generated: false, claim_ids: [cid(21)] };
}

const hop = (h: Partial<Schemas["TraceHop"]> & Pick<Schemas["TraceHop"], "index" | "type" | "from_symbol" | "to_symbol" | "kind">): Schemas["TraceHop"] => ({
  status: "verified",
  label: "verified",
  claim_id: cid(30 + h.index),
  qualifier: null,
  reason: null,
  evidence_scope: "static",
  ...h,
});

/** A five-step trace covering every hop type, delivered out of order to exercise index ordering. */
export const traceSample: Schemas["TraceResponse"] = {
  snapshot_id: SNAPSHOT_ID,
  from_symbol: sym("web/src/TaskForm.tsx", "TaskForm"),
  to_symbol: sym("api/models.py", "Task"),
  complete: false,
  disclaimer: "Static analysis only. No runtime behavior has been observed.",
  hidden_counts: { rejected: 1 },
  hops: [
    hop({ index: 2, type: "library_contract", from_symbol: sym("web/src/client.ts", "createTask"), to_symbol: sym("api/tasks.py", "create_task"), kind: "http_call", status: "unvalidated", label: "inferred", reason: "Matched by the HTTP client's documented request contract; the route string is not resolved statically." }),
    hop({ index: 0, type: "edge", from_symbol: sym("web/src/TaskForm.tsx", "TaskForm"), to_symbol: sym("web/src/TaskForm.tsx", "onSubmit"), kind: "defines" }),
    hop({ index: 1, type: "edge", from_symbol: sym("web/src/TaskForm.tsx", "onSubmit"), to_symbol: sym("web/src/client.ts", "createTask"), kind: "calls", status: "observed", label: "observed" }),
    hop({ index: 3, type: "gap", from_symbol: sym("api/tasks.py", "create_task"), to_symbol: sym("api/crud.py", "save"), kind: "calls", status: null, label: "inferred", claim_id: null, reason: "No recorded relationship between these symbols; the call goes through dependency injection." }),
    hop({ index: 4, type: "edge", from_symbol: sym("api/crud.py", "save"), to_symbol: sym("api/models.py", "Task"), kind: "writes", status: "missing_location", label: "inferred" }),
  ],
};
