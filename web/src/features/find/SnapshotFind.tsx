import { useQuery } from "@tanstack/react-query";
import { useEffect, useId, useMemo, useState, type KeyboardEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../../api/client";
import { keys } from "../../api/queries";
import { snapshotBase } from "../../app/nav";
import { findInSnapshot } from "./find";

/** Search stored components, routes, files, and handlers in this snapshot. */
export function SnapshotFind() {
  const { repoId = "", sha = "" } = useParams();
  const nav = useNavigate();
  const base = snapshotBase(repoId, sha);
  const inputId = useId();
  const listId = useId();
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const [open, setOpen] = useState(false);
  const ready = q.trim().length >= 2;
  const components = useQuery({ queryKey: keys.view("components", repoId, sha), queryFn: () => api.components(repoId, sha), enabled: ready });
  const routes = useQuery({ queryKey: keys.view("routes", repoId, sha), queryFn: () => api.routes(repoId, sha), enabled: ready });
  const hits = useMemo(
    () => (components.data && routes.data ? findInSnapshot(q, components.data, routes.data, base) : []),
    [q, components.data, routes.data, base],
  );
  useEffect(() => setActive(0), [q]);
  const go = (href: string) => {
    setQ("");
    setOpen(false);
    nav(href);
  };
  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(hits.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter" && hits[active]) {
      e.preventDefault();
      go(hits[active].href);
    } else if (e.key === "Escape") {
      setQ("");
      setOpen(false);
    }
  };
  const show = open && ready;
  return (
    <form role="search" className="relative w-full sm:ml-auto sm:w-72" onSubmit={(e) => e.preventDefault()}>
      <label htmlFor={inputId} className="sr-only">
        Find in this snapshot
      </label>
      <input
        id={inputId}
        role="combobox"
        aria-expanded={show && hits.length > 0}
        aria-controls={show && hits.length > 0 ? listId : undefined}
        aria-autocomplete="list"
        aria-activedescendant={show && hits[active] ? `${listId}-${active}` : undefined}
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => window.setTimeout(() => setOpen(false), 150)}
        onKeyDown={onKeyDown}
        placeholder="Component, route, or file"
        className="h-8 w-full rounded-md border border-white/10 bg-white/[0.03] px-2 text-sm"
        autoComplete="off"
      />
      {show ? (
        <div className="absolute z-40 mt-1 w-full rounded-md border border-white/10 bg-canvas py-1 shadow-card">
          {components.isPending || routes.isPending ? (
            <p className="px-2 py-1.5 text-xs text-muted" role="status">
              Looking up stored components and routes.
            </p>
          ) : components.isError || routes.isError ? (
            <p className="px-2 py-1.5 text-xs text-rejected" role="alert">
              The component or route list could not be loaded.
            </p>
          ) : hits.length === 0 ? (
            <p className="px-2 py-1.5 text-xs text-muted" role="status">
              No stored component, route, or file matches. That is not proof it is absent from the repository.
            </p>
          ) : (
            <ul id={listId} role="listbox" aria-label="Matches in this snapshot">
              {hits.map((h, i) => (
                <li key={h.id} id={`${listId}-${i}`} role="option" aria-selected={i === active}>
                  <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => go(h.href)} className={`flex w-full min-h-8 items-baseline justify-between gap-2 px-2 py-1 text-left text-sm ${i === active ? "bg-white/[0.06]" : ""}`}>
                    <span className="min-w-0 truncate">{h.title}</span>
                    <span className="shrink-0 text-[11px] text-muted">{h.detail}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </form>
  );
}
