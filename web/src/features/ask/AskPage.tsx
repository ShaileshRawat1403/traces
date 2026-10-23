import { useMutation } from "@tanstack/react-query";
import { useId, useState, type FormEvent } from "react";
import * as Tabs from "@radix-ui/react-tabs";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../../api/client";
import { snapshotBase } from "../../app/nav";
import { Button, ErrorState, PageHeader } from "../../ui/States";
import { ChatPanel } from "../chat/ChatPanel";
import { ExplainView } from "./ExplainView";

const TAB = "tap shrink-0 border-b-2 border-transparent px-3 text-sm data-[state=active]:border-accent data-[state=active]:font-semibold";

export function AskPage() {
  const { repoId = "", sha = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const mode = params.get("mode") === "chat" ? "chat" : "explain";
  return (
    <>
      <PageHeader title="Ask">
        Explain answers from evidence with citations and needs no AI key. Chat uses your own key from this browser; keys never reach Traces.
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
  const [question, setQuestion] = useState("");
  const qid = useId();
  const ask = useMutation({
    mutationFn: (v: { question: string; mode: "no_llm" | "prepare_bundle" }) => api.explain(repoId, sha, { question: v.question, mode: v.mode, focus_claim_ids: [] }),
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (question.trim()) ask.mutate({ question: question.trim(), mode: "no_llm" });
  };
  const preview = () => question.trim() && ask.mutate({ question: question.trim(), mode: "prepare_bundle" });
  return (
    <>
      <form onSubmit={submit} className="mb-4 flex flex-col gap-2 rounded-lg border border-line bg-surface p-3">
        <label htmlFor={qid} className="text-sm font-medium">
          Question about this snapshot
        </label>
        <textarea id={qid} value={question} maxLength={2000} rows={3} onChange={(e) => setQuestion(e.target.value)} className="rounded-md border border-line-strong p-2" placeholder="What does the items page depend on?" />
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
