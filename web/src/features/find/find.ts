import { recordedQuestion } from "../ask/recordedQuestion";

export interface FindComponent {
  id: string;
  name: string;
  layer: string;
  paths: readonly string[];
}

export interface FindRoute {
  method: string;
  path: string;
  file: string;
  line: number;
  handler_symbol: string | null;
}

export interface FindHit {
  id: string;
  kind: "component" | "route" | "file" | "handler";
  title: string;
  detail: string;
  href: string;
}

const LIMIT = 8;

function score(text: string, q: string): number | null {
  const t = text.toLowerCase();
  if (t === q) return 0;
  if (t.startsWith(q)) return 1;
  const i = t.indexOf(q);
  return i < 0 ? null : 2 + i / 1000;
}

function routeQuestion(method: string, path: string): string | null {
  if (method === "UNKNOWN" || method === "USE" || !path.startsWith("/")) return null;
  return `What does ${method} ${path} do?`;
}

/** Stored components, routes, files, and handlers that match the query. Nothing is inferred. */
export function findInSnapshot(query: string, components: readonly FindComponent[], routes: readonly FindRoute[], base: string): FindHit[] {
  const q = query.trim().toLowerCase();
  if (q.length < 2) return [];
  const ranked: { rank: number; hit: FindHit }[] = [];
  const push = (rank: number, hit: FindHit) => ranked.push({ rank, hit });

  for (const c of components) {
    const rank = score(c.name, q);
    if (rank !== null) {
      push(rank, { id: `component:${c.id}`, kind: "component", title: c.name, detail: c.layer, href: `${base}/graph?focus=${encodeURIComponent(c.id)}` });
    }
  }

  const files = new Set<string>();
  for (const c of components) {
    for (const p of c.paths) {
      if (files.has(p)) continue;
      const rank = score(p, q);
      if (rank === null) continue;
      files.add(p);
      push(rank + 0.2, { id: `file:${p}`, kind: "file", title: p, detail: "file", href: `${base}/source?path=${encodeURIComponent(p)}` });
    }
  }

  const handlers = new Set<string>();
  for (const r of routes) {
    const label = `${r.method} ${r.path}`.trim();
    const routeRank = score(label, q) ?? score(r.path, q);
    if (routeRank !== null) {
      const question = routeQuestion(r.method, r.path);
      push(routeRank + 0.1, {
        id: `route:${r.method}:${r.path}`,
        kind: "route",
        title: r.method === "UNKNOWN" ? r.path || "(path not recorded)" : label,
        detail: question ? "ask" : "route",
        href: question ? `${base}/ask?q=${encodeURIComponent(question)}` : `${base}/routes?q=${encodeURIComponent(r.path)}`,
      });
    }
    if (r.handler_symbol && !handlers.has(r.handler_symbol)) {
      const rank = score(r.handler_symbol, q);
      if (rank !== null) {
        handlers.add(r.handler_symbol);
        const question = recordedQuestion(r.handler_symbol);
        push(rank + 0.3, {
          id: `handler:${r.handler_symbol}`,
          kind: "handler",
          title: r.handler_symbol,
          detail: "handler",
          href: question ? `${base}/ask?q=${encodeURIComponent(question)}` : `${base}/trace?from=${encodeURIComponent(r.handler_symbol)}`,
        });
      }
    }
  }

  ranked.sort((a, b) => a.rank - b.rank || a.hit.title.localeCompare(b.hit.title));
  const seen = new Set<string>();
  const out: FindHit[] = [];
  for (const row of ranked) {
    if (seen.has(row.hit.id)) continue;
    seen.add(row.hit.id);
    out.push(row.hit);
    if (out.length >= LIMIT) break;
  }
  return out;
}
