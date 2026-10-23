import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ExplainResponse, Repo } from "../../api/client";
import fixture from "../../testing/bundle.fixture.json";
import { assemblePrompt, keptManifest, outgoing, readBundle } from "./bundle";
import { ChatPanel } from "./ChatPanel";
import { checkCitations, pieces } from "./citations";
import { STORAGE_KEYS, clearKey, loadKey, saveConfig, saveKey } from "./keyStore";
import { ProviderSettings } from "./ProviderSettings";
import { REDACTED, buildRequest, checkBaseUrl, parseAnswer, send, type ProviderConfig } from "./providers";
import { LOG_CAP, appendLog, readLog, type SentEntry } from "./sentLog";

// The fixture is real engine output (tests/explain/test_bundle_fence.py keeps it current), including a hostile statement.
const BUNDLE = fixture as unknown as ExplainResponse;
const KEY = "sk-test-0123456789abcdef";
const OPENAI: ProviderConfig = { kind: "openai", baseUrl: "https://llm.example.test/v1", model: "m-1" };
const ids = () => readBundle(BUNDLE)!.evidence.map((e) => e.claim_id);
const FORGED = "c_" + "f".repeat(64);

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("bundle", () => {
  it("rebuilds the server prompt exactly, and drops removed items", () => {
    const b = readBundle(BUNDLE)!;
    expect(b.format).toBe("traces-bundle/1");
    expect(b.rebuildable).toBe(true);
    expect(assemblePrompt(b, new Set())).toBe(b.prompt);
    const drop = b.evidence[0]!.claim_id;
    const out = outgoing(b, new Set([drop]));
    expect(out.prompt).not.toContain(drop);
    expect(out.claimIds).toEqual(b.evidence.slice(1).map((e) => e.claim_id));
    expect(keptManifest(BUNDLE.outbound_manifest, new Set([drop])).some((m) => m.claim_id === drop)).toBe(false);
  });

  it("keeps the hostile item fenced: one evidence block, one question block", () => {
    const p = readBundle(BUNDLE)!.prompt;
    expect(p.split("</evidence>")).toHaveLength(2);
    expect(p.split("<question>")).toHaveLength(2);
  });

  it("refuses removal when the prompt cannot be rebuilt", () => {
    const tampered = { ...BUNDLE, prompt_bundle: { ...BUNDLE.prompt_bundle, prompt: `${(BUNDLE.prompt_bundle as { prompt: string }).prompt} ` } };
    const b = readBundle(tampered)!;
    expect(b.rebuildable).toBe(false);
    expect(outgoing(b, new Set([b.evidence[0]!.claim_id])).prompt).toBe(b.prompt);
  });

  it("never sends rejected claims: strips them when the prompt can be rebuilt, refuses the bundle otherwise", () => {
    const pb = BUNDLE.prompt_bundle as { instructions: string; question: string; evidence: Record<string, string>[] };
    const evidence = pb.evidence.map((e, i) => (i === 0 ? { ...e, status: "rejected", label: "rejected" } : e));
    const prompt = assemblePrompt({ instructions: pb.instructions, question: pb.question, evidence: evidence as never }, new Set());
    const withRejected = { ...BUNDLE, prompt_bundle: { ...pb, evidence, prompt } };
    const b = readBundle(withRejected)!;
    expect(b.rejectedDropped).toBe(1);
    expect(b.evidence.some((e) => e.status === "rejected")).toBe(false);
    expect(b.prompt).not.toContain(evidence[0]!.claim_id);
    expect(readBundle({ ...withRejected, prompt_bundle: { ...withRejected.prompt_bundle, prompt: `${prompt} ` } })).toBeNull();
  });
});

describe("citations", () => {
  it("accepts only ids that were sent and flags the rest", () => {
    const [a, b] = ids();
    const c = checkCitations(`One [${a}]. Two [${a}, ${b}]. Forged [${FORGED}]. Not a claim [see above].`, ids());
    expect(c.valid).toEqual([a, b]);
    expect(c.invalid).toEqual([FORGED]);
    expect(c.grounded).toBe(true);
  });

  it("marks answers without a valid citation as ungrounded", () => {
    expect(checkCitations("It probably saves tasks.", ids()).grounded).toBe(false);
    expect(checkCitations(`Only [${FORGED}]`, ids())).toMatchObject({ grounded: false, invalid: [FORGED] });
  });

  it("splits answers into text and checked citation pieces", () => {
    const [a] = ids();
    expect(pieces(`x [${a}] y [${FORGED}] [note]`, ids())).toEqual([
      { t: "text", v: "x " },
      { t: "cite", v: a, ok: true },
      { t: "text", v: " y " },
      { t: "cite", v: FORGED, ok: false },
      { t: "text", v: " [note]" },
    ]);
  });
});

