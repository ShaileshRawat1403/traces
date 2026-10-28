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
    <footer className="border-t border-line px-4 py-4 pb-24 text-xs text-muted md:pb-4" role="contentinfo">
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
      <header className="sticky top-0 z-30 border-b border-line bg-canvas/85 shadow-[inset_0_-1px_0_0_rgb(228_194_122_/_0.35)] backdrop-blur-md" role="banner">
        <div className="mx-auto flex h-14 max-w-[88rem] items-center gap-3 px-4">
          <Link to="/" className="tap -ml-2 inline-flex items-center gap-2.5 rounded-md px-2 font-semibold tracking-tight text-ink no-underline hover:no-underline">
            <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true">
              <rect x="1" y="1" width="20" height="20" rx="6" fill="#16130c" stroke="#e4c27a" strokeWidth="1.25" />
              <circle cx="7" cy="14" r="1.7" fill="#8fd9cf" />
              <circle cx="15" cy="8" r="1.7" fill="#e4c27a" />
              <path d="M8.4 13.1 L13.6 8.9" stroke="#f4f1ea" strokeWidth="1.2" strokeLinecap="round" />
            </svg>
            <span className="text-[15px]">Traces</span>
          </Link>
          <span className="hidden text-sm text-muted sm:inline">One commit. Labeled evidence.</span>
          <nav aria-label="Global" className="ml-auto">
            <Link to="/settings" className="tap inline-flex items-center rounded-md px-2 text-sm text-ink-2">
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
