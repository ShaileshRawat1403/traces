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

/** ExplainResponse with every sentence standing, in order, plus a prepare_bundle variant with a manifest. */
export const explainSample: Schemas["ExplainResponse"] = {
  snapshot_id: SNAPSHOT_ID,
  answer: [
    { kind: "unknown", text: "Static evidence cannot show runtime behavior, so how this behaves when the code runs is unknown.", claim_ids: [] },
    { kind: "interpretation", text: "A recorded path of 3 steps links TaskForm to create_task.", claim_ids: [cid(40), cid(41), cid(42)] },
    { kind: "fact", text: "The evidence records that TaskForm calls createTask, at web/src/TaskForm.tsx:12 (verified).", claim_ids: [cid(40)] },
    { kind: "interpretation", text: "Not established: createTask hands off, through a library, to create_task. This is inferred.", claim_ids: [cid(41)] },
    { kind: "fact", text: "A route POST /tasks is declared at api/tasks.py:18 (observed).", claim_ids: Array.from({ length: 15 }, (_, i) => cid(50 + i)) },
  ],
  citations: [
    { claim_id: cid(40), status: "verified", label: "verified", file: "web/src/TaskForm.tsx", start_line: 12, end_line: 12, commit: SHA },
    { claim_id: cid(41), status: "unvalidated", label: "inferred", file: "web/src/client.ts", start_line: 30, end_line: 34, commit: SHA },
    { claim_id: cid(42), status: "missing_location", label: "inferred", file: null, start_line: null, end_line: null, commit: SHA },
  ],
  categories: { code_structure: [cid(40)], inference: [cid(41), cid(42)], documented_decisions: [], history_patterns: [], runtime_observations: [] },
  prompt_bundle: null,
  outbound_manifest: [],
  requires_consent: true,
};

export const explainBundleSample: Schemas["ExplainResponse"] = {
  ...explainSample,
  prompt_bundle: { instructions: "Use only the evidence below.", prompt: "Use only the evidence below.\n<evidence>\n[c_1] (verified) TaskForm calls createTask\n</evidence>\n<question>How is a task saved?</question>" },
  outbound_manifest: [
    { kind: "instructions", claim_id: null, file: null, start_line: null, end_line: null, chars: 28, sha256: "a".repeat(64) },
    { kind: "claim_statement", claim_id: cid(40), file: "web/src/TaskForm.tsx", start_line: 12, end_line: 12, chars: 27, sha256: "b".repeat(64) },
    { kind: "question", claim_id: null, file: null, start_line: null, end_line: null, chars: 19, sha256: "c".repeat(64) },
  ],
};

// ---------------------------------------------------------------- history (docs/contracts/history.md section 6)
const C1 = "1".repeat(40);
const C2 = "2".repeat(40);
const C3 = "3".repeat(40);
const C0 = "0".repeat(40);
export const HISTORY_SHAS = { C1, C2, C3 } as const;

type Summary = Schemas["ClaimSummary"];
const hs = (n: number, s: Omit<Summary, "claim_id" | "flags"> & { flags?: string[] }): Summary => ({ claim_id: cid(100 + n), flags: [], ...s });
const cite = (commit: string, paths: { path: string; status: string; old_path?: string; similarity?: number }[] = [], pr?: number) => ({
  commit,
  parents: [C0],
  paths: paths.map((p) => ({ old_path: null, similarity: null, blob_before: "a".repeat(40), blob_after: "b".repeat(40), ...p })),
  ...(pr ? { pr: { number: pr, merge_commit_sha: commit, fetched_at: "2026-10-21T10:00:00+05:30" } } : {}),
});
const params = (values: Record<string, unknown>) => ({ digest: "d".repeat(64), values });

/** Full records keyed by claim id, as GET .../claims/{claim_id} returns them (only the fields the history screens read). */
export const historyRecords: Record<string, Record<string, unknown>> = {};
function page(items: [Summary, Record<string, unknown>][], hidden_counts: Record<string, number> = {}): Schemas["ClaimPage"] {
  for (const [s, extra] of items) historyRecords[s.claim_id] = { schema_version: "traces-evidence/0.4", repo_sha: SHA, ...s, ...extra };
  return { items: items.map(([s]) => s), total: items.length, offset: 0, limit: 50, hidden_counts };
}
const renameParams = params({ rename_threshold: 50, copy_threshold: 50, rename_limit: 10000 });

export const timelineSample = page(
  [
    [hs(1, { claim_kind: "relationship", kind: "commit_modifies", status: "observed", label: "observed", class: "git_object_fact", evidence_scope: "history", statement: `Commit ${C1.slice(0, 12)} modified api/tasks.py (+12 -3).`, qualifier: "git tree change", from_symbol: `commit::${C1}`, to_symbol: "file::api/tasks.py" }), { citations: [cite(C1, [{ path: "api/tasks.py", status: "M" }])], parameters: renameParams }],
    [hs(2, { claim_kind: "relationship", kind: "renamed_to", status: "observed", label: "observed", class: "git_object_fact", evidence_scope: "history", statement: `Commit ${C2.slice(0, 12)} renamed src/tasks.py to api/tasks.py (Git similarity 87%).`, qualifier: "similarity rename, score 87%", flags: ["similarity_rename"], from_symbol: "file::src/tasks.py", to_symbol: "file::api/tasks.py" }), { citations: [cite(C2, [{ path: "api/tasks.py", old_path: "src/tasks.py", status: "R", similarity: 87 }])], parameters: renameParams }],
    [hs(3, { claim_kind: "relationship", kind: "documents_rationale", status: "observed", label: "observed", class: "documented_rationale", evidence_scope: "documented", statement: 'PR #12 description says: "Move the task API under api/ so the client can be generated."', qualifier: "quoted rationale, not proof of intent", from_symbol: "repo::example/app#12", to_symbol: `commit::${C2}` }), { citations: [cite(C2, [], 12)] }],
    [hs(4, { claim_kind: "relationship", kind: "alias_of", status: "unvalidated", label: "inferred", class: "history_inferred", evidence_scope: "history", statement: "Suggested alias: content of api/crud/tasks.py appears to continue in api/crud.py.", qualifier: null, from_symbol: "file::api/crud/tasks.py", to_symbol: "file::api/crud.py" }), { citations: [cite(C3, [{ path: "api/crud.py", status: "A" }])], review_state: { state: "none", reviewer: null, at: null }, metrics: { line_set_jaccard: 0.62 } }],
    [hs(5, { claim_kind: "relationship", kind: "reverts", status: "rejected", label: "rejected", class: "history_inferred", evidence_scope: "history", statement: "A rejected revert match.", qualifier: null, from_symbol: `commit::${C3}`, to_symbol: `commit::${C1}` }), { citations: [cite(C3)] }],
  ],
  { unvalidated: 2 },
);

