import { Link } from "react-router-dom";
import type { ExplainResponse } from "../../api/client";
import { CitationLinks, StandingChip, factStanding } from "../../ui/Facts";
import { StatusChip } from "../../ui/StatusChip";

function Meter({ label, n, total, cls }: { label: string; n: number; total: number; cls: string }) {
  const pct = total === 0 ? 0 : Math.round((n / total) * 100);
  return (
    <div className="rounded-md border border-line bg-canvas px-2 py-1">
      <div className="flex justify-between gap-2 text-ink-2">
        <span>{label}</span>
        <span className="tabular-nums">{n}</span>
      </div>
      <span className="mt-1 block h-1.5 rounded bg-sunken">
        <span className={`block h-1.5 rounded ${cls}`} style={{ width: `${pct}%` }} />
      </span>
    </div>
  );
}

const CITE_CAP = 12;

const CATEGORY: Record<string, { title: string; help: string }> = {
  code_structure: { title: "Code structure", help: "Verified or observed static claims." },
  inference: { title: "Inference", help: "Claims that are not established." },
  documented_decisions: { title: "Documented decisions", help: "Statements from README, ADRs or docs." },
  history_patterns: { title: "History patterns", help: "Patterns from commit history." },
  runtime_observations: { title: "Runtime observations", help: "Always empty: Traces analyzes code statically." },
};
const CATEGORY_ORDER = ["code_structure", "inference", "documented_decisions", "history_patterns", "runtime_observations"];

/** Per-sentence standing as plain text for screen readers and for tests. */
export function sentenceStanding(f: ExplainResponse["answer"][number]): "grounded" | "interpretation" | "unknown" {
  const s = factStanding(f);
  return s === "uncited" ? "unknown" : s;
}

function Cites({ ids, base }: { ids: readonly string[]; base: string }) {
  if (ids.length <= CITE_CAP) return <CitationLinks claimIds={ids} base={base} />;
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      <CitationLinks claimIds={ids.slice(0, CITE_CAP)} base={base} />
      <span className="text-xs text-muted">and {ids.length - CITE_CAP} more, listed under Citations</span>
    </span>
  );
}

