import type { TraceResponse } from "../../api/client";
import { splitSymbol } from "../../api/record";
import { HiddenCounts } from "../../ui/HiddenCounts";
import { Button } from "../../ui/States";
import { StatusChip } from "../../ui/StatusChip";
import { orderedHops, traceSummary, type HopView } from "./traceModel";

function Sym({ id }: { id: string }) {
  const s = splitSymbol(id);
  return (
    <span className="min-w-0">
      <code className="break-all font-semibold">{s.name}</code>
      {s.file ? <span className="block break-all font-mono text-xs text-muted">{s.file}</span> : null}
    </span>
  );
}

const RAIL: Record<HopView["kind"], string> = {
  edge: "bg-verified",
  hidden: "bg-line-strong",
  gap: "bg-inferred",
  library_contract: "bg-unknown",
};

const FRAME: Record<HopView["kind"], string> = {
  edge: "border-line bg-surface",
  hidden: "border-dashed border-line-strong bg-sunken",
  gap: "border-2 border-dashed border-inferred bg-inferred-soft",
  library_contract: "border-2 border-dotted border-inferred bg-surface",
};

function Hop({ v, onEvidence, last }: { v: HopView; onEvidence: (id: string) => void; last: boolean }) {
  const { hop } = v;
  const card =
    v.kind === "hidden" ? (
      <div className={`rounded-lg border p-3 text-sm text-ink-2 ${FRAME.hidden}`}>
        <span className="font-semibold">Step {hop.index + 1}: hidden.</span> A rejected relationship sits here. It is shown only in the reviewer view.
      </div>
    ) : (
      <div className={`rounded-lg border p-3 ${FRAME[v.kind]}`}>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-muted">Step {hop.index + 1}</span>
          <span className={`text-sm font-semibold ${v.kind === "edge" ? "" : "text-inferred"}`}>{v.title}</span>
          <StatusChip status={v.kind === "edge" ? hop.status : v.labelMismatch || !hop.status ? "unvalidated" : hop.status} label={v.kind === "edge" ? hop.label : "inferred"} qualifier={hop.qualifier} />
        </div>
        <div className="mt-2 grid grid-cols-[1fr] gap-1 text-sm sm:grid-cols-[1fr_auto_1fr] sm:items-start sm:gap-3">
          <Sym id={hop.from_symbol} />
          <span className="text-muted" aria-label={`then ${hop.kind}`}>
            <span aria-hidden="true">→ </span>
            {hop.kind}
          </span>
          <Sym id={hop.to_symbol} />
        </div>
        {v.kind !== "edge" ? (
          <p className="mt-2 text-sm" data-testid="hop-reason">
            <span className="font-semibold">Why this is inferred: </span>
            {v.reason ?? <span className="text-unknown">The API gave no reason, which the contract requires for this step.</span>}
          </p>
        ) : null}
        {v.labelMismatch ? (
          <p className="mt-1 text-xs text-unknown" role="note">
            The API labelled this step "{hop.label}". Gap and library contract steps are always inferred, so it is shown as Inferred.
          </p>
        ) : null}
        {v.claimId ? (
          <Button className="mt-2" onClick={() => onEvidence(v.claimId!)}>
            Open evidence
          </Button>
        ) : v.kind === "gap" ? (
          <p className="mt-2 text-xs text-ink-2">No claim backs this step, so there is no evidence to open.</p>
        ) : null}
      </div>
    );
  return (
    <li className="grid grid-cols-[1rem_minmax(0,1fr)] gap-3" data-hop={v.kind}>
      <div className="flex flex-col items-center pt-4" aria-hidden="true">
        <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${RAIL[v.kind]}`} />
        {last ? null : <span className={`mt-1 w-px flex-1 ${RAIL[v.kind]} opacity-60`} />}
      </div>
      <div className="mb-2 min-w-0">{card}</div>
    </li>
  );
}

/** Renders a TraceResponse as an ordered list. Gaps and library contract steps are their own, visibly different, items. */
export function TraceView({ t, reviewHref, onEvidence }: { t: TraceResponse; reviewHref: string; onEvidence: (claimId: string) => void }) {
  const s = traceSummary(t);
  const hops = orderedHops(t);
  return (
    <section aria-label="Trace result" data-testid="trace">
      <div className="mb-3 flex flex-col gap-2 rounded-lg border border-line bg-surface p-3">
        <p className="text-sm">
          From <code className="break-all">{splitSymbol(t.from_symbol).name}</code>
          {t.to_symbol ? (
            <>
              {" "}
              to <code className="break-all">{splitSymbol(t.to_symbol).name}</code>
            </>
          ) : null}
          : {s.total} steps, {s.edges} relationships, {s.library} library contract, {s.gaps} gaps
          {s.hidden ? `, ${s.hidden} hidden` : ""}.
        </p>
        {t.complete ? (
          <p className="text-sm text-ink-2" data-testid="trace-complete">
            Complete: every step is backed by a recorded relationship.
          </p>
        ) : (
          <p className="text-sm font-semibold text-inferred" role="note" data-testid="trace-incomplete">
            Incomplete: this trace has gaps. Gaps are steps where no relationship was recorded; they are inferred, not observed.
          </p>
        )}
        <p className="text-xs text-muted">{t.disclaimer}</p>
        <HiddenCounts counts={t.hidden_counts} reviewHref={reviewHref} />
      </div>
      {hops.length === 0 ? (
        <p className="text-sm text-ink-2">The API returned no steps for this trace.</p>
      ) : (
        <>
          <ol className="flex flex-col" aria-label="Trace steps in order" data-testid="trace-rail">
            {hops.map((v, i) => (
              <Hop key={`${v.hop.index}-${v.hop.from_symbol}-${v.hop.to_symbol}`} v={v} last={i === hops.length - 1} onEvidence={onEvidence} />
            ))}
          </ol>
        </>
      )}
    </section>
  );
}
