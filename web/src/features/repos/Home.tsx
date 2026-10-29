import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, api } from "../../api/client";
import { keys, useRepos } from "../../api/queries";
import { Button, Empty, ErrorState, Loading, PageHeader } from "../../ui/States";

const URL_RULE = /^https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/?$/;

const NOTES = [
  { title: "Pinned", body: "A snapshot is one commit. Later commits do not rewrite it." },
  { title: "Labeled", body: "Verified, observed, inferred, and rejected stay distinct." },
  { title: "Not executed", body: "The repository is read. Its own code is never run." },
] as const;

export function Home() {
  const repos = useRepos();
  const qc = useQueryClient();
  const [url, setUrl] = useState("");
  const [touched, setTouched] = useState(false);
  const inputId = useId();
  const hintId = useId();
  const errId = useId();
  const nav = useNavigate();
  const register = useMutation({
    mutationFn: (u: string) => api.registerRepo(u),
    onSuccess: (repo) => {
      setUrl("");
      setTouched(false);
      void qc.invalidateQueries({ queryKey: keys.repos });
      nav(`/r/${encodeURIComponent(repo.id)}`);
    },
  });
  const trimmed = url.trim();
  const localInvalid = touched && trimmed !== "" && !URL_RULE.test(trimmed);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (!URL_RULE.test(trimmed)) return;
    register.mutate(trimmed);
  };
  const serverError = register.error instanceof ApiError ? register.error : null;

  return (
    <main id="main" tabIndex={-1} className="mx-auto max-w-5xl px-5 py-14 focus:outline-none sm:py-16">
      <PageHeader title="Repositories">Add a public GitHub repository. You land on it next. Indexing is a separate step, and nothing is fetched until you start it.</PageHeader>

      <ol className="mt-2 grid gap-3 sm:grid-cols-3" aria-label="How Traces treats a repository">
        {NOTES.map((n, i) => (
          <li key={n.title} className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-4">
            <span className="font-mono text-[11px] text-verified">0{i + 1}</span>
            <p className="mt-2 text-[15px] font-medium tracking-[-0.02em]">{n.title}</p>
            <p className="mt-1 text-[13px] leading-snug text-muted">{n.body}</p>
          </li>
        ))}
      </ol>

      <form onSubmit={submit} noValidate className="mt-10 max-w-2xl" aria-label="Add a repository">
        <label id={`${inputId}-label`} htmlFor={inputId} className="block text-sm font-medium tracking-[-0.01em]">
          Public GitHub repository URL
        </label>
        <p id={hintId} className="mt-1 text-[13px] text-muted">
          Only https://github.com/owner/repo is accepted. Registering does not fetch or run anything.
        </p>
        <div className="mt-3 flex flex-col gap-2 sm:flex-row">
          <input
            id={inputId}
            type="url"
            inputMode="url"
            autoComplete="off"
            spellCheck={false}
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onBlur={() => setTouched(true)}
            placeholder="https://github.com/owner/repo"
            aria-describedby={`${hintId}${localInvalid || serverError ? ` ${errId}` : ""}`}
            aria-invalid={localInvalid || !!serverError}
            className="h-11 min-w-0 flex-1 rounded-md border border-white/10 bg-white/[0.03] px-3 text-[15px]"
          />
          <Button type="submit" variant="primary" disabled={register.isPending}>
            {register.isPending ? "Adding" : "Add repository"}
          </Button>
        </div>
        {localInvalid ? (
          <p id={errId} className="mt-2 text-sm text-rejected" role="alert">
            That is not a public GitHub repository URL of the form https://github.com/owner/repo.
          </p>
        ) : serverError ? (
          <p id={errId} className="mt-2 text-sm text-rejected" role="alert">
            {serverError.body.message} ({serverError.body.code})
          </p>
        ) : register.isError ? (
          <div className="mt-2">
            <ErrorState error={register.error} />
          </div>
        ) : null}
      </form>

      <section className="mt-12" aria-labelledby="repo-list-h">
        <h2 id="repo-list-h" className="text-sm font-medium tracking-[-0.02em] text-ink-2">
          Registered
        </h2>
        {repos.isPending ? (
          <Loading label="Loading repositories" />
        ) : repos.isError ? (
          <ErrorState error={repos.error} what="Repository list" />
        ) : repos.data.length === 0 ? (
          <Empty title="No repositories yet">Add a public GitHub URL above.</Empty>
        ) : (
          <ul className="mt-2" data-testid="repo-list">
            {repos.data.map((r) => (
              <li key={r.id} className="border-b border-white/8">
                <Link
                  to={`/r/${encodeURIComponent(r.id)}`}
                  className="group flex items-center gap-4 border-b border-white/8 py-4 text-ink no-underline hover:no-underline"
                >
                  <span className="h-10 w-1 shrink-0 rounded-full bg-verified" aria-hidden="true" />
                  <span className="min-w-0 flex-1">
                    <span className="block text-[18px] font-medium tracking-[-0.03em]">
                      {r.owner}/{r.name}
                    </span>
                    <span className="mt-0.5 block text-[13px] text-muted">
                      {r.latest_discovered_sha ? `${r.visibility} · latest seen @${r.latest_discovered_sha.slice(0, 7)}` : `${r.visibility} · open to see snapshots`}
                    </span>
                  </span>
                  <span aria-hidden="true" className="text-[13px] text-muted transition-colors group-hover:text-ink">
                    Open
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
