import AxeBuilder from "@axe-core/playwright";
import { expect, type APIRequestContext, type Page } from "@playwright/test";

/** First registered repo with a ready snapshot, discovered through the real API (no fixture names in the specs). */
export async function firstSnapshot(request: APIRequestContext): Promise<{ repoId: string; sha: string } | null> {
  const repos = (await (await request.get("/api/v1/repos")).json()) as { id: string }[];
  for (const r of repos) {
    const snaps = (await (await request.get(`/api/v1/repos/${encodeURIComponent(r.id)}/snapshots`)).json()) as { sha: string; state: string }[];
    const s = snaps.find((x) => x.state === "ready") ?? snaps[0];
    if (s) return { repoId: r.id, sha: s.sha };
  }
  return null;
}

export async function capabilities(request: APIRequestContext): Promise<Record<string, boolean>> {
  return ((await (await request.get("/api/v1/meta")).json()) as { capabilities: Record<string, boolean> }).capabilities;
}

export const base = (s: { repoId: string; sha: string }) => `/r/${encodeURIComponent(s.repoId)}/s/${s.sha}`;

export async function expectAccessible(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
  const summary = results.violations.map((v) => `${v.id} (${v.impact}): ${v.nodes.length} nodes, e.g. ${v.nodes[0]?.target.join(" ")}`);
  expect(summary, summary.join("\n")).toEqual([]);
}
