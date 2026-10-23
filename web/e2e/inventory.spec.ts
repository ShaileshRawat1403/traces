import { expect, test, type Page } from "@playwright/test";
import { componentsSample, traceSample } from "../src/testing/samples";
import { base, capabilities, expectAccessible, firstSnapshot, shotsDir } from "./helpers";

// Acceptance fixes (docs/ACCEPTANCE.md): G-3 real Routes, Components and Source views, O-2 gap wording, O-3 layer
// labels, F-7 intent routing. Live tests use the real API; names are discovered from it, never hard-coded.
const SHOTS = shotsDir("acceptance");

async function noSideways(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
}

test.describe("acceptance fixes", () => {
  let snap: { repoId: string; sha: string };
  let caps: Record<string, boolean>;
  let api = "";
  test.beforeAll(async ({ request }) => {
    const s = await firstSnapshot(request);
    test.skip(!s, "needs an API with at least one snapshot");
    snap = s!;
    caps = await capabilities(request);
    api = `/api/v1/repos/${encodeURIComponent(snap.repoId)}/snapshots/${snap.sha}`;
  });

  test("G-3 routes: real inventory, filter, labels, evidence drawer, keyboard", async ({ page, request }, info) => {
    test.skip(caps.routes === false, "routes not implemented by this API");
    const items = (await (await request.get(`${api}/routes`)).json()) as { path: string; claim_id: string | null }[];
    await page.goto(`${base(snap)}/routes`);
    await expect(page.getByRole("heading", { level: 1, name: "Routes" })).toBeVisible();
    await expect(page.getByTestId("routes-count")).toContainText(`of ${items.length} routes`);
    await expect(page.getByText("scheduled for the next UI checkpoint")).toHaveCount(0);
    test.skip(items.length === 0, "the snapshot has no routes");
    await expect(page.getByTestId("route-item")).toHaveCount(items.length);
    await expect(page.getByTestId("route-item").first().getByTestId("status-chip")).toBeVisible();
    await expect(page.locator('[data-testid="route-item"] [data-status="rejected"]')).toHaveCount(0);
    const target = items[items.length - 1]!.path;
    await page.getByLabel("Filter routes").fill(target);
    await expect(page).toHaveURL(/q=/);
    await expect(page.getByTestId("route-item").first()).toContainText(target);
    await expectAccessible(page);
    await noSideways(page);
    await page.screenshot({ path: `${SHOTS}/${info.project.name}-routes.png`, fullPage: true });
    // Keyboard: reach Open evidence with Tab and open the drawer with Enter.
    const btn = page.getByTestId("route-item").first().getByRole("button", { name: /Open evidence/ });
    await btn.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("evidence-drawer")).toBeVisible();
    await expectAccessible(page);
    await page.screenshot({ path: `${SHOTS}/${info.project.name}-routes-evidence.png`, fullPage: true });
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("evidence-drawer")).toBeHidden();
    await expect(btn).toBeFocused();
  });

  test("G-3 components and O-3: the API's layer with its rule, files open in Source", async ({ page, request }, info) => {
    test.skip(caps.components === false, "components not implemented by this API");
    type C = { name: string; layer: string; paths: string[] };
    // Use the first ready snapshot in the store that has components (a store may hold several repos).
    let target = snap;
    let comps = (await (await request.get(`${api}/components`)).json()) as C[];
    if (comps.length === 0) {
      for (const r of (await (await request.get("/api/v1/repos")).json()) as { id: string }[]) {
        const rid = encodeURIComponent(r.id);
        const snaps = (await (await request.get(`/api/v1/repos/${rid}/snapshots`)).json()) as { sha: string; state: string }[];
        const s = snaps.find((x) => x.state === "ready");
        if (!s) continue;
        const c = (await (await request.get(`/api/v1/repos/${rid}/snapshots/${s.sha}/components`)).json()) as C[];
        if (c.length > 0) {
          target = { repoId: r.id, sha: s.sha };
          comps = c;
          break;
        }
      }
    }
    await page.goto(`${base(target)}/components`);
    await expect(page.getByRole("heading", { level: 1, name: "Components" })).toBeVisible();
    await expect(page.getByTestId("components-count")).toContainText(`of ${comps.length} components`);
    await expect(page.getByTestId("layer-note")).toContainText("not a reading of what the code does");
    test.skip(comps.length === 0, "no components");
    expect(await page.getByTestId("component-layer").allTextContents()).toEqual(comps.map((c) => c.layer));
    await expect(page.locator('[data-testid="component-item"] [data-status="rejected"]')).toHaveCount(0);
    await expectAccessible(page);
    await noSideways(page);
    await page.screenshot({ path: `${SHOTS}/${info.project.name}-components.png`, fullPage: true });
    const withFiles = comps.findIndex((c) => c.paths.length > 0);
    test.skip(withFiles < 0, "no component files");
    const item = page.getByTestId("component-item").nth(withFiles);
    await item.locator("summary").click();
    await item.getByRole("link", { name: comps[withFiles]!.paths[0]! }).click();
    await expect(page).toHaveURL(/\/source\?path=/);
    await expect(page.getByTestId("source-page").or(page.getByRole("alert"))).toBeVisible();
  });

  test("G-3 components, contract shape: generic sample when the store has no components", async ({ page }, info) => {
    await page.route("**/api/v1/repos/*/snapshots/*/components", (r) => r.fulfill({ json: componentsSample }));
    await page.goto(`${base(snap)}/components`);
    await expect(page.getByTestId("component-item")).toHaveCount(componentsSample.length);
    expect(await page.getByTestId("component-layer").allTextContents()).toEqual(componentsSample.map((c) => c.layer));
    await page.getByLabel("Layer").selectOption(componentsSample[0]!.layer);
    await expect(page).toHaveURL(/layer=/);
    await expect(page.getByTestId("components-count")).toContainText(`of ${componentsSample.length} components`);
    await expectAccessible(page);
    await noSideways(page);
    await page.screenshot({ path: `${SHOTS}/${info.project.name}-components-shape.png`, fullPage: true });
  });

  test("G-3 source: a real file at the pinned commit, windowed, with claim links", async ({ page, request }, info) => {
    test.skip(caps.source === false, "source not implemented by this API");
    const rel = (await (await request.get(`${api}/claims?claim_kind=relationship&status=verified&limit=1`)).json()) as { items: { claim_id: string }[] };
    const rec = (await (await request.get(`${api}/claims/${rel.items[0]?.claim_id ?? "none"}`)).json()) as { locations?: { file: string; start_line: number; end_line: number }[] };
    const loc = rec.locations?.[0];
    test.skip(!loc, "no claim with a location");
    await page.goto(`${base(snap)}/source?path=${encodeURIComponent(loc!.file)}&start=${loc!.start_line}&end=${loc!.end_line}`);
    await expect(page.getByTestId("source-page")).toBeVisible();
    await expect(page.getByTestId("source-lines")).toContainText(loc!.file);
    await expect(page.locator("[data-hit]").first()).toBeVisible();
    await expect(page.getByText("scheduled for the next UI checkpoint")).toHaveCount(0);
    await expectAccessible(page);
    await noSideways(page);
    await page.screenshot({ path: `${SHOTS}/${info.project.name}-source.png`, fullPage: true });
    const claimBtn = page.getByRole("button", { name: /Open evidence for claim/ }).first();
    if (await claimBtn.count()) {
      await claimBtn.click();
      await expect(page.getByTestId("evidence-drawer")).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(page.getByTestId("evidence-drawer")).toBeHidden();
      await expect(claimBtn).toBeFocused();
    }
    // The path form opens another file, and a bad path is an honest error.
    await page.getByLabel("File path").fill("no/such/file.txt");
    await page.getByRole("button", { name: "Open file" }).click();
    await expect(page.getByRole("alert").or(page.getByTestId("not-available"))).toBeVisible();
  });

  test("Routes and Components are in the snapshot navigation", async ({ page, isMobile }) => {
    await page.goto(base(snap));
    if (isMobile) await page.getByRole("button", { name: "More" }).click();
    await expect(page.getByRole("link", { name: "Routes" }).first()).toBeVisible();
    await expect(page.getByRole("link", { name: "Components" }).first()).toBeVisible();
  });

  test("O-2: a gap says no static evidence connects the steps, and notes hidden rejected relationships", async ({ page }, info) => {
    const sample = { ...traceSample, hidden_counts: { rejected: 3 } };
    await page.route("**/api/v1/repos/*/snapshots/*/trace?*", (r) => r.fulfill({ json: sample }));
    await page.goto(`${base(snap)}/trace?from=${encodeURIComponent(traceSample.from_symbol)}&to=${encodeURIComponent(traceSample.to_symbol!)}`);
    const gap = page.locator('[data-hop="gap"]').first();
    await expect(gap.getByTestId("gap-meaning")).toContainText("No static evidence that Traces accepts connects these two steps");
    await expect(gap.getByTestId("gap-hidden")).toContainText("3 rejected relationships are hidden");
    await expectAccessible(page);
    await gap.scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${SHOTS}/${info.project.name}-trace-gap.png`, fullPage: true });
  });

  test("F-7: runtime and unsupported questions are unknown with a reason, never a guess", async ({ page }, info) => {
    test.skip(caps.explain === false, "explain not implemented by this API");
    await page.goto(`${base(snap)}/ask`);
    const ask = async (q: string) => {
      await page.getByLabel("Question about this snapshot").fill(q);
      await page.getByRole("button", { name: "Explain (no key needed)" }).click();
      await expect(page.getByTestId("explain")).toBeVisible();
    };
    await ask("Is this code slow at runtime?");
    await expect(page.getByTestId("answer-sentence")).toHaveCount(1);
    await expect(page.getByTestId("answer-sentence").first()).toHaveAttribute("data-standing", "unknown");
    await ask("tell me something interesting");
    await expect(page.getByTestId("answer-sentence")).toHaveCount(1);
    await expect(page.getByTestId("answer-sentence").first()).toContainText("Try one of");
    await expectAccessible(page);
    await page.screenshot({ path: `${SHOTS}/${info.project.name}-ask-unknown.png`, fullPage: true });
  });

  test("F-7: a dependency question about a real symbol lists only that symbol's relationships", async ({ page, request }, info) => {
    test.skip(caps.explain === false, "explain not implemented by this API");
    const p = (await (await request.get(`${api}/claims?claim_kind=relationship&status=verified&kind=depends_on&limit=1`)).json()) as { items: { from_symbol: string }[] };
    const sym = p.items[0]?.from_symbol;
    test.skip(!sym, "no depends_on claim");
    await page.goto(`${base(snap)}/ask`);
    await page.getByLabel("Question about this snapshot").fill(`What does ${sym} depend on?`);
    await page.getByRole("button", { name: "Explain (no key needed)" }).click();
    const sentences = page.getByTestId("answer-sentence");
    await expect(sentences.first()).toContainText("outgoing static relationship");
    const name = sym!.split("::").pop()!;
    for (const t of (await sentences.allTextContents()).slice(1)) expect(t).toContain(name);
    await expectAccessible(page);
    await page.screenshot({ path: `${SHOTS}/${info.project.name}-ask-dependencies.png`, fullPage: true });
  });
});
