import { useQuery } from "@tanstack/react-query";
import type { ThemedToken } from "shiki/core";
import { api, type SourceView } from "../../api/client";
import { ErrorState, Loading } from "../../ui/States";
import { tokenize } from "./highlight";

/** Facts about the returned window that the UI states plainly (no guessing beyond the response). */
export function windowFacts(v: SourceView, requested: { start: number; end: number }) {
  const shortened = v.end_line < Math.min(requested.end, v.total_lines);
  return { shortened, of: v.total_lines, from: v.start_line, to: v.end_line };
}

function Line({ n, hit, text, tokens }: { n: number; hit: boolean; text: string; tokens: ThemedToken[] | undefined }) {
  return (
    <span className={`flex ${hit ? "bg-hit" : ""}`} data-hit={hit || undefined}>
      <span className={`w-12 shrink-0 select-none border-r pr-2 text-right ${hit ? "border-accent font-semibold text-ink" : "border-line text-muted"}`} aria-hidden="true">
        {n}
      </span>
      <span className="whitespace-pre pl-3 pr-3">
        {tokens
          ? tokens.map((t, i) => (
              <span key={i} style={{ color: t.color }}>
                {t.content}
              </span>
            ))
          : text}
      </span>
    </span>
  );
}

/** Renders a SourceView: pinned path, blob, total lines, highlighted range. Text only, never HTML. */
export function SourceLinesView({ v, highlight, requested, tokens }: { v: SourceView; highlight: { start: number; end: number }; requested: { start: number; end: number }; tokens?: ThemedToken[][] | null }) {
  const f = windowFacts(v, requested);
  return (
    <figure className="overflow-hidden rounded-md border border-line" data-testid="source-lines">
      <figcaption className="flex flex-wrap gap-x-3 gap-y-1 border-b border-line bg-sunken px-3 py-1 text-xs text-ink-2">
        <span className="break-all font-mono">{v.path}</span>
        <span>
          lines {f.from} to {f.to} of {f.of}
        </span>
        <span className="font-mono">@{v.sha.slice(0, 7)}</span>
        <span className="font-mono">blob {v.blob_sha.slice(0, 10)}</span>
        {v.generated ? <span className="font-semibold">generated file</span> : null}
        {f.shortened ? <span className="font-semibold text-inferred">shortened by the API size cap</span> : null}
      </figcaption>
      <pre className="max-h-96 overflow-auto bg-surface py-1 text-[13px] leading-5" tabIndex={0} aria-label={`Source of ${v.path}, lines ${f.from} to ${f.to}. Lines ${highlight.start} to ${highlight.end} are the evidence.`}>
        <code>
          {v.lines.map((text, i) => {
            const n = v.start_line + i;
            return <Line key={n} n={n} hit={n >= highlight.start && n <= highlight.end} text={text} tokens={tokens?.[i]} />;
          })}
        </code>
      </pre>
    </figure>
  );
}

/** Fetches lines around a location from the source endpoint and highlights them with Shiki. */
export function SourcePanel({ repoId, sha, file, start, end, context = 3 }: { repoId: string; sha: string; file: string; start: number; end: number; context?: number }) {
  const from = Math.max(1, start - context);
  const to = end + context;
  const q = useQuery({ queryKey: ["source", repoId, sha, file, from, to], queryFn: () => api.source(repoId, sha, file, from, to) });
  const tok = useQuery({
    queryKey: ["tokens", repoId, sha, file, from, to],
    queryFn: () => tokenize(q.data!.lines, q.data!.path),
    enabled: !!q.data,
    staleTime: Infinity,
    retry: false,
  });
  if (q.isPending) return <Loading label="Loading source" />;
  if (q.isError) return <ErrorState error={q.error} what="Source view" />;
  return <SourceLinesView v={q.data} highlight={{ start, end }} requested={{ start: from, end: to }} tokens={tok.data} />;
}