const hotspotParams = params({ bot_filter: "default", generated_filter: "default", max_changeset_size: 30, complexity: "indentation proxy" });
export const hotspotsSample = page(
  ["api/tasks.py", "web/src/TaskList.tsx", "web/src/client.ts"].map((f, i) => [
    hs(10 + i, { claim_kind: "node", kind: "file_history_metrics", status: "observed", label: "observed", class: "history_pattern", evidence_scope: "history", statement: `${f}: ${30 - i * 8} revisions, hotspot score ${(0.9 - i * 0.3).toFixed(2)}.`, qualifier: "history pattern; complexity is an indentation proxy", flags: ["complexity_proxy"], from_symbol: `file::${f}`, to_symbol: null }),
    { citations: [cite(C1, [{ path: f, status: "M" }]), cite(C2, [{ path: f, status: "M" }])], parameters: hotspotParams, metrics: { hotspot_score: Number((0.9 - i * 0.3).toFixed(4)), revisions: 30 - i * 8, churn: 1200 - i * 400, authors: 4 - i } },
  ]),
);

const coParams = params({ min_revs: 5, min_shared_revs: 5, min_coupling: 0.3, max_changeset_size: 30, bot_filter: "default", generated_filter: "default", rename_normalization: "head_paths" });
export const cochangeSample = page([
  [hs(20, { claim_kind: "relationship", kind: "co_changed_with", status: "observed", label: "observed", class: "history_pattern", evidence_scope: "history", statement: "TaskForm.tsx and TaskEdit.tsx changed together in 18 of 19 commits that touched either file. This is a history pattern, not evidence that one change caused the other.", qualifier: "changed together in 18 of 19 commits", from_symbol: "file::web/src/TaskForm.tsx", to_symbol: "file::web/src/TaskEdit.tsx" }), { citations: [cite(C1, [{ path: "web/src/TaskForm.tsx", status: "M" }, { path: "web/src/TaskEdit.tsx", status: "M" }])], parameters: coParams, metrics: { support: 18, revs_a: 19, revs_b: 19, union_commits: 19, degree: 0.95 } }],
  [hs(21, { claim_kind: "relationship", kind: "co_changed_with", status: "observed", label: "observed", class: "history_pattern", evidence_scope: "history", statement: "api/tasks.py and api/models.py changed together in 6 of 15 commits that touched either file. This is a history pattern, not evidence that one change caused the other.", qualifier: "changed together in 6 of 15 commits", from_symbol: "file::api/tasks.py", to_symbol: "file::api/models.py" }), { citations: [cite(C2, [{ path: "api/tasks.py", status: "M" }, { path: "api/models.py", status: "M" }])], parameters: coParams, metrics: { support: 6, revs_a: 10, revs_b: 11, union_commits: 15, degree: 0.5714 } }],
]);

export const milestonesSample = page(
  [C1, C2].map((c, i) => [
    hs(30 + i, { claim_kind: "node", kind: "milestone", status: "observed", label: "observed", class: "history_pattern", evidence_scope: "history", statement: `Milestone ${c.slice(0, 12)}.`, qualifier: i === 0 ? "selected milestone: first commit" : "selected milestone: bulk move, dependency added", from_symbol: `commit::${c}`, to_symbol: null }),
    { citations: [cite(c)], parameters: params({ max_milestones: 8, first_parent: true }) },
  ]),
);

export const compareSample = page([
  [hs(40, { claim_kind: "relationship", kind: "snapshot_added", status: "observed", label: "observed", class: "snapshot_diff", evidence_scope: "history", statement: `The relationship TaskList renders TaskItem is present at ${C2.slice(0, 12)} and absent at ${C1.slice(0, 12)}.`, qualifier: `present at ${C2.slice(0, 12)}, absent at ${C1.slice(0, 12)}`, from_symbol: `commit::${C1}`, to_symbol: `commit::${C2}` }), { citations: [cite(C2)], metrics: { underlying_status_a: null, underlying_status_b: "verified" } }],
  [hs(41, { claim_kind: "relationship", kind: "snapshot_removed", status: "observed", label: "observed", class: "snapshot_diff", evidence_scope: "history", statement: `The relationship TaskList calls oldFetch is present at ${C1.slice(0, 12)} and absent at ${C2.slice(0, 12)}.`, qualifier: `present at ${C1.slice(0, 12)}, absent at ${C2.slice(0, 12)}`, from_symbol: `commit::${C1}`, to_symbol: `commit::${C2}` }), { citations: [cite(C1)] }],
]);