describe("provider adapter", () => {
  it("puts the key only in the outgoing headers, never in the body or the shown headers", () => {
    for (const kind of ["openai", "anthropic", "ollama"] as const) {
      const r = buildRequest({ ...OPENAI, kind }, kind === "ollama" ? "" : KEY, "PROMPT");
      expect(JSON.stringify(r.body)).not.toContain(KEY);
      expect(JSON.stringify(r.shownHeaders)).not.toContain(KEY);
      expect(r.init.credentials).toBe("omit");
      expect(JSON.stringify(r.body)).toContain("PROMPT");
      if (kind !== "ollama") expect(JSON.stringify(r.init.headers)).toContain(KEY);
    }
    expect(buildRequest(OPENAI, KEY, "p").url).toBe("https://llm.example.test/v1/chat/completions");
    expect(buildRequest({ ...OPENAI, kind: "anthropic", baseUrl: "https://a.test/" }, KEY, "p").url).toBe("https://a.test/v1/messages");
    expect(buildRequest({ ...OPENAI, kind: "ollama", baseUrl: "http://localhost:11434" }, "", "p").url).toBe("http://localhost:11434/api/chat");
  });

  it("allows https anywhere and http only on this computer", () => {
    expect(checkBaseUrl("https://x.test/v1")).toBeNull();
    expect(checkBaseUrl("http://localhost:11434")).toBeNull();
    expect(checkBaseUrl("http://127.0.0.1:9")).toBeNull();
    expect(checkBaseUrl("http://evil.test")).not.toBeNull();
    expect(checkBaseUrl("nope")).not.toBeNull();
  });

  it("parses each provider shape and rejects anything else", () => {
    expect(parseAnswer("openai", { choices: [{ message: { content: "a" } }] })).toBe("a");
    expect(parseAnswer("anthropic", { content: [{ type: "text", text: "b" }] })).toBe("b");
    expect(parseAnswer("ollama", { message: { content: "c" } })).toBe("c");
    expect(() => parseAnswer("openai", { content: "x" })).toThrow(/expected format/);
  });

  it("reports CORS or unreachable providers as unsupported, never relayed", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(send(OPENAI, buildRequest(OPENAI, KEY, "p"), KEY)).rejects.toThrow(/CORS[\s\S]*does not relay/);
  });

  it("redacts a key that a provider echoes back", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { message: `bad key ${KEY}` } }), { status: 401 })));
    const err = await send(OPENAI, buildRequest(OPENAI, KEY, "p"), KEY).catch((e: Error) => e);
    expect(String(err)).not.toContain(KEY);
    expect(String(err)).toContain(REDACTED);
  });
});

describe("key storage", () => {
  it("uses session storage by default and local storage only when remembered", () => {
    saveKey(KEY, false);
    expect(sessionStorage.getItem(STORAGE_KEYS.KEY)).toBe(KEY);
    expect(localStorage.getItem(STORAGE_KEYS.KEY)).toBeNull();
    saveKey(KEY, true);
    expect(sessionStorage.getItem(STORAGE_KEYS.KEY)).toBeNull();
    expect(loadKey()).toEqual({ key: KEY, remembered: true });
    clearKey();
    expect(loadKey()).toBeNull();
  });

  it("shows a warning for Remember on this device and never shows a saved key", async () => {
    const u = userEvent.setup();
    const { container } = render(<ProviderSettings />);
    await u.type(screen.getByLabelText("Model"), "m-1");
    await u.type(screen.getByLabelText("API key"), KEY);
    await u.click(screen.getByLabelText("Remember on this device"));
    expect(screen.getByTestId("remember-warning").textContent).toMatch(/local storage[\s\S]*could read it/);
    await u.click(screen.getByRole("button", { name: "Save provider" }));
    expect(loadKey()).toEqual({ key: KEY, remembered: true });
    expect((screen.getByLabelText("API key") as HTMLInputElement).value).toBe("");
    expect(container.textContent).not.toContain(KEY);
    const r = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(r.violations.map((v) => v.id)).toEqual([]);
  });
});

