import { useRef, type RefObject } from "react";
import { useSearchParams } from "react-router-dom";

/** Evidence drawer state in the URL (?claim=), the same convention as the graph. */
export function useDrawerClaim(): [string | null, (id: string | null) => void, RefObject<HTMLElement | null>] {
  const [sp, setSp] = useSearchParams();
  const opener = useRef<HTMLElement | null>(null);
  const set = (id: string | null) => {
    if (id && document.activeElement instanceof HTMLElement) opener.current = document.activeElement;
    const n = new URLSearchParams(sp);
    if (id) n.set("claim", id);
    else n.delete("claim");
    setSp(n, { replace: false });
  };
  return [sp.get("claim"), set, opener];
}

/** A filter value kept in the URL so views are shareable and survive reloads. */
export function useParam(name: string): [string, (v: string) => void] {
  const [sp, setSp] = useSearchParams();
  const set = (v: string) => {
    const n = new URLSearchParams(sp);
    if (v) n.set(name, v);
    else n.delete(name);
    setSp(n, { replace: true });
  };
  return [sp.get(name) ?? "", set];
}
