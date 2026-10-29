import { Link, useParams } from "react-router-dom";
import { snapshotBase } from "../../app/nav";
import { recordedQuestion } from "../ask/recordedQuestion";
import { subjectKindLabel, subjectLabel, withAt, type Subject } from "./subject";
import { useSubject } from "./useSubject";

function askFor(base: string, s: Subject): string | null {
  if (s.kind === "route") {
    if (!s.method || s.method === "UNKNOWN" || s.method === "USE" || !s.path.startsWith("/")) return null;
    return withAt(`${base}/ask?q=${encodeURIComponent(`What does ${s.method} ${s.path} do?`)}`, s);
  }
  const name = s.kind === "file" ? s.path : s.kind === "symbol" ? s.id : "";
  const q = recordedQuestion(name);
  return q ? withAt(`${base}/ask?q=${encodeURIComponent(q)}`, s) : null;
}

function traceFor(base: string, s: Subject): string | null {
  const from = s.kind === "symbol" ? s.id : s.kind === "route" ? s.handler : "";
  if (!from) return null;
  return withAt(`${base}/trace?from=${encodeURIComponent(from)}`, s);
}

function mapFor(base: string, s: Subject): string {
  if (s.kind === "component" || (s.kind === "symbol" && s.id.includes("::"))) return withAt(`${base}/graph?focus=${encodeURIComponent(s.id)}`, s);
  if (s.kind === "route" && s.handler) return withAt(`${base}/graph?focus=${encodeURIComponent(s.handler)}`, s);
  const q = s.kind === "file" ? s.path.split("/").pop() || s.path : s.kind === "route" ? s.path : s.label;
  return withAt(`${base}/graph?q=${encodeURIComponent(q)}`, s);
}

/** One selected thing, carried across the snapshot. Clearing it does not delete evidence. */
export function LookingBar() {
  const { repoId = "", sha = "" } = useParams();
  const base = snapshotBase(repoId, sha);
  const { subject, setSubject } = useSubject();
  if (!subject) {
    return (
      <p className="mb-3 text-[13px] text-muted" data-testid="looking-empty">
        Nothing selected. Choose a component on the map, or a route on Trace. It stays selected on the other pages.
      </p>
    );
  }
  const trace = traceFor(base, subject);
  const ask = askFor(base, subject);
  return (
    <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-2 border-y border-white/10 py-2" data-testid="looking-at" aria-label="Selected subject">
      <span className="min-w-0">
        <span className="block text-[11px] uppercase tracking-[0.14em] text-muted">{subjectKindLabel(subject)}</span>
        <span className="block truncate font-mono text-[15px] text-ink">{subjectLabel(subject)}</span>
      </span>
      <span className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
        <Link to={mapFor(base, subject)}>On the map</Link>
        {trace ? <Link to={trace}>Trace this</Link> : null}
        {ask ? <Link to={ask}>Ask about this</Link> : null}
        <button type="button" className="min-h-8 text-muted hover:text-ink" onClick={() => setSubject(null)}>
          Clear
        </button>
      </span>
    </div>
  );
}
