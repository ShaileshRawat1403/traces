import { expect, test } from "@playwright/test";
import { base, capabilities, expectAccessible, firstSnapshot } from "./helpers";

test.describe("snapshot screens", () => {
  let snap: { repoId: string; sha: string };
  let caps: Record<string, boolean>;
  test.beforeAll(async ({ request }) => {
    const s = await firstSnapshot(request);
    test.skip(!s, "needs an API with at least one snapshot (see docs/SETUP.md, baseline import)");
    snap = s!;
    caps = await capabilities(request);
  });

  test("overview shows real evidence counts, the static disclaimer and an honest overview state", async ({ page }) => {
    await page.goto(base(snap));
    await expect(page.getByTestId("static-disclaimer")).toHaveText("Static analysis only. No runtime behavior has been observed.");
    await expect(page.getByTestId("snapshot-counts")).toBeVisible();
    await expect(page.getByTestId("snapshot-counts")).not.toContainText("Rejected");
    if (caps.overview === false) {
      await expect(page.getByTestId("not-available")).toContainText("Overview is not available yet");
      await expect(page.getByTestId("owner")).not.toHaveText("not stated by the API");
    }
    await expectAccessible(page);
  });

  test("claims list never shows Rejected and reports hidden counts", async ({ page }) => {
    await page.goto(`${base(snap)}/claims`);
    await expect(page.getByTestId("claim-list")).toBeVisible();
    await expect(page.getByTestId("hidden-counts")).toBeVisible();
    const labels = await page.getByTestId("status-chip").evaluateAll((els) => els.map((e) => e.getAttribute("data-label")));
    expect(labels.length).toBeGreaterThan(0);
    expect(labels).not.toContain("rejected");
    await expectAccessible(page);
  });

  test("reviewer view shows rejected claims labelled Rejected", async ({ page }) => {
    await page.goto(`${base(snap)}/review`);
    await expect(page.getByRole("note")).toContainText("Reviewer view");
    const list = page.getByTestId("claim-list");
    if (await list.isVisible()) {
      await expect(list.getByTestId("status-chip").first()).toContainText("Rejected");
    }
    await expectAccessible(page);
  });

  test("evidence page shows status, checks, locations and an honest source state", async ({ page }) => {
    await page.goto(`${base(snap)}/claims?status=verified`);
    await page.getByRole("link", { name: /Open evidence/ }).first().click();
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByRole("region", { name: /Checks/ })).toBeVisible();
    await expect(page.getByTestId("status-chip").first()).toContainText("Verified");
    await page.getByRole("button", { name: "Show source" }).first().click();
    if (caps.source === false) await expect(page.getByTestId("not-available")).toContainText("Source view is not available yet");
    await expectAccessible(page);
  });

  test("graph route is code-split and shows the API's state", async ({ page }) => {
    const chunks: string[] = [];
    page.on("request", (r) => chunks.push(r.url()));
    await page.goto(base(snap));
    await expect(page.getByTestId("snapshot-counts")).toBeVisible();
    expect(chunks.some((u) => /GraphPage/.test(u))).toBe(false);
    await page.goto(`${base(snap)}/graph`);
    if (caps.graph === false) await expect(page.getByTestId("not-available")).toContainText("graph is not available yet");
    expect(chunks.some((u) => /GraphPage/.test(u))).toBe(true);
    await expectAccessible(page);
  });

  for (const [path, what] of [
    ["components", "Components"],
    ["routes", "Routes"],
    ["history", "History"],
  ] as const) {
    test(`${path} shows the API's answer`, async ({ page }) => {
      await page.goto(`${base(snap)}/${path}`);
      await expect(page.getByRole("heading", { level: 1, name: what })).toBeVisible();
      const cap = path === "history" ? caps.history : caps[path];
      if (cap === false) await expect(page.getByTestId("not-available")).toBeVisible();
      await expectAccessible(page);
    });
  }

  test("ask posts to explain and shows the API's state", async ({ page }) => {
    await page.goto(`${base(snap)}/ask`);
    await page.getByLabel("Question about this snapshot").fill("What does this depend on?");
    await page.getByRole("button", { name: /Explain/ }).click();
    if (caps.explain === false) await expect(page.getByTestId("not-available")).toContainText("Explain is not available yet");
    await expectAccessible(page);
  });

  test("phone layout: bottom bar and More sheet", async ({ page, isMobile }) => {
    test.skip(!isMobile, "phone only");
    await page.goto(base(snap));
    const bar = page.getByRole("navigation", { name: "Snapshot sections, bottom bar" });
    await expect(bar).toBeVisible();
    await bar.getByRole("button", { name: "More sections" }).tap();
    const sheet = page.getByRole("dialog", { name: "More sections" });
    await expect(sheet).toBeVisible();
    await sheet.getByRole("link", { name: "Claims" }).tap();
    await expect(page).toHaveURL(/\/claims$/);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
});
