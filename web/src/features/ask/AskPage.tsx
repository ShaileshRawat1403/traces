import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import * as Tabs from "@radix-ui/react-tabs";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../../api/client";
import { keys } from "../../api/queries";
import { snapshotBase } from "../../app/nav";
import { Button, ErrorState, PageHeader } from "../../ui/States";
import { ChatPanel } from "../chat/ChatPanel";
import { ExplainView } from "./ExplainView";
import { starterQuestions } from "./starters";

const TAB = "tap shrink-0 border-b-2 border-transparent px-3 text-sm data-[state=active]:border-accent data-[state=active]:font-semibold";

export function AskPage() {
  const { repoId = "", sha = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const mode = params.get("mode") === "chat" ? "chat" : "explain";
  return (
    <>
      <PageHeader title="Ask">
        Explain answers from stored evidence. Each sentence is marked grounded, interpretation, or unknown, and points at the record it uses; no model is called. Chat uses your own key from this browser, and keys never reach Traces.
      </PageHeader>
      <Tabs.Root
        value={mode}
        onValueChange={(v) => {
          const n = new URLSearchParams(params);
          if (v === "chat") n.set("mode", "chat");
          else n.delete("mode");
          setParams(n, { replace: true });
        }}
      >
        <Tabs.List aria-label="Ask mode" className="mb-4 flex border-b border-line">
          <Tabs.Trigger value="explain" className={TAB}>
            Explain
          </Tabs.Trigger>
          <Tabs.Trigger value="chat" className={TAB}>
            Chat
          </Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content value="explain" className="focus-visible:outline-offset-2">
          <ExplainPanel repoId={repoId} sha={sha} />
        </Tabs.Content>
        <Tabs.Content value="chat" className="focus-visible:outline-offset-2">
          <ChatPanel repoId={repoId} sha={sha} />
        </Tabs.Content>
      </Tabs.Root>
    </>
  );
}

function ExplainPanel({ repoId, sha }: { repoId: string; sha: string }) {
  const [sp] = useSearchParams();
  const seeded = sp.get("q") ?? "";
  const [question, setQuestion] = useState(seeded);
  const qid = useId();
  const routes = useQuery({ queryKey: keys.view("routes", repoId, sha), queryFn: () => api.routes(repoId, sha) });
  const questions = starterQuestions(sha, routes.data ?? []);
  const ask = useMutation({
    mutationFn: (v: { question: string; mode: "no_llm" | "prepare_bundle" }) => api.explain(repoId, sha, { question: v.question, mode: v.mode, focus_claim_ids: [] }),
  });
  const ran = useRef(false);
  useEffect(() => {
    if (ran.current || !seeded.trim()) return;
    ran.current = true;
    ask.mutate({ question: seeded.trim(), mode: "no_llm" });
  }, [seeded, ask]);
  const run = (q: string) => {
    setQuestion(q);
    ask.mutate({ question: q, mode: "no_llm" });
  };
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (question.trim()) ask.mutate({ question: question.trim(), mode: "no_llm" });
  };
  const preview = () => question.trim() && ask.mutate({ question: question.trim(), mode: "prepare_bundle" });
  return (
    <>
      <section className="mb-4" aria-label="Questions this snapshot can answer">
        <p className="text-sm text-ink-2">These match questions the explainer can answer from stored evidence. Pick one, or write your own. No model is called.</p>
        <ul className="mt-2 flex flex-col">
          {questions.map((q) => (
            <li key={q} className="border-b border-white/8">
              <button type="button" onClick={() => run(q)} disabled={ask.isPending} className="min-h-11 w-full py-2.5 text-left text-sm text-ink disabled:text-muted">
                {q}
              </button>
            </li>
          ))}
        </ul>
      </section>
      <form onSubmit={submit} className="mb-4 flex flex-col gap-2" aria-label="Ask a question">
        <label htmlFor={qid} className="text-sm font-medium">
          Question about this snapshot
        </label>
        <textarea id={qid} value={question} maxLength={2000} rows={3} onChange={(e) => setQuestion(e.target.value)} className="rounded-md border border-white/10 bg-white/[0.03] p-2" placeholder="For example: What does a function depend on? What calls it? Trace from one symbol to another." />
        <div className="flex flex-wrap items-center gap-2">
          <Button type="submit" variant="primary" disabled={!question.trim() || ask.isPending}>
            {ask.isPending ? "Asking" : "Explain (no key needed)"}
          </Button>
          <Button type="button" onClick={preview} disabled={!question.trim() || ask.isPending}>
            Preview what an AI would receive
          </Button>
          <span className="text-xs text-muted">{question.length}/2000</span>
        </div>
      </form>
      {ask.isError ? <ErrorState error={ask.error} what="Explain" /> : null}
      {ask.isSuccess ? <ExplainView r={ask.data} base={snapshotBase(repoId, sha)} /> : null}
      <p className="mt-4 text-sm text-muted">
        Provider settings for chat: <Link to="/settings">Settings</Link>.
      </p>
    </>
  );
}
