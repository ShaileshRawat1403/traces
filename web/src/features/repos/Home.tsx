import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
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
  const register = useMutation({
    mutationFn: (u: string) => api.registerRepo(u),
    onSuccess: () => {
      setUrl("");
      setTouched(false);
      void qc.invalidateQueries({ queryKey: keys.repos });
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
    <main id="main" tabIndex={-1} className="mx-auto max-w-3xl px-4 py-8 focus:outline-none sm:py-12">
      <PageHeader title="Repositories">Public repositories, one commit at a time. Every view is backed by stored evidence. A gap stays a gap.</PageHeader>

      <ul className="mb-6 grid gap-2 sm:grid-cols-3" aria-label="How Traces treats a repository">
        {NOTES.map((n) => (
          <li key={n.title} className="rounded-lg border border-line bg-surface px-3 py-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-accent">{n.title}</p>
            <p className="mt-1 text-sm leading-snug text-ink-2">{n.body}</p>
          </li>
        ))}
      </ul>

      <form onSubmit={submit} noValidate className="rounded-lg border border-line bg-surface p-4" aria-label="Add a repository">
        <label id={`${inputId}-label`} htmlFor={inputId} className="block font-medium">
          Public GitHub repository URL
        </label>
        <p id={hintId} className="text-sm text-muted">
          Only https://github.com/owner/repo is accepted. Registering does not fetch or run anything.
        </p>
        <div className="mt-2 flex flex-col gap-2 sm:flex-row">
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
            className="tap min-w-0 flex-1 rounded-md border border-line-strong bg-surface px-3 text-base"
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

      <section className="mt-6" aria-labelledby="repo-list-h">
        <h2 id="repo-list-h" className="mb-2 text-lg font-semibold">
          Registered
        </h2>
        {repos.isPending ? (
          <Loading label="Loading repositories" />
        ) : repos.isError ? (
          <ErrorState error={repos.error} what="Repository list" />
        ) : repos.data.length === 0 ? (
          <Empty title="No repositories yet">Add a public GitHub URL above.</Empty>
        ) : (
          <ul className="flex flex-col gap-2" data-testid="repo-list">
            {repos.data.map((r) => (
              <li key={r.id}>
                <Link
                  to={`/r/${encodeURIComponent(r.id)}`}
                  className="tap flex items-center justify-between gap-3 rounded-lg border border-line bg-surface px-4 py-3 text-ink no-underline hover:border-accent hover:no-underline"
                >
                  <span className="min-w-0">
                    <span className="block font-medium">
                      {r.owner}/{r.name}
                    </span>
                    <span className="block text-sm text-muted">
                      {r.latest_discovered_sha ? `${r.visibility} · latest seen @${r.latest_discovered_sha.slice(0, 7)}` : `${r.visibility} · open to see snapshots`}
                    </span>
                  </span>
                  <span aria-hidden="true" className="text-accent">
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
