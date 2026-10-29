/** The thing the user is looking at. It is a pointer into stored records, not a new relationship. */
export type Subject =
  | { kind: "component"; id: string; label: string }
  | { kind: "symbol"; id: string; label: string }
  | { kind: "file"; path: string }
  | { kind: "route"; method: string; path: string; handler: string };

export function encodeSubject(s: Subject): string {
  if (s.kind === "component") return `component\n${s.id}\n${s.label}`;
  if (s.kind === "symbol") return `symbol\n${s.id}\n${s.label}`;
  if (s.kind === "file") return `file\n${s.path}`;
  return `route\n${s.method}\n${s.path}\n${s.handler}`;
}

export function decodeSubject(raw: string | null): Subject | null {
  if (!raw) return null;
  const p = raw.split("\n");
  if (p[0] === "component" && p[1]) return { kind: "component", id: p[1], label: p[2] || p[1] };
  if (p[0] === "symbol" && p[1]) return { kind: "symbol", id: p[1], label: p[2] || p[1] };
  if (p[0] === "file" && p[1]) return { kind: "file", path: p[1] };
  if (p[0] === "route" && p[2]) return { kind: "route", method: p[1] || "", path: p[2], handler: p[3] || "" };
  return null;
}

/** Keep `at` on a link so the next page still knows what was selected. */
export function withAt(href: string, subject: Subject | null): string {
  if (!subject) return href;
  return `${href}${href.includes("?") ? "&" : "?"}at=${encodeURIComponent(encodeSubject(subject))}`;
}

export function subjectLabel(s: Subject): string {
  if (s.kind === "component" || s.kind === "symbol") return s.label;
  if (s.kind === "file") return s.path.split("/").pop() || s.path;
  return `${s.method} ${s.path}`.trim();
}

export function subjectKindLabel(s: Subject): string {
  if (s.kind === "component") return "Component";
  if (s.kind === "symbol") return "Symbol";
  if (s.kind === "file") return "File";
  return "Route";
}
