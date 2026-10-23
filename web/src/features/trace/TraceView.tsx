import type { TraceResponse } from "../../api/client";
import { splitSymbol } from "../../api/record";
import { HiddenCounts } from "../../ui/HiddenCounts";
import { Button } from "../../ui/States";
import { StatusChip } from "../../ui/StatusChip";
import { GapHidden } from "./GapHidden";
import { GAP_MEANING, orderedHops, traceSummary, type HopView } from "./traceModel";

function Sym({ id }: { id: string }) {
  const s = splitSymbol(id);
  return (
    <span className="min-w-0">
      <code className="break-all font-semibold">{s.name}</code>
      {s.file ? <span className="block break-all font-mono text-xs text-muted">{s.file}</span> : null}
    </span>
  );
}

function Hop({ v, onEvidence, snapshotHidden, reviewHref }: { v: HopView; onEvidence: (id: string) => void; snapshotHidden: Record<string, number> | null | undefined; reviewHref: string }) {
  const { hop } = v;
  return (
    <li className="flow-hop" data-hop={v.kind}>
      {v.kind === "hidden" ? (
        <div className="flow-span text-sm text-ink-2">
          <span className="font-semibold">Step {hop.index + 1}: hidden.</span> A rejected relationship sits here. It is shown only in the reviewer view.
        </div>
      ) : (
        <>
          <div className="flow-node">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted">From</span>
            <Sym id={hop.from_symbol} />
          </div>
          <div className="flow-join">
            <span className={`font-semibold ${v.kind === "edge" ? "text-ink" : "text-inferred"}`}>{v.title}</span>
            <span>
              {hop.kind}
              {v.kind === "edge" ? "" : " · inferred"}
            </span>
          </div>
          <div className="flow-node">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted">To</span>
            <Sym id={hop.to_symbol} />
          </div>
          <div className="flow-span flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted">Step {hop.index + 1}</span>
            <StatusChip status={v.kind === "edge" ? hop.status : v.labelMismatch || !hop.status ? "unvalidated" : hop.status} label={v.kind === "edge" ? hop.label : "inferred"} qualifier={hop.qualifier} />
          </div>
          {v.kind !== "edge" ? (
            v.kind === "gap" ? (
              <div className="flow-span flex flex-col gap-1 text-sm" data-testid="hop-reason">
                <p data-testid="gap-meaning">
                  <span className="font-semibold">What this gap means: </span>
                  {GAP_MEANING}
                </p>
                <GapHidden hop={hop} snapshotHidden={snapshotHidden} reviewHref={reviewHref} />
                <p className="text-ink-2">
                  <span className="font-semibold">API note: </span>
                  {v.reason ?? <span className="text-unknown">The API gave no reason, which the contract requires for this step.</span>}
                </p>
              </div>
            ) : (
              <p className="flow-span text-sm" data-testid="hop-reason">
                <span className="font-semibold">Why this is inferred: </span>
                {v.reason ?? <span className="text-unknown">The API gave no reason, which the contract requires for this step.</span>}
              </p>
            )
          ) : null}
          {v.labelMismatch ? (
            <p className="flow-span text-xs text-unknown" role="note">
              The API labelled this step "{hop.label}". Gap and library contract steps are always inferred, so it is shown as Inferred.
            </p>
          ) : null}
          {v.claimId ? (
            <div className="flow-span">
              <Button onClick={() => onEvidence(v.claimId!)}>Open evidence</Button>
            </div>
          ) : v.kind === "gap" ? (
            <p className="flow-span text-xs text-ink-2">No claim backs this step, so there is no evidence to open.</p>
          ) : null}
        </>
      )}
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
            Incomplete: this trace has gaps. A gap is a step that no accepted static evidence connects. It is not evidence that a call does or does not happen.
          </p>
        )}
        <p className="text-xs text-muted">{t.disclaimer}</p>
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2" aria-label="How to read the flow">
          <li>Solid border: a recorded relationship.</li>
          <li>Dotted border: inferred library step.</li>
          <li>Dashed border: a gap, no accepted static evidence.</li>
        </ul>
        <HiddenCounts counts={t.hidden_counts} reviewHref={reviewHref} />
      </div>
      {hops.length === 0 ? (
        <p className="text-sm text-ink-2">The API returned no steps for this trace.</p>
      ) : (
        <>
          <ol className="flow-list" aria-label="Trace steps in order" data-testid="trace-rail">
            {hops.map((v) => (
              <Hop key={`${v.hop.index}-${v.hop.from_symbol}-${v.hop.to_symbol}`} v={v} onEvidence={onEvidence} snapshotHidden={t.hidden_counts} reviewHref={reviewHref} />
            ))}
          </ol>
        </>
      )}
    </section>
  );
}
