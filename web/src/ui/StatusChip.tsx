import { presentStatus, type Context, type LineStyle, type StatusInput, type Tone } from "../status/status";

const TONE: Record<Tone, string> = {
  verified: "text-verified bg-verified-soft border-verified/40",
  observed: "text-observed bg-observed-soft border-observed/40",
  inferred: "text-inferred bg-inferred-soft border-inferred/50 border-dashed",
  rejected: "text-rejected bg-rejected-soft border-rejected/40",
  unknown: "text-unknown bg-unknown-soft border-unknown/40",
};

/** Small line sample matching the graph edge style, so the chip and the graph share one visual language. */
export function LineSample({ line, className = "" }: { line: LineStyle; className?: string }) {
  if (line === "none") return null;
  const dash = line === "dashed" ? "5 3" : line === "dotted" ? "1.5 3" : undefined;
  return (
    <svg width="18" height="8" viewBox="0 0 18 8" aria-hidden="true" className={className} data-line={line}>
      <line x1="1" y1="4" x2="17" y2="4" stroke="currentColor" strokeWidth={line === "thin" ? 1 : 2} strokeDasharray={dash} strokeLinecap="round" />
    </svg>
  );
}

export interface StatusChipProps extends StatusInput {
  context?: Context;
  /** Optional qualifier from the record (for example "statically established persistence path"). */
  qualifier?: string | null;
  className?: string;
}

/**
 * Renders the API's own label. In default contexts a rejected claim renders nothing: callers count it in HiddenCounts.
 */
export function StatusChip({ status, label, flags, context = "default", qualifier, className = "" }: StatusChipProps) {
  const p = presentStatus({ status, label, flags }, context);
  if (p.hidden) return null;
  return (
    <span className={`inline-flex flex-wrap items-center gap-1.5 ${className}`}>
      <span
        className={`inline-flex items-center gap-1.5 rounded-sm border px-1.5 py-0.5 text-xs font-semibold leading-none ${TONE[p.tone]}`}
        title={p.description}
        data-status={status ?? ""}
        data-label={label ?? ""}
        data-testid="status-chip"
      >
        <LineSample line={p.line} />
        <span>{p.text}</span>
        <span className="sr-only">. {p.description}</span>
      </span>
      {p.note ? (
        <span className={`text-xs ${p.inconsistent ? "font-semibold text-unknown" : "text-muted"}`} data-testid="status-note">
          {p.inconsistent ? "Warning: " : ""}
          {p.note}
        </span>
      ) : null}
      {qualifier ? (
        <span className="rounded-sm border border-line bg-sunken px-1.5 py-0.5 text-xs text-ink-2" data-testid="qualifier">
          {qualifier}
        </span>
      ) : null}
    </span>
  );
}
