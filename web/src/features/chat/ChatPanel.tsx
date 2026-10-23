import { useMutation } from "@tanstack/react-query";
import { useId, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import { useRepo } from "../../api/queries";
import { snapshotBase } from "../../app/nav";
import { StatusChip } from "../../ui/StatusChip";
import { Button, ErrorState, Loading } from "../../ui/States";
import { outgoing, keptManifest, readBundle, type EvidenceItem } from "./bundle";
import { checkCitations, pieces, shortId, type CitationCheck } from "./citations";
import { ConsentDialog, type Pending } from "./ConsentDialog";
import { loadConfig, loadKey } from "./keyStore";
import { PROVIDERS, ProviderError, buildRequest, checkBaseUrl, hostOf, send } from "./providers";
import { appendLog, type SentEntry } from "./sentLog";
import { SentEntryView } from "./SentRecord";

interface Message {
  id: string;
  question: string;
  sent: EvidenceItem[];
  entry: SentEntry;
  state: "sending" | "done" | "error";
  answer?: string;
  check?: CitationCheck;
  error?: string;
}

// randomUUID is missing outside secure contexts.
const newId = () => ("randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`);

function Answer({ m, base }: { m: Message; base: string }) {
  if (m.state === "sending") return <Loading label={`Waiting for ${m.entry.host}`} />;
  if (m.state === "error")
    return (
      <p role="alert" className="rounded-md border border-rejected/40 bg-rejected-soft p-2 text-sm text-ink" data-testid="chat-error">
        {m.error}
      </p>
    );
  const ids = m.sent.map((e) => e.claim_id);
  const c = m.check!;
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs" data-testid="grounding" data-grounded={c.grounded ? "true" : "false"}>
        {c.grounded ? (
          <span className="font-semibold text-verified">
            Cites {c.valid.length} {c.valid.length === 1 ? "claim that was" : "claims that were"} sent.
          </span>
        ) : (
          <span className="font-semibold text-rejected">Ungrounded: this answer cites none of the claims that were sent. Treat it as unsupported.</span>
        )}
        {c.invalid.length ? (
          <span className="ml-1 font-semibold text-rejected" data-testid="invalid-citations">
            {c.invalid.length} {c.invalid.length === 1 ? "citation points" : "citations point"} at claims that were not sent.
          </span>
        ) : null}
      </p>
      {/* Model output is plain text: no markdown, no links. Only checked claim ids become links, to our own evidence pages. */}
      <p className="whitespace-pre-wrap break-words" data-testid="chat-answer">
        {pieces(m.answer ?? "", ids).map((p, i) =>
          p.t === "text" ? (
            <span key={i}>{p.v}</span>
          ) : p.ok ? (
            <Link key={i} to={`${base}/claim/${p.v}`} className="mx-0.5 rounded border border-verified/50 px-1 font-mono text-xs" data-testid="cite-ok">
              {shortId(p.v)}
            </Link>
          ) : (
            <span key={i} className="mx-0.5 rounded border border-rejected/60 bg-rejected-soft px-1 font-mono text-xs text-rejected" data-testid="cite-bad" title="Not one of the claims that were sent">
              {shortId(p.v)} not sent
            </span>
          ),
        )}
      </p>
      <p className="text-xs text-muted">
        Written by {m.entry.model} from the evidence that was sent. Traces checked which claims it cites, not whether what it says is right. The evidence is static analysis; nothing was run.
      </p>
    </div>
  );
}

function CitedPanel({ m, base }: { m: Message | null; base: string }) {
  if (!m) return <p className="text-sm text-muted">Citations for an answer appear here.</p>;
  const cited = new Set(m.check?.valid ?? []);
  return (
    <ul className="flex flex-col gap-2" data-testid="cited-panel">
      {m.sent.map((e) => (
        <li key={e.claim_id} className={`rounded-md border p-2 text-sm ${cited.has(e.claim_id) ? "border-verified/60 bg-hit" : "border-line"}`} data-cited={cited.has(e.claim_id) ? "true" : "false"}>
          <span className="flex flex-wrap items-center gap-2">
            <StatusChip status={e.status} label={e.label} />
            <span className="text-xs text-muted">{cited.has(e.claim_id) ? "cited" : "sent, not cited"}</span>
          </span>
          <span className="mt-1 block break-words">{e.statement}</span>
          <Link to={`${base}/claim/${e.claim_id}`} className="mt-1 inline-block break-all text-xs">
            Evidence at {e.where}
          </Link>
        </li>
      ))}
      {m.check?.invalid.map((id) => (
        <li key={id} className="rounded-md border border-rejected/60 bg-rejected-soft p-2 text-xs">
          <span className="font-mono">{shortId(id)}</span> was cited but was not sent. It may not exist.
        </li>
      ))}
    </ul>
  );
}

/** BYOK chat (IA.md 8.2). The Traces API only prepares the scoped bundle; the browser sends it to the provider after consent. */
export function ChatPanel({ repoId, sha }: { repoId: string; sha: string }) {
  const repo = useRepo(repoId);
  const base = snapshotBase(repoId, sha);
  const [cfg] = useState(loadConfig);
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState<Pending | null>(null);
  const [removed, setRemoved] = useState<Set<string>>(new Set());
  const [messages, setMessages] = useState<Message[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const qid = useId();

  const prepare = useMutation({
    mutationFn: (q: string) => api.chatBundle(repoId, sha, { question: q, mode: "prepare_bundle", focus_claim_ids: [] }),
    onSuccess: (r, q) => {
      const b = readBundle(r);
      if (!b) return setNotice("The API answered without a prompt bundle, so there is nothing to send.");
      if (!b.evidence.length) return setNotice("No evidence matched this question, so nothing would be grounded. Nothing was sent. Try Explain, or ask about a named file or symbol.");
      setRemoved(new Set());
      setPending({ question: q, bundle: b, manifest: r.outbound_manifest });
    },
  });

  if (repo.isPending) return <Loading />;
  if (repo.isError) return <ErrorState error={repo.error} what="Repository" />;
  const visibility = repo.data.visibility as string;
  if (visibility !== "public")
    return (
      <p role="status" className="rounded-lg border border-line bg-surface p-4" data-testid="chat-blocked">
        Chat is off for this repository because it is not public ({visibility}), and this build has no recorded consent for sending its text to an AI provider.
      </p>
    );

  const badCfg = !cfg ? "No AI provider is set up." : checkBaseUrl(cfg.baseUrl) ?? (!cfg.model ? "No model is set." : null);
  const stored = loadKey();
  const needsKey = cfg ? PROVIDERS[cfg.kind].needsKey : true;
  const blocked = badCfg ?? (needsKey && !stored ? "No API key is stored in this browser." : null);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setNotice(null);
    if (question.trim() && !blocked) prepare.mutate(question.trim());
  };

  const sendNow = async () => {
    if (!pending || !cfg) return;
    const key = loadKey()?.key ?? "";
    const out = outgoing(pending.bundle, removed);
    const req = buildRequest(cfg, key, out.prompt);
    const sent = pending.bundle.evidence.filter((e) => out.claimIds.includes(e.claim_id));
    const entry: SentEntry = {
      id: newId(),
      at: new Date().toISOString(),
      repoId,
      sha,
      provider: PROVIDERS[cfg.kind].name,
      host: hostOf(req.url),
      url: req.url,
      model: cfg.model,
      headers: req.shownHeaders,
      body: req.body,
      manifest: keptManifest(pending.manifest, removed),
      removed: [...removed],
      outcome: { ok: false, detail: "Sent, waiting for an answer" },
    };
    const m: Message = { id: entry.id, question: pending.question, sent, entry, state: "sending" };
    setPending(null);
    setMessages((ms) => [...ms, m]);
    setSelected(m.id);
    setQuestion("");
    let done: Message;
    try {
      const answer = await send(cfg, req, key);
      const check = checkCitations(answer, out.claimIds);
      entry.outcome = {
        ok: true,
        detail: check.grounded ? `Answered, ${check.valid.length} valid and ${check.invalid.length} invalid citations` : `Answered, ungrounded (${check.invalid.length} invalid citations)`,
        grounded: check.grounded,
        valid: check.valid.length,
        invalid: check.invalid.length,
      };
      done = { ...m, entry, state: "done", answer, check };
    } catch (e) {
      const msg = e instanceof ProviderError ? e.message : "The request failed before an answer arrived.";
      entry.outcome = { ok: false, detail: msg };
      done = { ...m, entry, state: "error", error: msg };
    }
    appendLog(entry);
    setMessages((ms) => ms.map((x) => (x.id === done.id ? done : x)));
  };

  const current = messages.find((x) => x.id === selected) ?? messages[messages.length - 1] ?? null;

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]" data-testid="chat">
      <div className="flex min-w-0 flex-col gap-3">
        <p className="text-sm text-ink-2">
          Chat sends a small, scoped set of evidence to an AI provider you choose, using your own key, straight from this browser. You see and approve exactly what is sent every
          time. Answers are checked against the claims that were sent.
        </p>
        {blocked ? (
          <p role="status" className="rounded-md border border-line bg-surface p-3 text-sm" data-testid="chat-setup">
            {blocked} Set one up in <Link to="/settings">Settings</Link>. Explain works without any key.
          </p>
        ) : (
          <p className="text-xs text-muted" data-testid="chat-provider">
            Provider: {PROVIDERS[cfg!.kind].name}, {cfg!.model} at {hostOf(cfg!.baseUrl)}. Key {stored?.remembered ? "remembered on this device" : needsKey ? "kept for this session" : "not needed"}.
          </p>
        )}

        <ol className="flex flex-col gap-3" aria-label="Conversation">
          {messages.map((m) => (
            <li key={m.id} className={`rounded-lg border bg-surface p-3 ${current?.id === m.id ? "border-accent" : "border-line"}`} data-testid="chat-message">
              <p className="text-sm font-medium">You asked: {m.question}</p>
              <div className="mt-2">
                <Answer m={m} base={base} />
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                <Button type="button" onClick={() => setSelected(m.id)} aria-pressed={current?.id === m.id}>
                  Show citations
                </Button>
              </div>
              <details className="mt-2 text-sm" data-testid="sent-context">
                <summary className="tap flex cursor-pointer items-center">Sent context</summary>
                <SentEntryView e={m.entry} />
              </details>
            </li>
          ))}
        </ol>

        <form onSubmit={submit} className="flex flex-col gap-2 rounded-lg border border-line bg-surface p-3">
          <label htmlFor={qid} className="text-sm font-medium">
            Message
          </label>
          <textarea id={qid} value={question} maxLength={2000} rows={3} onChange={(e) => setQuestion(e.target.value)} className="rounded-md border border-line-strong p-2" />
          <div className="flex flex-wrap items-center gap-2">
            <Button type="submit" variant="primary" disabled={!question.trim() || !!blocked || prepare.isPending}>
              {prepare.isPending ? "Preparing" : "Review what will be sent"}
            </Button>
            <span className="text-xs text-muted">Nothing is sent until you approve it.</span>
          </div>
        </form>
        {prepare.isError ? <ErrorState error={prepare.error} what="Chat bundle" /> : null}
        {notice ? (
          <p role="status" className="rounded-md border border-line bg-surface p-3 text-sm" data-testid="chat-notice">
            {notice}
          </p>
        ) : null}
      </div>
      <aside aria-label="Citations for this answer" className="min-w-0 rounded-lg border border-line bg-surface p-3">
        <h2 className="mb-2 text-sm font-semibold">Citations for this answer</h2>
        <CitedPanel m={current} base={base} />
      </aside>
      {cfg ? (
        <ConsentDialog
          pending={pending}
          cfg={cfg}
          removed={removed}
          onToggle={(id) =>
            setRemoved((s) => {
              const n = new Set(s);
              if (n.has(id)) n.delete(id);
              else n.add(id);
              return n;
            })
          }
          onCancel={() => setPending(null)}
          onSend={() => void sendNow()}
        />
      ) : null}
    </div>
  );
}