describe("sent record", () => {
  it("keeps the newest entries up to the cap", () => {
    for (let i = 0; i < LOG_CAP + 3; i++) appendLog({ id: String(i) } as SentEntry);
    expect(readLog()).toHaveLength(LOG_CAP);
    expect(readLog()[0]!.id).toBe(String(LOG_CAP + 2));
  });
});

describe("ChatPanel", () => {
  const repo: Repo = { id: "r1", host: "github.com", owner: "o", name: "n", url: "https://github.com/o/n", visibility: "public", external_ai_consent: false, created_at: "2026-01-01T00:00:00Z" };

  function mount() {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <ChatPanel repoId="r1" sha={"0".repeat(40)} />
        </MemoryRouter>
      </QueryClientProvider>,
    );
  }

  it("asks for setup when there is no provider or key", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(repo))));
    mount();
    expect((await screen.findByTestId("chat-setup")).textContent).toContain("No AI provider is set up");
  });

  it("prepares, asks consent, sends only approved items to the provider and checks citations", async () => {
    saveConfig(OPENAI);
    saveKey(KEY, false);
    const b = readBundle(BUNDLE)!;
    const [first, second] = b.evidence;
    const calls: { url: string; init?: RequestInit }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        calls.push({ url, init });
        if (url.startsWith("/api/v1/repos/r1/snapshots/")) return new Response(JSON.stringify(BUNDLE));
        if (url.startsWith("/api/v1/repos/r1")) return new Response(JSON.stringify(repo));
        if (url === "https://llm.example.test/v1/chat/completions")
          return new Response(JSON.stringify({ choices: [{ message: { content: `Grounded [${second!.claim_id}] and forged [${FORGED}].` } }] }));
        return new Response("{}", { status: 404 });
      }),
    );
    const u = userEvent.setup();
    const { container } = mount();
    await u.type(await screen.findByLabelText("Message"), "trace from Form to save_task");
    await u.click(screen.getByRole("button", { name: "Review what will be sent" }));
    const dialog = await screen.findByTestId("consent-dialog");
    expect(within(dialog).getAllByTestId("consent-item")).toHaveLength(b.evidence.length);
    expect(within(dialog).getByTestId("consent-scope").textContent).toContain("no recorded consent");
    expect(calls.some((c) => c.url.includes("llm.example.test"))).toBe(false);
    await u.click(within(dialog).getAllByRole("checkbox")[0]!);
    expect(within(dialog).getByTestId("consent-body").textContent).not.toContain(first!.claim_id);
    expect(dialog.textContent).not.toContain(KEY);
    await u.click(within(dialog).getByRole("button", { name: /^Send to llm\.example\.test/ }));
    await waitFor(() => expect(screen.getByTestId("grounding").getAttribute("data-grounded")).toBe("true"));
    expect(screen.getByTestId("invalid-citations").textContent).toContain("1 citation points");
    expect(screen.getAllByTestId("cite-bad")).toHaveLength(1);
    const llm = calls.find((c) => c.url.includes("llm.example.test"))!;
    expect(String(llm.init?.body)).not.toContain(first!.claim_id);
    expect((llm.init?.headers as Record<string, string>).Authorization).toBe(`Bearer ${KEY}`);
    for (const c of calls.filter((x) => x.url.startsWith("/api/"))) expect(JSON.stringify(c)).not.toContain(KEY);
    const log = readLog();
    expect(log).toHaveLength(1);
    expect(JSON.stringify(log)).not.toContain(KEY);
    expect(log[0]!.removed).toEqual([first!.claim_id]);
    expect(container.textContent).not.toContain(KEY);
    const r = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
    expect(r.violations.map((v) => v.id)).toEqual([]);
  });

  it("blocks repositories that are not public", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...repo, visibility: "private" }))));
    mount();
    expect((await screen.findByTestId("chat-blocked")).textContent).toContain("not public");
  });
});
