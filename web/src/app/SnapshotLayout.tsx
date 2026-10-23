import * as Dialog from "@radix-ui/react-dialog";
import { useState } from "react";
import { Link, NavLink, Outlet, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { useCapability, useSnapshot } from "../api/queries";
import { STATIC_DISCLAIMER } from "../status/status";
import { SNAPSHOT_NAV, shortSha, snapshotBase, type NavItem } from "./nav";

function PendingDot({ capability }: { capability?: string }) {
  const cap = useCapability(capability ?? "");
  if (!capability || cap !== false) return null;
  return (
    <span className="ml-auto rounded-sm bg-sunken px-1 text-[11px] font-normal text-muted" title="Not available yet in this build (per /meta)">
      soon
    </span>
  );
}

function SideLink({ base, item }: { base: string; item: NavItem }) {
  return (
    <NavLink
      to={item.to ? `${base}/${item.to}` : base}
      end={item.to === ""}
      className={({ isActive }) =>
        `tap flex items-center gap-2 rounded-md px-3 text-sm no-underline hover:bg-sunken hover:no-underline ${
          isActive ? "bg-accent-soft font-semibold text-accent" : "text-ink-2"
        }`
      }
    >
      {item.label}
      <PendingDot capability={item.capability} />
    </NavLink>
  );
}

function ShaChip({ sha }: { sha: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      className="tap inline-flex items-center gap-1 rounded-md border border-line bg-sunken px-2 font-mono text-xs text-ink-2"
      onClick={() => {
        void navigator.clipboard?.writeText(sha).then(() => setCopied(true));
        window.setTimeout(() => setCopied(false), 1500);
      }}
      title={`Pinned commit ${sha}`}
    >
      @{shortSha(sha)}
      <span className="sr-only"> pinned commit, copy full SHA</span>
      <span aria-live="polite" className="font-sans">
        {copied ? "Copied" : ""}
      </span>
    </button>
  );
}

function MoreSheet({ base }: { base: string }) {
  const [open, setOpen] = useState(false);
  const rest = SNAPSHOT_NAV.filter((n) => !n.primary);
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger className="tap flex flex-1 flex-col items-center justify-center text-xs text-ink-2" aria-label="More sections">
        <span aria-hidden="true" className="text-lg leading-none">
          ⋯
        </span>
        More
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/60" />
        <Dialog.Content className="fixed inset-x-0 bottom-0 z-50 rounded-t-lg border-t border-line bg-surface p-4 pb-8 shadow-lg focus:outline-none">
          <div className="mx-auto mb-3 h-1 w-10 rounded bg-line-strong" aria-hidden="true" />
          <Dialog.Title className="text-base font-semibold">More sections</Dialog.Title>
          <Dialog.Description className="sr-only">Other views of this snapshot</Dialog.Description>
          <ul className="mt-2 flex flex-col">
            {rest.map((n) => (
              <li key={n.to}>
                <Link to={`${base}/${n.to}`} onClick={() => setOpen(false)} className="tap flex items-center rounded-md px-2 text-ink no-underline hover:bg-sunken">
                  {n.label}
                  <PendingDot capability={n.capability} />
                </Link>
              </li>
            ))}
            <li>
              <Link to="/settings" onClick={() => setOpen(false)} className="tap flex items-center rounded-md px-2 text-ink no-underline hover:bg-sunken">
                Settings
              </Link>
            </li>
          </ul>
          <Dialog.Close className="tap mt-3 w-full rounded-md border border-line-strong text-sm">Close</Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export function SnapshotLayout() {
  const { repoId = "", sha = "" } = useParams();
  const base = snapshotBase(repoId, sha);
  const snap = useSnapshot(repoId, sha);
  const repoName = repoId.split("__").slice(1).join("/") || repoId;
  return (
    <div className="mx-auto flex max-w-6xl gap-6 px-4 py-4 md:py-6">
      <aside className="hidden w-52 shrink-0 md:block">
        <nav aria-label="Snapshot sections" className="sticky top-20 flex flex-col gap-0.5">
          {SNAPSHOT_NAV.map((n) => (
            <SideLink key={n.to} base={base} item={n} />
          ))}
        </nav>
      </aside>
      <main id="main" tabIndex={-1} className="min-w-0 flex-1 focus:outline-none">
        <div className="mb-4 flex flex-wrap items-center gap-2 text-sm">
          <Link to={`/r/${encodeURIComponent(repoId)}`} className="font-medium">
            {repoName}
          </Link>
          <ShaChip sha={sha} />
          {snap.data ? <span className="text-muted">Snapshot {snap.data.state}</span> : null}
          {snap.isError ? (
            <span className="text-rejected" role="status">
              {snap.error instanceof ApiError && snap.error.status === 404 ? "Snapshot not found" : "Snapshot details unavailable"}
            </span>
          ) : null}
        </div>
        <p className="mb-1 rounded-md border border-line bg-sunken px-3 py-1.5 text-xs text-ink-2" data-testid="static-disclaimer">
          {STATIC_DISCLAIMER}
        </p>
        <p className="mb-3 text-xs text-muted">Rejected claims stay hidden until you open Review.</p>
        <Outlet />
      </main>
      <nav aria-label="Snapshot sections, bottom bar" className="fixed inset-x-0 bottom-0 z-30 flex border-t border-line bg-surface md:hidden">
        {SNAPSHOT_NAV.filter((n) => n.primary).map((n) => (
          <NavLink
            key={n.to}
            to={n.to ? `${base}/${n.to}` : base}
            end={n.to === ""}
            className={({ isActive }) =>
              `tap flex flex-1 flex-col items-center justify-center text-xs no-underline hover:no-underline ${isActive ? "font-semibold text-accent" : "text-ink-2"}`
            }
          >
            {({ isActive }) => (
              <>
                <span aria-hidden="true" className={`mb-1 h-1 w-6 rounded ${isActive ? "bg-accent" : "bg-transparent"}`} />
                {n.label}
              </>
            )}
          </NavLink>
        ))}
        <MoreSheet base={base} />
      </nav>
    </div>
  );
}
