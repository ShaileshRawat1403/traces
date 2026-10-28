import type { ButtonHTMLAttributes, ReactNode } from "react";
import { ApiError } from "../api/client";

/** Honest state for endpoints that answer 501: names what is missing and the seat that owns it. Never shows mock data. */
export function NotAvailable({ error, what }: { error: ApiError; what: string }) {
  const { message, owner, milestone } = error.body;
  return (
    <section className="rounded-lg border border-line bg-surface p-4 sm:p-5" role="status" data-testid="not-available" aria-live="polite">
      <h2 className="text-base font-semibold">{what} is not available yet</h2>
      <p className="mt-1 text-ink-2">{message}.</p>
      <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
        <dt className="text-muted">Owner</dt>
        <dd data-testid="owner">{owner ?? "not stated by the API"}</dd>
        <dt className="text-muted">Milestone</dt>
        <dd>{milestone ?? "not stated by the API"}</dd>
      </dl>
      <p className="mt-3 text-sm text-muted">This view shows real data only. Nothing is simulated while the endpoint is pending.</p>
    </section>
  );
}

export function ErrorState({ error, what = "This view" }: { error: unknown; what?: string }) {
  if (error instanceof ApiError && error.notImplemented) return <NotAvailable error={error} what={what} />;
  const status = error instanceof ApiError ? error.status : null;
  const msg = error instanceof Error ? error.message : String(error);
  const network = error instanceof TypeError;
  return (
    <section className="rounded-lg border border-rejected/40 bg-rejected-soft p-4" role="alert" data-testid="error-state">
      <h2 className="text-base font-semibold text-rejected">{network ? "Cannot reach the Traces API" : status === 404 ? "Not found" : "Something went wrong"}</h2>
      <p className="mt-1 text-ink-2">
        {network ? "Check that the API is running (./scripts/start.sh) and reload." : msg}
        {status ? ` (HTTP ${status})` : ""}
      </p>
    </section>
  );
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-2 py-2" data-testid="loading">
      <span className="sr-only">{label}</span>
      <div className="h-4 w-2/3 animate-pulse rounded bg-sunken" />
      <div className="h-4 w-1/2 animate-pulse rounded bg-sunken" />
      <div className="h-4 w-3/5 animate-pulse rounded bg-sunken" />
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <section className="rounded-lg border border-dashed border-line-strong bg-surface p-4 text-ink-2" data-testid="empty">
      <h2 className="text-base font-semibold text-ink">{title}</h2>
      {children ? <div className="mt-1 text-sm">{children}</div> : null}
    </section>
  );
}

export function PageHeader({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <header className="mb-5">
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      {children ? <div className="mt-1.5 max-w-2xl text-[15px] leading-relaxed text-ink-2">{children}</div> : null}
    </header>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`panel p-4 ${className}`}>{children}</div>;
}

export function Button({
  children,
  variant = "secondary",
  className = "",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" }) {
  const v =
    variant === "primary"
      ? "bg-accent text-accent-ink border-transparent hover:brightness-105 disabled:border-line disabled:bg-line disabled:text-muted"
      : "bg-transparent text-ink border-line-strong hover:bg-sunken";
  return (
    <button className={`tap inline-flex items-center justify-center rounded-lg border px-3 text-sm font-medium tracking-tight disabled:cursor-not-allowed ${v} ${className}`} {...rest}>
      {children}
    </button>
  );
}
