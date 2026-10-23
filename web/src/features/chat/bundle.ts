// Reading the backend's prompt bundle (backend/traces/explain/engine.py, format traces-bundle/1) and rebuilding the prompt
// when the user removes evidence items. The rebuild must reproduce the server prompt exactly when nothing is removed;
// if it does not, removal is disabled and the server prompt is sent verbatim.
import type { ExplainResponse, OutboundItem } from "../../api/client";

export interface EvidenceItem {
  claim_id: string;
  status: string;
  label: string;
  where: string;
  statement: string;
}

export interface Bundle {
  format: string | null;
  instructions: string;
  evidence: EvidenceItem[];
  question: string;
  prompt: string;
  /** True when assemblePrompt(all evidence) equals the server prompt, so removal is safe. */
  rebuildable: boolean;
  /** Rejected claims the server included by mistake. They are stripped before anything is shown or sent. */
  rejectedDropped: number;
}

/** Rejected claims are never used (charter, CONTRACTS.md). Status, not label, decides. */
export const isRejected = (e: Pick<EvidenceItem, "status" | "label">) => e.status === "rejected" || e.label.toLowerCase() === "rejected";

const str = (v: unknown): v is string => typeof v === "string";

/** Parse the server bundle. Returns null when there is nothing safe to send: no prompt, or rejected claims that cannot be
 * removed because the browser cannot rebuild the prompt exactly. */
export function readBundle(r: ExplainResponse): Bundle | null {
  const pb = r.prompt_bundle as Record<string, unknown> | null | undefined;
  if (!pb || !str(pb.prompt)) return null;
  const evidence: EvidenceItem[] = Array.isArray(pb.evidence)
    ? (pb.evidence as Record<string, unknown>[])
        .filter((e) => e && str(e.claim_id))
        .map((e) => ({ claim_id: e.claim_id as string, status: String(e.status ?? ""), label: String(e.label ?? ""), where: String(e.where ?? ""), statement: String(e.statement ?? "") }))
    : [];
  const b: Bundle = {
    format: str(pb.format) ? pb.format : null,
    instructions: str(pb.instructions) ? pb.instructions : "",
    evidence,
    question: str(pb.question) ? pb.question : "",
    prompt: pb.prompt,
    rebuildable: false,
    rejectedDropped: 0,
  };
  b.rebuildable = evidence.length > 0 && assemblePrompt(b, new Set()) === b.prompt;
  const rejected = evidence.filter(isRejected);
  if (rejected.length) {
    if (!b.rebuildable) return null;
    b.evidence = evidence.filter((e) => !isRejected(e));
    b.prompt = assemblePrompt(b, new Set());
    b.rejectedDropped = rejected.length;
  }
  return b;
}

export const evidenceLine = (e: EvidenceItem) => `[${e.claim_id}] (${e.label}, ${e.where}) ${e.statement}`;

export function assemblePrompt(b: Pick<Bundle, "instructions" | "evidence" | "question">, removed: ReadonlySet<string>): string {
  const lines = [b.instructions, "", "<evidence>"];
  for (const e of b.evidence) if (!removed.has(e.claim_id)) lines.push(evidenceLine(e));
  lines.push("</evidence>", "", "<question>", b.question, "</question>");
  return lines.join("\n");
}

/** The prompt that will be sent and the claim ids it contains. */
export function outgoing(b: Bundle, removed: ReadonlySet<string>): { prompt: string; claimIds: string[] } {
  if (!b.rebuildable || removed.size === 0) return { prompt: b.prompt, claimIds: b.evidence.map((e) => e.claim_id) };
  return { prompt: assemblePrompt(b, removed), claimIds: b.evidence.filter((e) => !removed.has(e.claim_id)).map((e) => e.claim_id) };
}

export function keptManifest(m: readonly OutboundItem[], removed: ReadonlySet<string>): OutboundItem[] {
  return m.filter((i) => !(i.kind === "claim_statement" && i.claim_id && removed.has(i.claim_id)));
}
