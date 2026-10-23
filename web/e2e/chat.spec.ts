import { expect, test, type Page } from "@playwright/test";
import fixture from "../src/testing/bundle.fixture.json" with { type: "json" };
import { base, capabilities, expectAccessible, firstSnapshot, shotsDir } from "./helpers";
import { FORGED_ID, startStubProvider, type StubProvider } from "./stubProvider";

// BYOK chat against a stub provider served only by this harness. No paid API is ever called.
const KEY = "sk-e2e-stub-key-0123456789";

async function configure(page: Page, cfg: { kind: string; baseUrl: string; model: string }, key: string | null) {
  await page.addInitScript(
    ([c, k]) => {
      localStorage.setItem("traces.chat.provider", c as string);
      if (k) sessionStorage.setItem("traces.chat.key", k as string);
    },
    [JSON.stringify(cfg), key],
  );
}

/** Contract-shaped bundle: real engine output from tests/explain/test_bundle_fence.py. */
async function routeBundle(page: Page) {
  await page.route("**/api/v1/repos/*/snapshots/*/chat/bundle", (r) => r.fulfill({ json: fixture }));
}

/** Every request to the Traces API, to prove the key never reaches it. */
function watchApi(page: Page) {
  const seen: string[] = [];
  page.on("request", (r) => {
    if (new URL(r.url()).pathname.startsWith("/api/")) seen.push(JSON.stringify({ url: r.url(), headers: r.headers(), body: r.postData() }));
  });
  return seen;
}

