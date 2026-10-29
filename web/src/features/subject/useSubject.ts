import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { decodeSubject, encodeSubject, type Subject } from "./subject";

/** The selected subject lives in `at` on the snapshot URL, so a copied link keeps it. */
export function useSubject() {
  const [sp, setSp] = useSearchParams();
  const subject = decodeSubject(sp.get("at"));
  const setSubject = useCallback(
    (next: Subject | null) => {
      setSp(
        (p) => {
          const n = new URLSearchParams(p);
          if (next) n.set("at", encodeSubject(next));
          else n.delete("at");
          return n;
        },
        { replace: true },
      );
    },
    [setSp],
  );
  return { subject, setSubject };
}
