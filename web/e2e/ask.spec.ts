import { expect, test } from "@playwright/test";
import { explainBundleSample, explainSample } from "../src/testing/samples";
import { base, capabilities, expectAccessible, firstSnapshot, shotsDir } from "./helpers";

const SHOTS = shotsDir("ask");

// Live: the real API. Contract-shape: only the not-yet-wired explain endpoint is answered with a generic, schema-typed
// ExplainResponse; the request body the app sends is checked against the contract.
test.describe("ask", () => {
  let snap: { repoId: string; sha: string };
  let caps: Record<string, boolean>;
  test.beforeAll(async ({ request }) => {
    const s = await firstSnapshot(request);
    test.skip(!s, "needs an API with at least one snapshot");
    snap = s!;
    caps = await capabilities(request);
  });

  test("live: shows the API's explain state", async ({ page }, info) => {
    await page.goto(`${base(snap)}/ask`);
    await page.getByLabel("Question about this snapshot").fill("Which routes are declared?");
    await page.getByRole("button", { name: "Explain (no key needed)" }).click();
    if (caps.explain === false) await expect(page.getByTestId("not-available")).toContainText("Explain is not available yet");
    else await expect(page.getByTestId("explain")).toBeVisible();
    await expectAccessible(page);
    await page.screenshot({ path: `${SHOTS}/${info.project.name}-live.png`, fullPage: true });
  });

  test("contract-shape: every sentence is tagged, and the bundle preview lists what would be sent", async ({ page }, info) => {
    const bodies: unknown[] = [];
    await page.route("**/api/v1/repos/*/snapshots/*/explain", async (r) => {
      const body = r.request().postDataJSON() as { mode: string };
      bodies.push(body);
      await r.fulfill({ json: body.mode === "prepare_bundle" ? explainBundleSample : explainSample });
    });
    await page.goto(`${base(snap)}/ask`);
    await page.getByLabel("Question about this snapshot").fill("How is a task saved?");
    await page.getByRole("button", { name: "Explain (no key needed)" }).click();
    const sentences = page.getByTestId("answer-sentence");
    await expect(sentences).toHaveCount(explainSample.answer.length);
    expect(await sentences.evaluateAll((els) => els.map((e) => e.getAttribute("data-standing")))).toEqual(["unknown", "interpretation", "grounded", "interpretation", "grounded"]);
    expect(bodies[0]).toEqual({ question: "How is a task saved?", mode: "no_llm", focus_claim_ids: [] });
    await page.getByTestId("citations").locator("summary").click();
    await expectAccessible(page);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(0);
    await page.screenshot({ path: `${SHOTS}/${info.project.name}-answer.png`, fullPage: true });

    await page.getByRole("button", { name: "Preview what an AI would receive" }).click();
    const out = page.getByTestId("outbound");
    await expect(out).toContainText("Nothing has been sent");
    await expect(out.getByRole("row")).toHaveCount(1 + explainBundleSample.outbound_manifest.length);
    expect((bodies[1] as { mode: string }).mode).toBe("prepare_bundle");
    await page.evaluate(() => window.scrollTo(0, 0));
    await expectAccessible(page);
    await page.screenshot({ path: `${SHOTS}/${info.project.name}-bundle-preview.png`, fullPage: true });
  });
});
