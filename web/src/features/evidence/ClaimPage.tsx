import { useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { useClaim } from "../../api/queries";
import { readRecord, splitSymbol, type EvidenceRecordView } from "../../api/record";
import { HistoryEvidence } from "../history/HistoryEvidence";
import { SourcePanel } from "../source/SourceLines";
import { snapshotBase } from "../../app/nav";
import { presentStatus } from "../../status/status";
import { Button, ErrorState, Loading } from "../../ui/States";
import { StatusChip } from "../../ui/StatusChip";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-line bg-surface p-4" aria-label={title}>
      <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted">{title}</h2>
      {children}
    </section>
  );
}

function Row({ k, children }: { k: string; children: ReactNode }) {
  return (
    <>
      <dt className="text-muted">{k}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </>
  );
}

function Locations({ r, repoId, sha, pinFirst }: { r: EvidenceRecordView; repoId: string; sha: string; pinFirst: boolean }) {
  // In the evidence drawer the first location's source lines are shown immediately.
  const [open, setOpen] = useState<number | null>(pinFirst ? 0 : null);
  if (r.locations.length === 0) return <p className="text-sm text-muted">No source locations recorded{r.status === "missing_location" ? " (missing_location)" : ""}.</p>;
  return (
    <ul className="flex flex-col gap-2">
      {r.locations.map((l, i) => (
        <li key={i} className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="rounded-sm bg-sunken px-1.5 text-xs">{l.role ?? "location"}</span>
            <code className="break-all">
              {l.file}:{l.start_line}
              {l.end_line !== l.start_line ? `-${l.end_line}` : ""}
            </code>
            <span className="text-xs text-muted">
              {l.range_kind} · {l.source}
            </span>
            <Button className="ml-auto" aria-expanded={open === i} onClick={() => setOpen(open === i ? null : i)}>
              {open === i ? "Hide source" : "Show source"}
            </Button>
          </div>
          {open === i ? <SourcePanel repoId={repoId} sha={sha} file={l.file} start={l.start_line} end={Math.max(l.start_line, l.end_line)} /> : null}
        </li>
      ))}
    </ul>
  );
}

export function ClaimPage() {
  const { repoId = "", sha = "", claimId = "" } = useParams();
  return <ClaimEvidence repoId={repoId} sha={sha} claimId={claimId} />;
}

