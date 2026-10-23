import { expect, test, type Page } from "@playwright/test";
import { cochangeSample, compareSample, HISTORY_SHAS, historyRecords, hotspotsSample, milestonesSample, timelineSample } from "../src/testing/samples";
import { base, capabilities, expectAccessible, firstSnapshot, shotsDir } from "./helpers";

const SHOTS = shotsDir("history");

// Live: the real API (history endpoints are 501 until the History seat wires them). Contract-shape: only the history
// and compare endpoints, and the claim-by-id lookups for the samples' own ids (which do not exist in the store), are
// answered with generic schema-typed samples. Every other request reaches the real API.
async function routeHistory(page: Page) {
  await page.route("**/api/v1/repos/*/snapshots/*/history/timeline*", (r) => r.fulfill({ json: timelineSample }));
  await page.route("**/api/v1/repos/*/snapshots/*/history/hotspots*", (r) => r.fulfill({ json: hotspotsSample }));
  await page.route("**/api/v1/repos/*/snapshots/*/history/cochange*", (r) => r.fulfill({ json: cochangeSample }));
  await page.route("**/api/v1/repos/*/snapshots/*/history/milestones*", (r) => r.fulfill({ json: milestonesSample }));
  await page.route("**/api/v1/repos/*/compare?*", (r) => r.fulfill({ json: compareSample }));
  await page.route("**/api/v1/repos/*/snapshots/*/claims/*", (r) => {
    const id = decodeURIComponent(new URL(r.request().url()).pathname.split("/").pop() ?? "");
    const rec = historyRecords[id];
    return rec ? r.fulfill({ json: rec }) : r.fallback();
  });
}

const noOverflow = async (page: Page) => expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);

test.describe("history", () => {
  let snap: { repoId: string; sha: string };
  let caps: Record<string, boolean>;
  test.beforeAll(async ({ request }) => {
    const s = await firstSnapshot(request);
    test.skip(!s, "needs an API with at least one snapshot");
    snap = s!;
    caps = await capabilities(request);
  });

  test("live: every history view shows the API's state", async ({ page }, info) => {
    for (const tab of ["timeline", "hotspots", "cochange", "milestones"]) {
      await page.goto(`${base(snap)}/history?tab=${tab}`);
      if (caps.history === false) await expect(page.getByTestId("not-available")).toContainText("not available yet");
      else await expect(page.getByTestId("history-summary")).toBeVisible();
      await expectAccessible(page);
    }
    await page.goto(`${base(snap)}/history?tab=compare&base=${HISTORY_SHAS.C1}&head=${snap.sha}`);
    if (caps.compare === false) await expect(page.getByTestId("not-available")).toContainText("not available yet");
    await expectAccessible(page);
    await page.screenshot({ path: `${SHOTS}/${info.project.name}-live.png`, fullPage: true });
  });

  test("contract-shape: timeline with criteria echo, rejected hidden, evidence with citations", async ({ page }, info) => {
    await routeHistory(page);
    await page.goto(`${base(snap)}/history`);
    const items = page.getByTestId("history-item");
    await expect(items).toHaveCount(4);
    await expect(page.getByTestId("hidden-counts")).toContainText("1 rejected");
    const criteria = page.getByTestId("criteria");
    await expect(criteria.getByTestId("criteria-set")).toHaveCount(1);
    await expect(criteria.getByLabel("Parameters, verbatim")).toContainText('"rename_threshold": 50');
    await expect(items.filter({ hasText: "PR #12" })).toContainText("Quoted rationale, not proof of intent.");
    await expect(items.filter({ hasText: "Suggested alias" })).toContainText("suggested, not confirmed");
    await expectAccessible(page);
    await noOverflow(page);
    await page.screenshot({ path: `${SHOTS}/${info.project.name}-timeline.png`, fullPage: true });
    await items.filter({ hasText: "renamed" }).getByRole("button", { name: "Open evidence" }).click();
    const drawer = page.getByTestId("evidence-drawer");
    await expect(drawer.getByTestId("history-citations")).toContainText("Git similarity 87%");
    await expect(drawer.getByLabel("Record parameters")).toContainText("rename_limit");
    await expectAccessible(page);
    await page.keyboard.press("Escape");
    await expect(drawer).toBeHidden();
  });

  test("contract-shape: hotspots and co-change charts have text equivalents and pattern wording", async ({ page }, info) => {
    await routeHistory(page);
    await page.goto(`${base(snap)}/history?tab=hotspots`);
    const chart = page.getByTestId("bar-chart");
    await expect(chart.getByRole("row")).toHaveCount(1 + hotspotsSample.items.length);
    await expect(chart).toContainText("hotspot_score");
    await expect(page.getByTestId("history-item").first()).toContainText("Count checked against Git, not a confirmed relationship");
    await page.getByLabel("Chart metric").selectOption("revisions");
    await expect(chart.getByRole("row").nth(1)).toContainText("30");
    await expectAccessible(page);
    await noOverflow(page);
    await page.screenshot({ path: `${SHOTS}/${info.project.name}-hotspots.png`, fullPage: true });

    await page.getByRole("tab", { name: "Co-change" }).click();
    await expect(page).toHaveURL(/tab=cochange/);
    await expect(page.getByTestId("cochange-caveat")).toContainText("not evidence of a code dependency");
    await expect(page.getByTestId("cochange-text").first()).toHaveText("changed together in 18 of 19 commits. History pattern.");
    const text = (await page.getByRole("main").textContent()) ?? "";
    for (const banned of ["depends on", "causes", "is coupled to", "breaks when"]) expect(text).not.toContain(banned);
    await expectAccessible(page);
    await noOverflow(page);
    await page.screenshot({ path: `${SHOTS}/${info.project.name}-cochange.png`, fullPage: true });
  });

  test("contract-shape: milestones feed compare; compare groups added and removed", async ({ page }, info) => {
    await routeHistory(page);
    await page.goto(`${base(snap)}/history?tab=milestones`);
    await expect(page.getByTestId("history-item")).toHaveCount(2);
    await page.getByRole("button", { name: `Compare from ${HISTORY_SHAS.C1.slice(0, 7)}` }).click();
    await expect(page).toHaveURL(new RegExp(`tab=compare.*base=${HISTORY_SHAS.C1}|base=${HISTORY_SHAS.C1}.*tab=compare`));
    await expect(page.getByLabel("Base commit (40-hex SHA)")).toHaveValue(HISTORY_SHAS.C1);
    await expect(page.getByTestId("compare-added").getByTestId("history-item")).toHaveCount(1);
    await expect(page.getByTestId("compare-removed").getByTestId("history-item")).toHaveCount(1);
    await expectAccessible(page);
    await noOverflow(page);
    await page.screenshot({ path: `${SHOTS}/${info.project.name}-compare.png`, fullPage: true });
    await page.getByLabel("Base commit (40-hex SHA)").fill("abc123");
    await expect(page.getByRole("button", { name: "Compare", exact: true })).toBeDisabled();
  });
});