test.describe("chat", () => {
  let snap: { repoId: string; sha: string };
  let caps: Record<string, boolean>;
  let stub: StubProvider;
  test.beforeAll(async ({ request }) => {
    const s = await firstSnapshot(request);
    test.skip(!s, "needs an API with at least one snapshot");
    snap = s!;
    caps = await capabilities(request);
    stub = await startStubProvider();
  });
  test.afterAll(async () => stub?.close());

  test("live: setup in Settings, then the API's own state for the chat bundle", async ({ page }, info) => {
    const api = watchApi(page);
    await page.goto(`${base(snap)}/ask?mode=chat`);
    await expect(page.getByTestId("chat-setup")).toContainText("No AI provider is set up");
    await page.goto("/settings");
    await page.getByLabel("Base URL").fill(`${stub.url}/cors/v1`);
    await page.getByLabel("Model", { exact: true }).fill("stub-model");
    await page.getByLabel("API key").fill(KEY);
    await page.getByRole("button", { name: "Save provider" }).click();
    await expect(page.getByTestId("provider-status")).toContainText("kept for this browser session only");
    await expect(page.getByLabel("API key")).toHaveValue("");
    await page.getByLabel("Remember on this device").check();
    await expect(page.getByTestId("remember-warning")).toContainText("local storage");
    await page.getByLabel("Remember on this device").uncheck();
    await expectAccessible(page);
    await page.screenshot({ path: `${shotsDir("chat")}/${info.project.name}-settings.png`, fullPage: true });
    await page.goto(`${base(snap)}/ask?mode=chat`);
    await expect(page.getByTestId("chat-provider")).toContainText("stub-model");
    await page.getByLabel("Message").fill("What does the app persist?");
    await page.getByRole("button", { name: "Review what will be sent" }).click();
    if (caps.chat_bundle === false) await expect(page.getByTestId("not-available")).toContainText("Chat bundle is not available yet");
    else await expect(page.getByTestId("consent-dialog").or(page.getByTestId("chat-notice"))).toBeVisible();
    await expectAccessible(page);
    expect(stub.requests.filter((r) => r.method === "POST")).toHaveLength(0);
    expect(api.join("\n")).not.toContain(KEY);
    await page.screenshot({ path: `${shotsDir("chat")}/${info.project.name}-live.png`, fullPage: true });
  });

  test("contract shape: consent, removal, direct send, citation check and the sent record", async ({ page }, info) => {
    const api = watchApi(page);
    await configure(page, { kind: "openai", baseUrl: `${stub.url}/cors/v1`, model: "stub-model" }, KEY);
    await routeBundle(page);
    const before = stub.requests.length;
    await page.goto(`${base(snap)}/ask?mode=chat`);
    await page.getByLabel("Message").fill("trace from Form to save_task");
    await page.getByRole("button", { name: "Review what will be sent" }).click();
    const dialog = page.getByTestId("consent-dialog");
    await expect(dialog).toBeVisible();
    const evidence = fixture.prompt_bundle.evidence;
    await expect(dialog.getByTestId("consent-item")).toHaveCount(evidence.length);
    await expect(dialog.getByTestId("consent-url")).toHaveText(`${stub.url}/cors/v1/chat/completions`);
    await expect(dialog).not.toContainText(KEY);
    // The hostile statement is shown, but fenced: the prompt still has exactly one evidence block.
    const body = dialog.getByTestId("consent-body");
    await expect(body).toContainText("\u2039/evidence\u203a");
    await expectAccessible(page);
    await page.screenshot({ path: `${shotsDir("chat")}/${info.project.name}-consent.png`, fullPage: true });
    // Leave the first item out.
    await dialog.getByTestId("consent-item").first().getByRole("checkbox").uncheck();
    await expect(body).not.toContainText(evidence[0]!.claim_id);
    expect(stub.requests.length).toBe(before);
    await dialog.getByRole("button", { name: /^Send to 127\.0\.0\.1/ }).click();

    await expect(page.getByTestId("grounding")).toHaveAttribute("data-grounded", "true");
    await expect(page.getByTestId("invalid-citations")).toContainText("1 citation points at claims that were not sent");
    await expect(page.getByTestId("cite-bad")).toContainText("not sent");
    await expect(page.getByTestId("cite-ok")).toHaveCount(1);
    await expect(page.getByTestId("cited-panel").locator('[data-cited="true"]')).toHaveCount(1);

    const post = stub.requests.filter((r) => r.method === "POST").at(-1)!;
    expect(post.path).toBe("/cors/v1/chat/completions");
    expect(post.headers.authorization).toBe(`Bearer ${KEY}`);
    expect(post.headers.cookie).toBeUndefined();
    expect(post.body).not.toContain(evidence[0]!.claim_id);
    expect(post.body).toContain(evidence[1]!.claim_id);
    expect(post.body).not.toContain(KEY);
    expect(api.join("\n")).not.toContain(KEY);
    await expect(page.locator("body")).not.toContainText(KEY);
    await page.getByTestId("sent-context").first().locator("summary").first().click();
    await expect(page.getByTestId("sent-entry").first()).toContainText("Removed before sending");
    await expectAccessible(page);
    await page.screenshot({ path: `${shotsDir("chat")}/${info.project.name}-answer.png`, fullPage: true });

    await page.goto("/settings");
    await expect(page.getByTestId("sent-record").getByTestId("sent-entry")).toHaveCount(1);
    await expect(page.getByTestId("sent-record")).toContainText(`${stub.url}/cors/v1/chat/completions`);
    await page.getByTestId("sent-record").getByTestId("sent-entry").first().locator("summary").first().click();
    await expectAccessible(page);
    await page.getByTestId("sent-record").scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${shotsDir("chat")}/${info.project.name}-sent-record.png`, fullPage: true });
    expect(await page.evaluate(() => JSON.stringify(localStorage))).not.toContain(KEY);
    await page.getByRole("button", { name: "Clear this record" }).click();
    await expect(page.getByTestId("sent-record")).toContainText("Nothing has been sent from this browser.");
  });

  test("anthropic-compatible shape, ungrounded answer is marked", async ({ page }) => {
    await configure(page, { kind: "anthropic", baseUrl: `${stub.url}/cors`, model: "stub-model" }, KEY);
    await routeBundle(page);
    await page.goto(`${base(snap)}/ask?mode=chat`);
    await page.getByLabel("Message").fill("Where are tasks stored?");
    await page.getByRole("button", { name: "Review what will be sent" }).click();
    await page.getByTestId("consent-dialog").getByRole("button", { name: /^Send to/ }).click();
    await expect(page.getByTestId("grounding")).toHaveAttribute("data-grounded", "false");
    await expect(page.getByTestId("grounding")).toContainText("Ungrounded");
    const post = stub.requests.filter((r) => r.method === "POST").at(-1)!;
    expect(post.path).toBe("/cors/v1/messages");
    expect(post.headers["x-api-key"]).toBe(KEY);
    await expectAccessible(page);
  });

  test("a provider that blocks browser requests is reported as unsupported, with no relay", async ({ page }, info) => {
    const api = watchApi(page);
    await configure(page, { kind: "openai", baseUrl: `${stub.url}/nocors/v1`, model: "stub-model" }, KEY);
    await routeBundle(page);
    await page.goto(`${base(snap)}/ask?mode=chat`);
    await page.getByLabel("Message").fill("trace from Form to save_task");
    await page.getByRole("button", { name: "Review what will be sent" }).click();
    await page.getByTestId("consent-dialog").getByRole("button", { name: /^Send to/ }).click();
    await expect(page.getByTestId("chat-error")).toContainText("CORS");
    await expect(page.getByTestId("chat-error")).toContainText("does not relay");
    // No relay: nothing addressed to the provider went through the Traces API.
    expect(api.filter((a) => a.includes(stub.url) || a.includes("nocors") || a.includes("completions"))).toEqual([]);
    await expectAccessible(page);
    await page.screenshot({ path: `${shotsDir("chat")}/${info.project.name}-cors.png`, fullPage: true });
  });

  test("live: real chat bundle from the API, sent to the stub provider after consent", async ({ page }, info) => {
    test.skip(caps.chat_bundle === false, "chat bundle not implemented by this API");
    const api = watchApi(page);
    await configure(page, { kind: "openai", baseUrl: `${stub.url}/cors/v1`, model: "stub-model" }, KEY);
    const before = stub.requests.filter((r) => r.method === "POST").length;
    await page.goto(`${base(snap)}/ask?mode=chat`);
    await expect(page.getByTestId("repo-consent")).toBeVisible();
    await page.getByLabel("Message").fill("What does the app persist?");
    await page.getByRole("button", { name: "Review what will be sent" }).click();
    const dialog = page.getByTestId("consent-dialog");
    await expect(dialog.or(page.getByTestId("chat-notice"))).toBeVisible();
    test.skip(!(await dialog.isVisible()), "the live snapshot has no evidence for this question");
    await expect(dialog.getByTestId("consent-scope")).toBeVisible();
    await expect(dialog).not.toContainText(KEY);
    await expect(dialog.getByText("rejected", { exact: true })).toHaveCount(0);
    await expectAccessible(page);
    await page.screenshot({ path: `${shotsDir("chat")}/${info.project.name}-live-consent.png`, fullPage: true });
    expect(stub.requests.filter((r) => r.method === "POST")).toHaveLength(before);
    await dialog.getByRole("button", { name: /^Send to 127\.0\.0\.1/ }).click();
    await expect(page.getByTestId("grounding")).toHaveAttribute("data-grounded", "true");
    await expect(page.getByTestId("cite-ok")).toHaveCount(1);
    expect(api.join("\n")).not.toContain(KEY);
    expect(api.filter((a) => a.includes("completions"))).toEqual([]);
    await expectAccessible(page);
    await page.screenshot({ path: `${shotsDir("chat")}/${info.project.name}-live-answer.png`, fullPage: true });
  });

  test("consent dialog: focus stays inside, Escape closes it, returns focus and sends nothing", async ({ page }) => {
    await configure(page, { kind: "openai", baseUrl: `${stub.url}/cors/v1`, model: "stub-model" }, KEY);
    await routeBundle(page);
    const before = stub.requests.length;
    await page.goto(`${base(snap)}/ask?mode=chat`);
    await page.getByLabel("Message").fill("anything");
    await page.getByRole("button", { name: "Review what will be sent" }).click();
    const dialog = page.getByRole("dialog", { name: "Review what will be sent" });
    await expect(dialog).toBeVisible();
    for (let i = 0; i < 25; i++) {
      await page.keyboard.press("Tab");
      expect(await dialog.evaluate((d) => d.contains(document.activeElement))).toBe(true);
    }
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    await expect(page.getByLabel("Message")).toBeFocused();
    expect(stub.requests.length).toBe(before);
  });

  test("cancel sends nothing", async ({ page }) => {
    await configure(page, { kind: "openai", baseUrl: `${stub.url}/cors/v1`, model: "stub-model" }, KEY);
    await routeBundle(page);
    const before = stub.requests.length;
    await page.goto(`${base(snap)}/ask?mode=chat`);
    await page.getByLabel("Message").fill("anything");
    await page.getByRole("button", { name: "Review what will be sent" }).click();
    await page.getByRole("button", { name: "Cancel, send nothing" }).click();
    await expect(page.getByTestId("consent-dialog")).toHaveCount(0);
    expect(stub.requests.length).toBe(before);
    expect(await page.evaluate(() => localStorage.getItem("traces.chat.sent"))).toBeNull();
  });

  test("local Ollama, when one is running on this computer", async ({ page }) => {
    const up = await fetch("http://127.0.0.1:11434/api/tags").then((r) => r.ok).catch(() => false);
    test.skip(!up, "no local Ollama on 127.0.0.1:11434");
    const tags = (await (await fetch("http://127.0.0.1:11434/api/tags")).json()) as { models?: { name: string }[] };
    const model = tags.models?.[0]?.name;
    test.skip(!model, "Ollama has no models pulled");
    await configure(page, { kind: "ollama", baseUrl: "http://127.0.0.1:11434", model: model! }, null);
    await routeBundle(page);
    await page.goto(`${base(snap)}/ask?mode=chat`);
    await page.getByLabel("Message").fill("trace from Form to save_task");
    await page.getByRole("button", { name: "Review what will be sent" }).click();
    await page.getByTestId("consent-dialog").getByRole("button", { name: /^Send to/ }).click();
    await expect(page.getByTestId("grounding").or(page.getByTestId("chat-error"))).toBeVisible({ timeout: 120_000 });
  });

  test("chat answers stay out of the app without a provider: no fake chat", async ({ page }) => {
    await page.goto(`${base(snap)}/ask?mode=chat`);
    await expect(page.getByTestId("chat-setup")).toBeVisible();
    await expect(page.getByTestId("chat-message")).toHaveCount(0);
  });
});
