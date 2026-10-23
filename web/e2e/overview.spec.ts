import { expect, test } from "@playwright/test";
import { overviewSample } from "../src/testing/samples";
import { base, capabilities, expectAccessible, firstSnapshot } from "./helpers";

// Live: the real API. Contract-shape: only the not-yet-implemented overview endpoint is answered by the test with a
// generic, schema-typed Overview (src/testing/samples.ts) so the renderer is exercised at 1280 px and 360 px.
test.describe("overview", () => {
  let snap: { repoId: string; sha: string };
  let caps: Record<string, boolean>;
  test.beforeAll(async ({ request }) => {
    const s = await firstSnapshot(request);
    test.skip(!s, "needs an API with at least one snapshot");
    snap = s!;
    caps = await capabilities(request);
  });

  test("live: shows the API's overview state", async ({ page }) => {
    await page.goto(base(snap));
    if (caps.overview === false) await expect(page.getByTestId("not-available")).toContainText("Overview is not available yet");
    else await expect(page.getByTestId("overview")).toBeVisible();
    await expectAccessible(page);
  });

  test("contract-shape: grounded, interpretation and unknown are separated", async ({ page }) => {
    await page.route("**/api/v1/repos/*/snapshots/*/overview", (r) => r.fulfill({ json: overviewSample }));
    await page.goto(base(snap));
    const view = page.getByTestId("overview");
    await expect(view).toBeVisible();
    const panel = page.getByRole("tabpanel");
    await expect(panel.getByRole("group", { name: "Grounded in evidence" })).toBeVisible();
    await expect(panel.getByRole("group", { name: "Interpretation" })).toBeVisible();
    await expect(panel.getByRole("group", { name: "Unknown or unsupported" })).toBeVisible();
    await expectAccessible(page);
    await page.getByRole("tab", { name: /Business/ }).focus();
    await page.keyboard.press("ArrowRight");
    await expect(page.getByRole("tab", { name: /Architecture/ })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("tabpanel").getByTestId("fact-standing").filter({ hasText: "Unsupported" })).toHaveCount(1);
    await page.getByRole("tab", { name: /Implementation/ }).click();
    await expect(page.getByRole("group", { name: "Languages" })).toBeVisible();
    await expectAccessible(page);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
});
