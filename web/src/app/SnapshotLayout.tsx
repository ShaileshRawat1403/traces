import * as Dialog from "@radix-ui/react-dialog";
import { useState } from "react";
import { Link, NavLink, Outlet, useParams, useSearchParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { useCapability, useSnapshot } from "../api/queries";
import { LookingBar } from "../features/subject/LookingBar";
import { SnapshotFind } from "../features/find/SnapshotFind";
import { STATIC_DISCLAIMER } from "../status/status";
import { SNAPSHOT_NAV, shortSha, snapshotBase, type NavItem } from "./nav";

function keepAt(path: string, at: string | null) {
  if (!at) return path;
  const q = path.indexOf("?");
  const base = q < 0 ? path : path.slice(0, q);
  const n = new URLSearchParams(q < 0 ? "" : path.slice(q + 1));
  n.set("at", at);
  return `${base}?${n.toString()}`;
}

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
  const [sp] = useSearchParams();
  return (
    <NavLink
      to={keepAt(item.to ? `${base}/${item.to}` : base, sp.get("at"))}
      end={item.to === ""}
      className={({ isActive }) =>
        `inline-flex h-9 items-center gap-2 border-b px-2 text-sm no-underline hover:no-underline ${
          isActive ? "border-ink font-medium text-ink" : "border-transparent text-muted hover:text-ink"
        }`
      }
    >
      {item.label}
      <PendingDot capability={item.capability} />
    </NavLink>
  );
}

function CopyViewLink() {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      className="inline-flex min-h-8 items-center text-muted hover:text-ink"
      onClick={() => {
        void navigator.clipboard?.writeText(window.location.href).then(() => setCopied(true));
        window.setTimeout(() => setCopied(false), 1500);
      }}
    >
      {copied ? "Link copied" : "Copy link"}
      <span className="sr-only"> to this page, including what is selected</span>
    </button>
  );
}

function ShaChip({ sha }: { sha: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      className="inline-flex h-8 items-center gap-1 rounded-md px-1.5 font-mono text-xs text-muted hover:text-ink"
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
  const [sp] = useSearchParams();
  const at = sp.get("at");
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
                <Link to={keepAt(`${base}/${n.to}`, at)} onClick={() => setOpen(false)} className="tap flex items-center rounded-md px-2 text-ink no-underline hover:bg-sunken">
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

function BottomLink({ base, item }: { base: string; item: NavItem }) {
  const [sp] = useSearchParams();
  return (
    <NavLink
      to={keepAt(item.to ? `${base}/${item.to}` : base, sp.get("at"))}
      end={item.to === ""}
      className={({ isActive }) =>
        `tap flex flex-1 flex-col items-center justify-center text-[11px] tracking-[-0.01em] no-underline hover:no-underline ${isActive ? "font-medium text-ink" : "text-muted"}`
      }
    >
      {({ isActive }) => (
        <>
          <span aria-hidden="true" className={`mb-1 h-px w-5 ${isActive ? "bg-ink" : "bg-transparent"}`} />
          {item.label}
        </>
      )}
    </NavLink>
  );
}

export function SnapshotLayout() {
  const { repoId = "", sha = "" } = useParams();
  const base = snapshotBase(repoId, sha);
  const snap = useSnapshot(repoId, sha);
  const repoName = repoId.split("__").slice(1).join("/") || repoId;
  return (
    <div className="mx-auto flex max-w-[88rem] flex-col px-4 py-4 md:px-6">
      <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-2 text-sm">
        <Link to={`/r/${encodeURIComponent(repoId)}`} className="font-medium">
          {repoName}
        </Link>
        <ShaChip sha={sha} />
        {snap.data ? <span className="text-muted">Snapshot {snap.data.state}</span> : null}
        <CopyViewLink />
        <a href={`/api/v1/repos/${encodeURIComponent(repoId)}/snapshots/${encodeURIComponent(sha)}/export`} className="inline-flex min-h-8 items-center text-muted">
          Download evidence
          <span className="sr-only"> as one JSONL record per line for this snapshot</span>
        </a>
        {snap.isError ? (
          <span className="text-rejected" role="status">
            {snap.error instanceof ApiError && snap.error.status === 404 ? "Snapshot not found" : "Snapshot details unavailable"}
          </span>
        ) : null}
        <SnapshotFind />
      </div>
      <nav aria-label="Snapshot sections" className="mb-3 hidden gap-1 overflow-x-auto border-b border-white/8 md:flex">
        {SNAPSHOT_NAV.map((n) => (
          <SideLink key={n.to} base={base} item={n} />
        ))}
      </nav>
      <LookingBar />
      <main id="main" tabIndex={-1} className="min-w-0 focus:outline-none">
        <div className="mb-3 flex flex-col gap-0.5 text-[13px] leading-relaxed text-muted sm:flex-row sm:flex-wrap sm:items-baseline sm:gap-x-6">
          <p data-testid="static-disclaimer">{STATIC_DISCLAIMER}</p>
          <p>Rejected claims stay hidden until you open Review.</p>
        </div>
        <Outlet />
      </main>
      <nav aria-label="Snapshot sections, bottom bar" className="fixed inset-x-0 bottom-0 z-30 flex border-t border-white/10 bg-canvas/95 backdrop-blur-md md:hidden">
        {SNAPSHOT_NAV.filter((n) => n.primary).map((n) => (
          <BottomLink key={n.to} base={base} item={n} />
        ))}
        <MoreSheet base={base} />
      </nav>
    </div>
  );
}
