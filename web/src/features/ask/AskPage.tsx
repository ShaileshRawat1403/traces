import { useMutation } from "@tanstack/react-query";
import { useId, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { snapshotBase } from "../../app/nav";
import { Button, ErrorState, PageHeader } from "../../ui/States";
import { ExplainView } from "./ExplainView";

export function AskPage() {
  const { repoId = "", sha = "" } = useParams();
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
      <PageHeader title="Ask">A short answer from stored evidence. Each sentence is marked grounded, interpretation, or unknown, and points at the record it uses. No model is called.</PageHeader>
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
        Provider settings: <Link to="/settings">Settings</Link>.
      </p>
    </>
  );
}
