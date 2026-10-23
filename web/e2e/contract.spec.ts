import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { traceSample } from "../src/testing/samples";
import { base, expectAccessible, firstSnapshot, shotsDir } from "./helpers";

// UI wiring for the D-029 contract fields: RouteItem.label, TraceHop.hidden_rejected, Component.reason and the
// library layer. Live tests use the real API and read names from it; nothing is hard-coded to one repository.
const SHOTS = shotsDir("contract");

type Snap = { repoId: string; sha: string };
type Comp = { name: string; layer: string; reason?: string | null };

async function noSideways(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
}

const apiBase = (s: Snap) => `/api/v1/repos/${encodeURIComponent(s.repoId)}/snapshots/${s.sha}`;

/** Every ready snapshot in the store with its components. */
async function snapshotsWithComponents(request: APIRequestContext): Promise<{ snap: Snap; comps: Comp[] }[]> {
  const out: { snap: Snap; comps: Comp[] }[] = [];
  for (const r of (await (await request.get("/api/v1/repos")).json()) as { id: string }[]) {
    const snaps = (await (await request.get(`/api/v1/repos/${encodeURIComponent(r.id)}/snapshots`)).json()) as { sha: string; state: string }[];
    const s = snaps.find((x) => x.state === "ready");
    if (!s) continue;
    const snap = { repoId: r.id, sha: s.sha };
    const comps = (await (await request.get(`${apiBase(snap)}/components`)).json()) as Comp[];
    if (comps.length) out.push({ snap, comps });
  }
  return out;
}

test.describe("contract wiring", () => {
  let snap: Snap;
  test.beforeAll(async ({ request }) => {
    const s = await firstSnapshot(request);
    test.skip(!s, "needs an API with at least one snapshot");
    snap = s!;
  });

  test("RouteItem.label: the recorded name when present, nothing when null, separate from the status chip", async ({ page, request }, info) => {
    const items = (await (await request.get(`${apiBase(snap)}/routes`)).json()) as { label?: string | null }[];
    test.skip(items.length === 0, "no routes");
    await page.goto(`${base(snap)}/routes`);
    await expect(page.getByTestId("route-item")).toHaveCount(items.length);
    const named = items.filter((r) => typeof r.label === "string" && r.label.trim()).length;
    await expect(page.getByTestId("route-name")).toHaveCount(named);
    if (named) {
      const first = items.find((r) => typeof r.label === "string" && r.label.trim())!;
      await expect(page.getByTestId("route-name").first()).toContainText(first.label!.trim());
    }
    await expectAccessible(page);
    await noSideways(page);
    await page.screenshot({ path: `${SHOTS}/${info.project.name}-routes-label.png`, fullPage: true });
  });

  test("Component.reason replaces the path-rule note; layers match the API, library included", async ({ page, request }, info) => {
    const all = await snapshotsWithComponents(request);
    test.skip(all.length === 0, "no snapshot with components");
    for (const { snap: s, comps } of all) {
      const i = s.repoId.split("__").pop();
      await page.goto(`${base(s)}/components`);
      await expect(page.getByTestId("component-item")).toHaveCount(comps.length);
      expect(await page.getByTestId("component-layer").allTextContents()).toEqual(comps.map((c) => c.layer));
      const withReason = comps.filter((c) => !!c.reason).length;
      await expect(page.getByTestId("component-reason")).toHaveCount(withReason);
      await expect(page.getByTestId("component-rule")).toHaveCount(comps.length - withReason);
      await expect(page.getByTestId("layer-note")).toContainText(withReason === comps.length ? "the API's own reason for its layer" : "not a reading of what the code does");
      if (comps.some((c) => c.layer === "library")) {
        await page.getByLabel("Layer").selectOption("library");
        await expect(page.getByTestId("component-layer").first()).toHaveText("library");
        await page.getByLabel("Layer").selectOption("");
      }
      await expectAccessible(page);
      await noSideways(page);
      await page.screenshot({ path: `${SHOTS}/${info.project.name}-components-${i}.png`, fullPage: true });
      // Overview legend: one band per API layer present.
      await page.goto(base(s));
      const band = page.getByRole("region", { name: "Components by layer" });
      await expect(band).toBeVisible();
      for (const l of new Set(comps.map((c) => c.layer))) await expect(band.getByRole("heading", { level: 3, name: l, exact: true })).toBeVisible();
      await expectAccessible(page);
      await page.screenshot({ path: `${SHOTS}/${info.project.name}-overview-${i}.png`, fullPage: true });
      // Graph layer filter lists library like every other layer.
      await page.goto(`${base(s)}/graph`);
      await page.getByTestId("graph-filters").locator("summary").click();
      await expect(page.getByRole("checkbox", { name: "library" })).toHaveCount(1);
    }
  });

  test("TraceHop.hidden_rejected: a per-step count with a reviewer link; without it the snapshot note stays", async ({ page }, info) => {
    const withCount = { ...traceSample, hidden_counts: { rejected: 9 }, hops: traceSample.hops.map((h) => (h.type === "gap" ? { ...h, hidden_rejected: 2 } : h)) };
    await page.route("**/api/v1/repos/*/snapshots/*/trace?*", (r) => r.fulfill({ json: withCount }));
    const url = `${base(snap)}/trace?from=${encodeURIComponent(traceSample.from_symbol)}&to=${encodeURIComponent(traceSample.to_symbol!)}`;
    await page.goto(url);
    const gap = page.locator('[data-hop="gap"]').first();
    await expect(gap.getByTestId("gap-hidden-step")).toHaveText(/2 rejected claims hidden here\./);
    await expect(gap.getByTestId("gap-hidden")).toHaveCount(0);
    await expectAccessible(page);
    await gap.scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${SHOTS}/${info.project.name}-trace-gap-step.png`, fullPage: true });
    await gap.getByRole("link", { name: "Open the reviewer view" }).click();
    await expect(page).toHaveURL(/\/review/);

    await page.unroute("**/api/v1/repos/*/snapshots/*/trace?*");
    await page.route("**/api/v1/repos/*/snapshots/*/trace?*", (r) => r.fulfill({ json: { ...traceSample, hidden_counts: { rejected: 9 } } }));
    await page.goto(url);
    const old = page.locator('[data-hop="gap"]').first();
    await expect(old.getByTestId("gap-hidden")).toContainText("9 rejected relationships are hidden");
    await expect(old.getByTestId("gap-hidden-step")).toHaveCount(0);
  });
});
