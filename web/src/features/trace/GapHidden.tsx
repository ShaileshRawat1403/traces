import { Link } from "react-router-dom";
import type { TraceHop } from "../../api/client";
import { gapHiddenNote, stepHiddenRejected, stepHiddenText } from "./traceModel";

/**
 * Hidden rejected claims at a gap. When the API gives a per-step count (hidden_rejected) it is shown for this step with
 * a link to the reviewer view; zero says nothing. Without a per-step count, the snapshot-wide note is kept.
 */
export function GapHidden({ hop, snapshotHidden, reviewHref }: { hop: TraceHop; snapshotHidden: Record<string, number> | null | undefined; reviewHref: string }) {
  const n = stepHiddenRejected(hop);
  if (n !== null) {
    if (n === 0) return null;
    return (
      <p className="flow-span text-sm text-ink-2" data-testid="gap-hidden-step">
        {stepHiddenText(n)}{" "}
        <Link to={reviewHref} className="tap-sm inline-flex">
          Open the reviewer view
        </Link>
      </p>
    );
  }
  const note = gapHiddenNote(snapshotHidden);
  return note ? (
    <p className="flow-span text-sm text-ink-2" data-testid="gap-hidden">
      {note}
    </p>
  ) : null;
}
