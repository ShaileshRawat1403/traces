import { expect, test } from "@playwright/test";
import { traceSample } from "../src/testing/samples";
import { base, capabilities, expectAccessible, firstSnapshot } from "./helpers";

const SHOTS = "/workspace/traces-ui-shots/trace";

// Live: the real API. Contract-shape: only the not-yet-implemented trace endpoint is answered with a generic
// schema-typed TraceResponse; a real claim id from the store is put on the library contract hop so the drawer is real.
test.describe("trace", () => {
  let snap: { repoId: string; sha: string };
  let caps: Record<string, boolean>;
  let real: { claim_id: string; from_symbol: string } | null = null;
  test.beforeAll(async ({ request }) => {
    const s = await firstSnapshot(request);
    test.skip(!s, "needs an API with at least one snapshot");
    snap = s!;
    caps = await capabilities(request);
    const p = await (await request.get(`/api/v1/repos/${encodeURIComponent(snap.repoId)}/snapshots/${snap.sha}/claims?claim_kind=relationship&status=verified&limit=1`)).json();
    real = (p as { items: { claim_id: string; from_symbol: string }[] }).items[0] ?? null;
  });

  test("live: submitting a real symbol shows the API's trace state", async ({ page }, info) => {
    await page.goto(`${base(snap)}/trace`);
    await page.getByLabel("From symbol").fill(real?.from_symbol ?? "x::y");
    await page.getByRole("button", { name: "Trace", exact: true }).click();
    await expect(page).toHaveURL(/from=/);
    if (caps.trace === false) await expect(page.getByTestId("not-available")).toContainText("Trace is not available yet");
    else await expect(page.getByTestId("trace")).toBeVisible();
    await expectAccessible(page);
    await page.screenshot({ path: `${SHOTS}/${info.project.name}-live.png`, fullPage: true });
  });

  test("contract-shape: ordered steps, gaps and library contract steps are explicit inferred items", async ({ page }, info) => {
    const lib = traceSample.hops.find((h) => h.type === "library_contract")!;
    const sample = { ...traceSample, hops: traceSample.hops.map((h) => (h === lib && real ? { ...h, claim_id: real.claim_id } : h)) };
    await page.route("**/api/v1/repos/*/snapshots/*/trace?*", (r) => r.fulfill({ json: sample }));
    await page.goto(`${base(snap)}/trace?from=${encodeURIComponent(traceSample.from_symbol)}&to=${encodeURIComponent(traceSample.to_symbol!)}`);
    const steps = page.getByRole("list", { name: "Trace steps in order" }).getByRole("listitem");
    await expect(steps).toHaveCount(5);
    expect(await steps.evaluateAll((els) => els.map((e) => e.getAttribute("data-hop")))).toEqual(["edge", "edge", "library_contract", "gap", "edge"]);
    await expect(steps.nth(3)).toContainText("Gap: no recorded relationship");
    await expect(steps.nth(3).getByTestId("hop-reason")).toContainText("dependency injection");
    await expect(steps.nth(2).getByTestId("hop-reason")).toBeVisible();
    await expect(page.getByTestId("trace-incomplete")).toBeVisible();
    await expectAccessible(page);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(0);
    await page.screenshot({ path: `${SHOTS}/${info.project.name}-contract-shape.png`, fullPage: true });
    if (real) {
      await steps.nth(2).getByRole("button", { name: "Open evidence" }).click();
      await expect(page.getByTestId("evidence-drawer")).toBeVisible();
      await expectAccessible(page);
      await page.keyboard.press("Escape");
      await expect(page.getByTestId("evidence-drawer")).toBeHidden();
    }
  });
});
