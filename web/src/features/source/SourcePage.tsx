import { useQuery } from "@tanstack/react-query";
import { useId, useState, type FormEvent } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { api } from "../../api/client";
import { Button, Empty, ErrorState, Loading, PageHeader } from "../../ui/States";
import { EvidenceDrawer } from "../evidence/EvidenceDrawer";
import { SourceLinesView } from "./SourceLines";
import { tokenize } from "./highlight";
import { useDrawerClaim } from "../inventory/useDrawer";

const CLAIMS_SHOWN = 30;
/** The API serves at most 400 lines per request (MAX_SOURCE_LINES), so the file is read in windows of that size. */
export const WINDOW = 400;

export function windowFor(from: number | undefined, highlightStart: number | undefined): { start: number; end: number } {
  const start = Math.max(1, from ?? (highlightStart ? highlightStart - 50 : 1));
  return { start, end: start + WINDOW - 1 };
}

/** Read-only file view at the pinned commit. Text only; the API caps size and says when it shortened the file. */
export function SourcePage() {
  const { repoId = "", sha = "" } = useParams();
  const [sp, setSp] = useSearchParams();
  const path = sp.get("path") ?? "";
  const start = Number(sp.get("start")) || undefined;
  const end = Number(sp.get("end")) || undefined;
  const [claim, setClaim, opener] = useDrawerClaim();
  const win = windowFor(Number(sp.get("from")) || undefined, start);
  const [draft, setDraft] = useState(path);
  const pid = useId();
  const q = useQuery({ queryKey: ["source", repoId, sha, path, win.start, win.end], queryFn: () => api.source(repoId, sha, path, win.start, win.end), enabled: !!path });
  const tok = useQuery({ queryKey: ["tokens-file", repoId, sha, path, win.start], queryFn: () => tokenize(q.data!.lines, q.data!.path), enabled: !!q.data, staleTime: Infinity, retry: false });
  const setParam = (k: string, v: string | null) => {
    const n = new URLSearchParams(sp);
    if (v) n.set(k, v);
    else n.delete(k);
    setSp(n);
  };
  const open = (e: FormEvent) => {
    e.preventDefault();
    const n = new URLSearchParams();
    if (draft.trim()) n.set("path", draft.trim().replace(/^\/+/, ""));
    setSp(n);
  };
  const hl = start ? { start, end: end ?? start } : { start: 0, end: -1 };
  return (
    <>
      <PageHeader title="Source at the pinned commit">Read a tracked file exactly as it is at this snapshot's commit. Nothing here is run.</PageHeader>
      <form onSubmit={open} className="mb-3 flex flex-wrap items-end gap-2 rounded-lg border border-line bg-surface p-3">
        <label htmlFor={pid} className="flex min-w-0 flex-1 flex-col gap-1 text-sm">
          <span className="font-medium">File path</span>
          <input id={pid} value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="path/to/file.py" className="tap rounded-md border border-line-strong px-2 font-mono text-sm" autoComplete="off" spellCheck={false} />
        </label>
        <Button type="submit" variant="primary" disabled={!draft.trim()}>
          Open file
        </Button>
      </form>
      {!path ? (
        <Empty title="No file selected">Enter a path, or open a file from Components, Routes or a claim's locations.</Empty>
      ) : q.isPending ? (
        <Loading label="Loading source" />
      ) : q.isError ? (
        <ErrorState error={q.error} what="Source view" />
      ) : (
        <div className="flex flex-col gap-3" data-testid="source-page">
          <SourceLinesView v={q.data} highlight={hl} requested={win} tokens={tok.data} />
          {q.data.start_line > 1 || q.data.end_line < q.data.total_lines ? (
            <nav className="flex flex-wrap gap-2" aria-label="Move through the file">
              {q.data.start_line > 1 ? <Button onClick={() => setParam("from", String(Math.max(1, q.data.start_line - WINDOW)))}>Previous {WINDOW} lines</Button> : null}
              {q.data.end_line < q.data.total_lines ? <Button onClick={() => setParam("from", String(q.data.end_line + 1))}>Next {WINDOW} lines</Button> : null}
            </nav>
          ) : null}
          {start ? (
            <p className="text-sm text-ink-2">
              Lines {hl.start} to {hl.end} are highlighted because the link that opened this file pointed at them.
            </p>
          ) : null}
          <section aria-label="Claims in this file" className="rounded-lg border border-line bg-surface p-3">
            <h2 className="text-sm font-semibold">Claims with a location in these lines ({q.data.claim_ids.length})</h2>
            <p className="mt-1 text-xs text-muted">Any status. The evidence drawer shows each claim's label; rejected claims are labelled Rejected there and are never drawn as architecture.</p>
            {q.data.claim_ids.length === 0 ? (
              <p className="mt-1 text-sm text-muted">No claim has a location in these lines.</p>
            ) : (
              <ul className="mt-2 flex flex-wrap gap-2">
                {q.data.claim_ids.slice(0, CLAIMS_SHOWN).map((id) => (
                  <li key={id}>
                    <Button onClick={() => setClaim(id)} aria-label={`Open evidence for claim ${id.slice(0, 10)}`}>
                      <span className="font-mono text-xs">{id.slice(0, 10)}</span>
                    </Button>
                  </li>
                ))}
              </ul>
            )}
            {q.data.claim_ids.length > CLAIMS_SHOWN ? <p className="mt-1 text-xs text-muted">and {q.data.claim_ids.length - CLAIMS_SHOWN} more.</p> : null}
          </section>
        </div>
      )}
      <EvidenceDrawer repoId={repoId} sha={sha} claimId={claim} onClose={() => setClaim(null)} returnFocus={opener} />
    </>
  );
}