/** ExplainResponse renderer: the answer in order, each sentence tagged, then citations, categories and what a bundle would send. */
export function ExplainView({ r, base }: { r: ExplainResponse; base: string }) {
  const counts = { grounded: 0, interpretation: 0, unknown: 0 };
  for (const f of r.answer) counts[sentenceStanding(f)] += 1;
  const cats = [...CATEGORY_ORDER, ...Object.keys(r.categories).filter((k) => !CATEGORY_ORDER.includes(k))];
  return (
    <section aria-label="Answer" data-testid="explain">
      <div className="rounded-lg border border-line bg-surface p-4">
        <h2 className="text-base font-semibold">Answer</h2>
        <p className="mt-1 text-xs text-muted" data-testid="answer-summary">
          {counts.grounded} grounded, {counts.interpretation} interpretation, {counts.unknown} unknown. Built from evidence records without an AI model. Static analysis only.
        </p>
        <div className="mt-3 grid grid-cols-3 gap-2 text-xs" aria-hidden="true">
          <Meter label="Grounded" n={counts.grounded} total={r.answer.length} cls="bg-verified" />
          <Meter label="Interpretation" n={counts.interpretation} total={r.answer.length} cls="bg-inferred" />
          <Meter label="Unknown" n={counts.unknown} total={r.answer.length} cls="bg-unknown" />
        </div>
        <ol className="mt-3 flex flex-col gap-3">
          {r.answer.map((f, i) => (
            <li key={i} className="flex flex-col gap-1" data-standing={sentenceStanding(f)} data-testid="answer-sentence">
              <span className="flex flex-wrap items-center gap-2">
                <StandingChip fact={f} />
                <Cites ids={f.claim_ids ?? []} base={base} />
              </span>
              <span className={sentenceStanding(f) === "interpretation" ? "italic text-ink-2" : ""}>{f.text}</span>
            </li>
          ))}
        </ol>
      </div>

      <details className="mt-3 rounded-lg border border-line bg-surface" data-testid="citations">
        <summary className="tap flex cursor-pointer items-center px-4 text-sm font-semibold">Citations ({r.citations.length})</summary>
        <ul className="flex flex-col divide-y divide-line border-t border-line">
          {r.citations.map((c) => (
            <li key={c.claim_id} className="flex flex-wrap items-center gap-2 px-4 py-2 text-sm">
              <StatusChip status={c.status} label={c.label} context="reviewer" />
              <code className="break-all text-xs">
                {c.file ? `${c.file}${c.start_line ? `:${c.start_line}${c.end_line && c.end_line !== c.start_line ? `-${c.end_line}` : ""}` : ""}` : "no source location"}
              </code>
              {c.commit ? <span className="font-mono text-xs text-muted">@{c.commit.slice(0, 7)}</span> : null}
              <Link to={`${base}/claim/${c.claim_id}`} className="ml-auto text-xs">
                Evidence for {c.claim_id.slice(0, 10)}
              </Link>
            </li>
          ))}
        </ul>
      </details>

      <div className="mt-3 rounded-lg border border-line bg-surface p-4">
        <h2 className="text-sm font-semibold">Where the cited evidence comes from</h2>
        <dl className="mt-2 grid grid-cols-[auto_auto] justify-start gap-x-4 gap-y-1 text-sm" data-testid="categories">
          {cats.map((k) => (
            <div key={k} className="contents">
              <dt>
                {CATEGORY[k]?.title ?? k}
                <span className="block text-xs text-muted">{CATEGORY[k]?.help ?? ""}</span>
              </dt>
              <dd className="tabular-nums">{(r.categories[k] ?? []).length}</dd>
            </div>
          ))}
        </dl>
      </div>

      {r.prompt_bundle || r.outbound_manifest.length ? (
        <section className="mt-3 rounded-lg border border-inferred/50 bg-surface p-4" aria-label="What would be sent" data-testid="outbound">
          <h2 className="text-sm font-semibold">What would be sent to an AI provider</h2>
          <p className="mt-1 text-sm text-ink-2">
            Nothing has been sent. {r.requires_consent ? "Sending needs your explicit consent, " : ""}and your key would stay in this browser. These are exactly the items in the
            bundle:
          </p>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-muted">
                <tr>
                  <th scope="col" className="py-1 pr-3 font-medium">
                    Item
                  </th>
                  <th scope="col" className="py-1 pr-3 font-medium">
                    Source
                  </th>
                  <th scope="col" className="py-1 pr-3 text-right font-medium">
                    Characters
                  </th>
                  <th scope="col" className="py-1 font-medium">
                    SHA-256
                  </th>
                </tr>
              </thead>
              <tbody>
                {r.outbound_manifest.map((m, i) => (
                  <tr key={i} className="border-t border-line align-top">
                    <td className="py-1 pr-3">{m.kind.replace(/_/g, " ")}</td>
                    <td className="break-all py-1 pr-3 font-mono text-xs">{m.claim_id ? `${m.claim_id.slice(0, 10)} ${m.file ?? ""}${m.start_line ? `:${m.start_line}` : ""}` : "none"}</td>
                    <td className="py-1 pr-3 text-right tabular-nums">{m.chars.toLocaleString("en-US")}</td>
                    <td className="py-1 font-mono text-xs">{m.sha256.slice(0, 12)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {typeof r.prompt_bundle?.prompt === "string" ? (
            <details className="mt-2">
              <summary className="tap flex cursor-pointer items-center text-sm">Show the full prompt text</summary>
              <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-md border border-line bg-sunken p-2 text-xs" tabIndex={0} aria-label="Prompt text">
                {r.prompt_bundle.prompt}
              </pre>
            </details>
          ) : null}
        </section>
      ) : null}
    </section>
  );
}
