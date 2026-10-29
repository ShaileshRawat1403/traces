// Defensive reading of a traces-evidence/0.4 record (GET .../claims/{claim_id}).
// The OpenAPI response is an open object, so every field is checked before use and unknown shapes are shown raw.

export interface RecordEndpoint {
  symbol: string;
  file?: string;
  start_line?: number;
  end_line?: number;
}
export interface RecordLocation {
  file: string;
  start_line: number;
  end_line: number;
  range_kind?: string;
  role?: string;
  source?: string;
  blob_sha?: string;
}
export interface RecordCheck {
  check_id: string;
  method: string;
  establishes?: string;
  rule_id?: string | null;
  independent?: boolean;
  result?: string;
  detail?: string;
  validator?: { name?: string; version?: string; family?: string };
}
export interface RecordHistoryItem {
  from: string | null;
  to: string;
  at?: string;
  by?: string;
  run_id?: string;
}
export interface RecordCitation {
  commit?: string;
  pr?: unknown;
  paths?: unknown[];
}
export interface EvidenceRecordView {
  claim_id: string;
  statement: string;
  status: string;
  label: string;
  claim_kind: string;
  kind: string | null;
  class: string;
  evidence_scope: string;
  qualifier: string | null;
  status_reason: string | null;
  flags: string[];
  repo_sha: string;
  run_id: string | null;
  schema_version: string | null;
  provenance: string | null;
  originator: { name?: string; version?: string; role?: string } | null;
  injected: boolean;
  from: RecordEndpoint | null;
  to: RecordEndpoint | null;
  locations: RecordLocation[];
  checks: RecordCheck[];
  status_history: RecordHistoryItem[];
  citations: RecordCitation[];
  consolidation: { rule?: string; count?: number; members?: unknown[] } | null;
  raw: Record<string, unknown>;
}

type Obj = Record<string, unknown>;
const isObj = (v: unknown): v is Obj => typeof v === "object" && v !== null && !Array.isArray(v);
const str = (v: unknown): string | null => (typeof v === "string" ? v : null);
const num = (v: unknown): number | undefined => (typeof v === "number" && Number.isFinite(v) ? v : undefined);
const arr = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);

function endpoint(v: unknown): RecordEndpoint | null {
  if (!isObj(v) || typeof v.symbol !== "string") return null;
  return { symbol: v.symbol, file: str(v.file) ?? undefined, start_line: num(v.start_line), end_line: num(v.end_line) };
}

export function readRecord(raw: unknown): EvidenceRecordView {
  if (!isObj(raw) || typeof raw.claim_id !== "string") throw new Error("The API returned a claim record without a claim_id.");
  const locations: RecordLocation[] = [];
  for (const l of arr(raw.locations)) {
    if (isObj(l) && typeof l.file === "string" && num(l.start_line) !== undefined && num(l.end_line) !== undefined)
      locations.push({
        file: l.file,
        start_line: l.start_line as number,
        end_line: l.end_line as number,
        range_kind: str(l.range_kind) ?? undefined,
        role: str(l.role) ?? undefined,
        source: str(l.source) ?? undefined,
        blob_sha: str(l.blob_sha) ?? undefined,
      });
  }
  const checks: RecordCheck[] = [];
  for (const c of arr(raw.checks)) {
    if (!isObj(c) || typeof c.check_id !== "string") continue;
    const v = isObj(c.validator) ? c.validator : null;
    checks.push({
      check_id: c.check_id,
      method: str(c.method) ?? "unknown",
      establishes: str(c.establishes) ?? undefined,
      rule_id: str(c.rule_id),
      independent: typeof c.independent === "boolean" ? c.independent : undefined,
      result: str(c.result) ?? undefined,
      detail: str(c.detail) ?? undefined,
      validator: v ? { name: str(v.name) ?? undefined, version: str(v.version) ?? undefined, family: str(v.family) ?? undefined } : undefined,
    });
  }
  const history: RecordHistoryItem[] = [];
  for (const h of arr(raw.status_history)) {
    if (isObj(h) && typeof h.to === "string")
      history.push({ from: str(h.from), to: h.to, at: str(h.at) ?? undefined, by: str(h.by) ?? undefined, run_id: str(h.run_id) ?? undefined });
  }
  const o = isObj(raw.originator) ? raw.originator : null;
  const cons = isObj(raw.consolidation) ? raw.consolidation : null;
  return {
    claim_id: raw.claim_id,
    statement: str(raw.statement) ?? "(no statement)",
    status: str(raw.status) ?? "unknown",
    label: str(raw.label) ?? "unknown",
    claim_kind: str(raw.claim_kind) ?? "unknown",
    kind: str(raw.relationship_kind) ?? str(raw.node_kind),
    class: str(raw.class) ?? "unknown",
    evidence_scope: str(raw.evidence_scope) ?? "unknown",
    qualifier: str(raw.qualifier),
    status_reason: str(raw.status_reason),
    flags: arr(raw.flags).filter((f): f is string => typeof f === "string"),
    repo_sha: str(raw.repo_sha) ?? "",
    run_id: str(raw.run_id),
    schema_version: str(raw.schema_version),
    provenance: str(raw.provenance),
    originator: o ? { name: str(o.name) ?? undefined, version: str(o.version) ?? undefined, role: str(o.role) ?? undefined } : null,
    injected: raw.injected === true,
    from: endpoint(raw.from),
    to: endpoint(raw.to),
    locations,
    checks,
    status_history: history,
    citations: arr(raw.citations).filter(isObj) as RecordCitation[],
    consolidation: cons ? { rule: str(cons.rule) ?? undefined, count: num(cons.count), members: arr(cons.members) } : null,
    raw,
  };
}

/** Symbols are "<file>::<name>"; show the name, keep the file for context. */
export function splitSymbol(symbol: string): { file: string | null; name: string } {
  const i = symbol.indexOf("::");
  if (i < 0) return { file: null, name: symbol };
  const file = symbol.slice(0, i);
  const name = symbol.slice(i + 2);
  return { file, name: name === file ? (file.split("/").pop() ?? file) : name };
}
