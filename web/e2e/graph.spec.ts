import { expect, test, type Page } from "@playwright/test";
import { componentsSample, graphComponentsSample, graphSymbolsSample, sourceSample } from "../src/testing/samples";
import { base, capabilities, expectAccessible, firstSnapshot } from "./helpers";

const SHOTS = "/workspace/traces-ui-shots/graph";

// Live: the real API. Contract-shape: only the not-yet-implemented graph, components and source endpoints are answered
// by the test with generic schema-typed samples; claims come from the real API (a real verified claim id is put on the
// sample's verified edge so the evidence drawer reads real evidence).
test.describe("graph", () => {
  let snap: { repoId: string; sha: string };
  let caps: Record<string, boolean>;
  let realClaim: string | null = null;
  test.beforeAll(async ({ request }) => {
    const s = await firstSnapshot(request);
    test.skip(!s, "needs an API with at least one snapshot");
    snap = s!;
    caps = await capabilities(request);
    const page = await (await request.get(`/api/v1${base(snap).replace("/r/", "/repos/").replace("/s/", "/snapshots/")}/claims?status=verified&claim_kind=relationship&limit=1`)).json();
    realClaim = (page as { items: { claim_id: string }[] }).items[0]?.claim_id ?? null;
  });

  async function routeContract(page: Page, requests: URL[]) {
    const verifiedId = graphSymbolsSample.edges.find((e) => e.status === "verified")!.id;
    const symbols = { ...graphSymbolsSample, edges: graphSymbolsSample.edges.map((e) => (e.id === verifiedId && realClaim ? { ...e, id: realClaim } : e)) };
    await page.route("**/api/v1/repos/*/snapshots/*/graph?*", (r) => {
      const u = new URL(r.request().url());
      requests.push(u);
      return r.fulfill({ json: u.searchParams.has("focus") ? symbols : graphComponentsSample });
    });
    await page.route("**/api/v1/repos/*/snapshots/*/components", (r) => r.fulfill({ json: componentsSample }));
    await page.route("**/api/v1/repos/*/snapshots/*/source?*", (r) => {
      const u = new URL(r.request().url());
      const start = Number(u.searchParams.get("start") ?? 1);
      return r.fulfill({ json: sourceSample(u.searchParams.get("path") ?? "x", start, Number(u.searchParams.get("end") ?? start + 10), 400) });
    });
  }

  test("live: shows the API's graph state", async ({ page }, info) => {
    await page.goto(`${base(snap)}/graph`);
    if (caps.graph === false) await expect(page.getByTestId("not-available")).toContainText("not available yet");
    else await expect(page.getByTestId("graph-summary")).toBeVisible();
    await expectAccessible(page);
    await page.screenshot({ path: `${SHOTS}/${info.project.name}-live.png`, fullPage: true });
  });

  test("contract-shape: components first, keyboard expansion, no rejected, inferred off by default", async ({ page }, info) => {
    const requests: URL[] = [];
    await routeContract(page, requests);
    await page.goto(`${base(snap)}/graph`);
    await expect(page.getByTestId("graph-summary")).toContainText("2 nodes, 1 relationships");
    const first = requests[0]!;
    expect(first.searchParams.getAll("status")).toEqual(["verified", "observed"]);
    expect(first.searchParams.has("include_rejected")).toBe(false);
    expect(first.searchParams.has("focus")).toBe(false);
    await expectAccessible(page);
    await page.screenshot({ path: `${SHOTS}/${info.project.name}-components.png`, fullPage: true });

    const canvas = page.getByTestId("graph-canvas");
    await canvas.focus();
    await page.keyboard.press("ArrowRight");
    const panel = page.getByTestId("selection-panel");
    await expect(panel).toBeVisible();
    await expect(panel.getByTestId("component-counts")).toBeVisible();
    await expect(page.getByTestId("graph-announce")).not.toBeEmpty();
    await canvas.focus();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/focus=/);
    await expect(page.getByTestId("graph-summary")).toContainText("4 nodes, 3 relationships");
    expect(requests.at(-1)!.searchParams.get("depth")).toBe("1");
    await expect(page.getByTestId("focus-bar")).toBeVisible();
    await expectAccessible(page);
    await page.screenshot({ path: `${SHOTS}/${info.project.name}-expanded.png`, fullPage: true });
  });

  test("contract-shape: list view opens the evidence drawer with pinned source lines", async ({ page }, info) => {
    test.skip(!realClaim, "needs a verified relationship claim in the store");
    const requests: URL[] = [];
    await routeContract(page, requests);
    await page.goto(`${base(snap)}/graph?focus=${encodeURIComponent(graphSymbolsSample.nodes[0]!.id)}&view=list`);
    const list = page.getByTestId("graph-list");
    // The focused node starts selected, so the list shows its own relationships first.
    await expect(list.getByRole("listitem")).toHaveCount(2);
    await page.getByRole("button", { name: "Clear selection" }).click();
    await expect(list.getByRole("listitem")).toHaveCount(3);
    await expect(list).not.toContainText("Rejected");
    await expect(list.getByText("Inferred").first()).toBeVisible();
    await expectAccessible(page);
    await list.getByRole("listitem").filter({ hasText: "Verified" }).getByRole("button", { name: "Open evidence" }).click();
    const drawer = page.getByTestId("evidence-drawer");
    await expect(drawer).toBeVisible();
    await expect(drawer.getByTestId("source-lines")).toBeVisible();
    await expect(drawer.getByTestId("source-lines").locator("[data-hit]").first()).toBeVisible();
    await expect(page).toHaveURL(/claim=c_/);
    await expectAccessible(page);
    await page.screenshot({ path: `${SHOTS}/${info.project.name}-drawer.png` });
    await page.keyboard.press("Escape");
    await expect(drawer).toBeHidden();
    await expect(page).not.toHaveURL(/claim=/);
  });

  test("contract-shape: filters and cards, no horizontal overflow", async ({ page }, info) => {
    const requests: URL[] = [];
    await routeContract(page, requests);
    await page.goto(`${base(snap)}/graph?view=cards`);
    await expect(page.getByTestId("graph-cards").getByRole("listitem")).toHaveCount(2);
    await page.getByTestId("graph-filters").locator("summary").click();
    await page.getByLabel("Inferred (unvalidated)").check();
    await expect.poll(() => requests.at(-1)!.searchParams.getAll("status")).toContain("unvalidated");
    expect(requests.at(-1)!.searchParams.getAll("status")).not.toContain("rejected");
    await page.getByLabel("frontend").check();
    await expect.poll(() => requests.at(-1)!.searchParams.getAll("layer")).toEqual(["frontend"]);
    // At 360 px the checkbox scrolls the search button under the sticky header; axe then reports it as an obscured
    // target. Check from the top of the page, where nothing overlaps.
    await page.evaluate(() => window.scrollTo(0, 0));
    await expectAccessible(page);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(0);
    await page.screenshot({ path: `${SHOTS}/${info.project.name}-cards-filters.png`, fullPage: true });
  });
});
