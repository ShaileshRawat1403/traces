import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError, api } from "../../api/client";
import { keys, useRepos } from "../../api/queries";
import { Button, Empty, ErrorState, Loading, PageHeader } from "../../ui/States";

const URL_RULE = /^https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/?$/;

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
    <main id="main" tabIndex={-1} className="mx-auto max-w-3xl px-4 py-6 focus:outline-none sm:py-10">
      <PageHeader title="Repositories">Point Traces at a public GitHub repository. Every view is pinned to a commit and backed by evidence.</PageHeader>

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
                  className="tap flex flex-col justify-center rounded-lg border border-line bg-surface px-4 py-3 text-ink no-underline hover:border-line-strong hover:no-underline"
                >
                  <span className="font-medium">
                    {r.owner}/{r.name}
                  </span>
                  <span className="text-sm text-muted">
                    {r.visibility} · {r.latest_discovered_sha ? `latest seen @${r.latest_discovered_sha.slice(0, 7)}` : "HEAD not checked yet"}
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