/** Evidence for one claim: used by the claim page and the evidence drawer. */
export function ClaimEvidence({ repoId, sha, claimId, inDrawer = false }: { repoId: string; sha: string; claimId: string; inDrawer?: boolean }) {
  const q = useClaim(repoId, sha, claimId);
  const base = snapshotBase(repoId, sha);
  if (q.isPending) return <Loading label="Loading evidence" />;
  if (q.isError) return <ErrorState error={q.error} what="Evidence" />;
  let r: EvidenceRecordView;
  try {
    r = readRecord(q.data);
  } catch (e) {
    return <ErrorState error={e} what="Evidence" />;
  }
  // The evidence drawer is a reviewer context (CONTRACTS.md 2): a deep link to a rejected claim shows it, labelled Rejected.
  const p = presentStatus(r, "reviewer");
  const rejected = r.status === "rejected";
  const from = r.from ? splitSymbol(r.from.symbol) : null;
  const to = r.to ? splitSymbol(r.to.symbol) : null;
  const pinMismatch = r.repo_sha && r.repo_sha !== sha;

  return (
    <article className="flex flex-col gap-4" aria-labelledby="claim-h">
      {inDrawer ? (
        <p className="text-sm">
          <Link to={`${base}/claim/${r.claim_id}`}>Open as a page</Link>
        </p>
      ) : (
        <p className="text-sm">
          <Link to={`${base}/${rejected ? "review" : "claims"}`}>{rejected ? "Reviewer view" : "Claims"}</Link>
        </p>
      )}
      {rejected ? (
        <p className="rounded-md border border-rejected/40 bg-rejected-soft px-3 py-2 text-sm" role="note">
          This claim was rejected by an independent check. It is kept for audit and is never shown as architecture.
        </p>
      ) : null}
      <header>
        <div className="mb-2">
          <StatusChip status={r.status} label={r.label} flags={r.flags} qualifier={r.qualifier} context="reviewer" />
        </div>
        {inDrawer ? (
          <h2 id="claim-h" className="break-words text-base font-semibold leading-snug">
            {r.statement}
          </h2>
        ) : (
          <h1 id="claim-h" className="break-words text-lg font-semibold leading-snug sm:text-xl">
            {r.statement}
          </h1>
        )}
        {from || to ? (
          <p className="mt-2 break-words text-sm">
            {from ? <code>{from.name}</code> : null} <span className="text-muted">{r.kind ?? r.claim_kind}</span> {to ? <code>{to.name}</code> : null}
          </p>
        ) : null}
      </header>

      <Section title="Locations at the pinned commit">
        <Locations r={r} repoId={repoId} sha={sha} pinFirst={inDrawer} />
      </Section>

      <Section title="Status">
        <p className="text-sm">{p.description}</p>
        {r.status_reason ? (
          <p className="mt-2 text-sm">
            <span className="font-medium">Reason:</span> {r.status_reason}
          </p>
        ) : null}
        {r.flags.length ? (
          <p className="mt-2 flex flex-wrap gap-1 text-xs">
            {r.flags.map((f) => (
              <span key={f} className="rounded-sm border border-line bg-sunken px-1.5 py-0.5">
                {f}
              </span>
            ))}
          </p>
        ) : null}
      </Section>

      <Section title={`Checks (${r.checks.length})`}>
        {r.checks.length === 0 ? (
          <p className="text-sm text-muted">No checks recorded.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {r.checks.map((c) => (
              <li key={c.check_id} className="rounded-md border border-line p-2 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`font-semibold ${c.result === "pass" ? "text-verified" : c.result === "fail" ? "text-rejected" : "text-inferred"}`}>{c.result ?? "no result"}</span>
                  <span className="font-mono">{c.method}</span>
                  {c.rule_id ? <span className="rounded-sm bg-sunken px-1">rule {c.rule_id}</span> : null}
                  <span className="text-xs text-muted">
                    establishes {c.establishes ?? "?"} · {c.independent ? "independent" : "not independent"}
                    {c.validator ? ` · ${c.validator.family ?? ""} ${c.validator.name ?? ""} ${c.validator.version ?? ""}` : ""}
                  </span>
                </div>
                {c.detail ? <p className="mt-1 break-words text-ink-2">{c.detail}</p> : null}
              </li>
            ))}
          </ul>
        )}
      </Section>


      <HistoryEvidence raw={q.data} />

      <Section title="Provenance">
        <dl className="grid grid-cols-[minmax(7rem,auto)_1fr] gap-x-3 gap-y-1 text-sm">
          <Row k="Commit">
            <code className="break-all">{r.repo_sha}</code>
            {pinMismatch ? <span className="ml-2 text-rejected">differs from the snapshot in the URL</span> : null}
          </Row>
          <Row k="Originator">{r.originator ? `${r.originator.name ?? "?"} ${r.originator.version ?? ""} (${r.originator.role ?? "?"})` : "unknown"}</Row>
          <Row k="Provenance">{r.provenance ?? "unknown"}</Row>
          <Row k="Class">{r.class} (how the claim was produced, not its status)</Row>
          <Row k="Scope">{r.evidence_scope}</Row>
          <Row k="Run">{r.run_id ?? "unknown"}</Row>
          <Row k="Schema">{r.schema_version ?? "unknown"}</Row>
          {r.injected ? <Row k="Injected">Yes: a test claim planted to check the validators</Row> : null}
          <Row k="Claim id">
            <code className="break-all">{r.claim_id}</code>
          </Row>
        </dl>
      </Section>

      <Section title="Status history">
        <ol className="flex flex-col gap-1 text-sm">
          {r.status_history.map((h, i) => (
            <li key={i}>
              <span className="font-mono">{h.from ?? "new"}</span> to <span className="font-mono">{h.to}</span>
              <span className="text-muted">
                {" "}
                by {h.by ?? "?"}
                {h.at ? `, ${h.at}` : ""}
              </span>
            </li>
          ))}
        </ol>
        {r.consolidation ? (
          <p className="mt-2 text-sm">
            Consolidated from {r.consolidation.count ?? r.consolidation.members?.length ?? "?"} identical rows ({r.consolidation.rule}).
          </p>
        ) : null}
      </Section>
    </article>
  );
}
