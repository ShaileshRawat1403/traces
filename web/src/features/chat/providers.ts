// Provider-neutral adapter for browser-side chat (IA.md 8.2). The browser calls the provider directly; Traces never relays,
// and the key is only ever placed in the outbound request headers built here.

export type ProviderKind = "openai" | "anthropic" | "ollama";

export interface ProviderConfig {
  kind: ProviderKind;
  baseUrl: string;
  model: string;
}

export const PROVIDERS: Record<ProviderKind, { name: string; defaultBase: string; needsKey: boolean; help: string }> = {
  openai: {
    name: "OpenAI-compatible",
    defaultBase: "https://api.openai.com/v1",
    needsKey: true,
    help: "Any service with an OpenAI-style /chat/completions endpoint that allows browser requests (CORS).",
  },
  anthropic: {
    name: "Anthropic-compatible",
    defaultBase: "https://api.anthropic.com",
    needsKey: true,
    help: "Messages API at /v1/messages. Direct browser access must be allowed by the provider.",
  },
  ollama: {
    name: "Local Ollama",
    defaultBase: "http://localhost:11434",
    needsKey: false,
    help: "A model running on this computer. Ollama must allow this page's origin (OLLAMA_ORIGINS).",
  },
};

export const MAX_TOKENS = 1024;

export interface OutboundRequest {
  url: string;
  /** Header names and values with the key replaced, for the record and the consent screen. */
  shownHeaders: Record<string, string>;
  /** Exact JSON body that is sent. Contains no key. */
  body: Record<string, unknown>;
  init: RequestInit;
}

const trimSlash = (u: string) => u.replace(/\/+$/, "");
export const REDACTED = "(your key, not shown)";

/** Validate a base URL: https anywhere, or http only for this computer. */
export function checkBaseUrl(raw: string): string | null {
  let u: URL;
  try {
    u = new URL(raw);
  } catch {
    return "Enter a full URL, for example https://api.example.com/v1.";
  }
  const local = ["localhost", "127.0.0.1", "[::1]"].includes(u.hostname);
  if (u.protocol === "https:" || (u.protocol === "http:" && local)) return null;
  return "Use https, or http only for localhost.";
}

export function hostOf(url: string): string {
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
}

export function buildRequest(cfg: ProviderConfig, key: string, prompt: string): OutboundRequest {
  const base = trimSlash(cfg.baseUrl);
  const messages = [{ role: "user", content: prompt }];
  let url: string;
  let body: Record<string, unknown>;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const shown: Record<string, string> = { "Content-Type": "application/json" };
  if (cfg.kind === "openai") {
    url = `${base}/chat/completions`;
    body = { model: cfg.model, messages, max_tokens: MAX_TOKENS };
    if (key) {
      headers.Authorization = `Bearer ${key}`;
      shown.Authorization = `Bearer ${REDACTED}`;
    }
  } else if (cfg.kind === "anthropic") {
    url = `${base}/v1/messages`;
    body = { model: cfg.model, messages, max_tokens: MAX_TOKENS };
    headers["x-api-key"] = key;
    headers["anthropic-version"] = "2023-06-01";
    headers["anthropic-dangerous-direct-browser-access"] = "true";
    shown["x-api-key"] = REDACTED;
    shown["anthropic-version"] = "2023-06-01";
    shown["anthropic-dangerous-direct-browser-access"] = "true";
  } else {
    url = `${base}/api/chat`;
    body = { model: cfg.model, messages, stream: false, options: { temperature: 0 } };
  }
  // credentials: "omit" so no cookies for this site or the provider travel with the request; no-referrer keeps the
  // snapshot URL out of the provider's logs.
  return { url, shownHeaders: shown, body, init: { method: "POST", headers, body: JSON.stringify(body), credentials: "omit", referrerPolicy: "no-referrer", mode: "cors" } };
}

export class ProviderError extends Error {
  constructor(
    public kind: "unreachable" | "http" | "shape",
    message: string,
    public status?: number,
  ) {
    super(message);
    this.name = "ProviderError";
  }
}

/** Plain text of the first answer in a provider response. Anything else is a shape error, never guessed at. */
export function parseAnswer(kind: ProviderKind, json: unknown): string {
  const j = json as Record<string, unknown> | null;
  let text: unknown;
  if (kind === "openai") text = (j?.choices as { message?: { content?: unknown } }[] | undefined)?.[0]?.message?.content;
  else if (kind === "anthropic")
    text = Array.isArray(j?.content)
      ? (j.content as { type?: string; text?: unknown }[])
          .filter((c) => c.type === "text" && typeof c.text === "string")
          .map((c) => c.text)
          .join("\n")
      : undefined;
  else text = (j?.message as { content?: unknown } | undefined)?.content;
  if (typeof text !== "string" || !text.trim()) throw new ProviderError("shape", "The provider answered, but not in the expected format, so nothing is shown.");
  return text;
}

/** Remove the key from any text before it is shown or recorded (some services echo it back in errors). */
export function redact(text: string, key: string): string {
  return key && key.length >= 4 ? text.split(key).join(REDACTED) : text;
}

export async function send(cfg: ProviderConfig, req: OutboundRequest, key: string, signal?: AbortSignal): Promise<string> {
  try {
    return redact(await sendRaw(cfg, req, signal), key);
  } catch (e) {
    if (e instanceof ProviderError) throw new ProviderError(e.kind, redact(e.message, key), e.status);
    throw e;
  }
}

async function sendRaw(cfg: ProviderConfig, req: OutboundRequest, signal?: AbortSignal): Promise<string> {
  let res: Response;
  try {
    res = await fetch(req.url, { ...req.init, signal });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ProviderError(
      "unreachable",
      `The browser could not reach ${hostOf(req.url)}. Either it is not running or reachable, or it does not allow requests from a web page (CORS). Traces does not relay requests through its server, so this provider is unsupported from the browser unless it allows this origin.`,
    );
  }
  if (!res.ok) {
    let detail = "";
    try {
      const j = (await res.json()) as { error?: { message?: unknown } | string };
      const m = typeof j.error === "string" ? j.error : j.error?.message;
      if (typeof m === "string") detail = `: ${m.slice(0, 300)}`;
    } catch {
      /* non-JSON error body */
    }
    throw new ProviderError("http", `${hostOf(req.url)} answered HTTP ${res.status}${detail}`, res.status);
  }
  let json: unknown;
  try {
    json = await res.json();
  } catch {
    throw new ProviderError("shape", "The provider answered with something that is not JSON, so nothing is shown.");
  }
  return parseAnswer(cfg.kind, json);
}
