import { Link, Outlet } from "react-router-dom";
import { useHealth, useMeta } from "../api/queries";

function SkipLink() {
  return (
    <a
      href="#main"
      className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-surface focus:px-3 focus:py-2 focus:shadow"
    >
      Skip to main content
    </a>
  );
}

function ApiFooter() {
  const health = useHealth();
  const meta = useMeta();
  let text: string;
  if (health.isPending) text = "Checking the Traces API";
  else if (health.isError) text = "Traces API unavailable. Start it with ./scripts/start.sh.";
  else text = `API ${health.data.version}, store migration ${health.data.store_migration}`;
  return (
    <footer className="border-t border-white/8 px-4 py-4 pb-24 text-xs text-muted md:px-6 md:pb-4" role="contentinfo">
      <div className="mx-auto flex max-w-[88rem] flex-wrap gap-x-4 gap-y-1">
        <span aria-live="polite">{text}</span>
        {meta.data ? (
          <>
            <span>Evidence schema {meta.data.evidence_schema}</span>
            <span>Isolation {meta.data.isolation}</span>
          </>
        ) : null}
        <span>Read-only analysis. No telemetry.</span>
      </div>
    </footer>
  );
}

export function AppShell() {
  return (
    <div className="flex min-h-dvh flex-col">
      <SkipLink />
      <header className="sticky top-0 z-30 border-b border-white/8 bg-canvas/80 backdrop-blur-md" role="banner">
        <div className="mx-auto flex h-12 max-w-[88rem] items-center gap-3 px-4 md:px-6">
          <Link to="/" className="-ml-1 inline-flex h-8 items-center gap-2 rounded-md px-1 text-[15px] font-medium tracking-[-0.03em] text-ink no-underline hover:no-underline">
            <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
              <circle cx="4" cy="12.5" r="1.7" fill="#8fd9cf" />
              <circle cx="14" cy="5.5" r="1.7" fill="#7eb6ff" />
              <path d="M5.5 11.6 L12.5 6.4" stroke="#eef1f6" strokeWidth="1.1" strokeLinecap="round" />
            </svg>
            Traces
          </Link>
          <span className="hidden text-[13px] text-muted sm:inline">One commit. Labeled evidence.</span>
          <nav aria-label="Global" className="ml-auto">
            <Link to="/settings" className="inline-flex h-8 items-center rounded-md px-2 text-sm text-muted no-underline hover:text-ink hover:no-underline">
              Settings
            </Link>
          </nav>
        </div>
      </header>
      <div className="flex-1">
        <Outlet />
      </div>
      <ApiFooter />
    </div>
  );
}
