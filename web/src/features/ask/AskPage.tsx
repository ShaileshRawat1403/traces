import { useMutation } from "@tanstack/react-query";
import { useId, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { Button, Card, ErrorState, PageHeader } from "../../ui/States";

export function AskPage() {
  const { repoId = "", sha = "" } = useParams();
  const [question, setQuestion] = useState("");
  const qid = useId();
  const ask = useMutation({ mutationFn: (qq: string) => api.explain(repoId, sha, { question: qq, mode: "no_llm", focus_claim_ids: [] }) });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (question.trim()) ask.mutate(question.trim());
  };
  return (
    <>
      <PageHeader title="Ask">
        Explain mode answers from evidence with citations and needs no AI key. Optional chat with your own key arrives later; keys stay in your browser and never reach Traces.
      </PageHeader>
      <form onSubmit={submit} className="mb-4 flex flex-col gap-2 rounded-lg border border-line bg-surface p-3">
        <label htmlFor={qid} className="text-sm font-medium">
          Question about this snapshot
        </label>
        <textarea id={qid} value={question} maxLength={2000} rows={3} onChange={(e) => setQuestion(e.target.value)} className="rounded-md border border-line-strong p-2" placeholder="What does the items page depend on?" />
        <div className="flex items-center gap-2">
          <Button type="submit" variant="primary" disabled={!question.trim() || ask.isPending}>
            {ask.isPending ? "Asking" : "Explain (no key needed)"}
          </Button>
          <span className="text-xs text-muted">{question.length}/2000</span>
        </div>
      </form>
      {ask.isError ? <ErrorState error={ask.error} what="Explain" /> : null}
      {ask.isSuccess ? (
        <Card>
          <p role="status">The API returned an answer with {ask.data.citations.length} citations. The answer renderer is scheduled for the explain checkpoint.</p>
        </Card>
      ) : null}
      <p className="mt-4 text-sm text-muted">
        Provider settings: <Link to="/settings">Settings</Link>.
      </p>
    </>
  );
}
