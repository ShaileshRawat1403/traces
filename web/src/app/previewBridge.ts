// Guest side of the Grok preview chrome. Noops outside that frame.
// The chrome hides the pane until the guest posts ready.

const CHANNEL = "grok-preview-bridge";
const VERSION = 1;
const ROOT_KEY = "__grokPreviewBridgeRoot";

const PATH_HOSTS = new Set(["preview.grok.genai.mil", "preview.grok.mil", "preview.grokgsac.com"]);
const PORT_PREFIX = /^\/hds-[a-z0-9]+-\d+-[a-z0-9]+/i;

/** Path prefix a path-based preview keeps in the browser URL. Empty everywhere else. */
export function previewBasename(): string {
  if (typeof window === "undefined") return "";
  if (!PATH_HOSTS.has(window.location.hostname.toLowerCase())) return "";
  return PORT_PREFIX.exec(window.location.pathname)?.[0] ?? "";
}

function grokOrigin(origin: string): boolean {
  try {
    const url = new URL(origin);
    if (url.protocol !== "https:" && url.protocol !== "http:") return false;
    const host = url.hostname.toLowerCase();
    return host === "grok.com" || host.endsWith(".grok.com") || host === "localhost" || host === "127.0.0.1" || host === "[::1]";
  } catch {
    return false;
  }
}

function parentOrigin(): string | null {
  if (typeof window === "undefined" || window.parent === window) return null;
  const ancestor = typeof location.ancestorOrigins !== "undefined" && location.ancestorOrigins.length > 0 ? location.ancestorOrigins[0] : "";
  const candidates = [document.referrer, ancestor].filter((x): x is string => typeof x === "string" && x.length > 0);
  for (const candidate of candidates) {
    try {
      const url = new URL(candidate.includes("://") ? candidate : `https://${candidate}`);
      if (url.protocol !== "https:" && url.protocol !== "http:") continue;
      const guest = window.location.hostname.toLowerCase();
      const sandbox = guest === "grok-sandbox.com" || guest.endsWith(".grok-sandbox.com");
      if (grokOrigin(url.origin) || sandbox) return url.origin;
    } catch {
      /* next candidate */
    }
  }
  return null;
}

function safePath(path: string): boolean {
  if (!path.startsWith("/") || path.startsWith("//") || path.includes("\\")) return false;
  try {
    return new URL(path, "https://preview.invalid").origin === "https://preview.invalid";
  } catch {
    return false;
  }
}

function stripBase(path: string): string {
  const base = previewBasename();
  if (base && (path === base || path.startsWith(`${base}/`))) {
    const rest = path.slice(base.length) || "/";
    return rest.startsWith("/") ? rest : `/${rest}`;
  }
  return path;
}

export function installPreviewBridge(navigate: (path: string) => void): () => void {
  const origin = parentOrigin();
  if (!origin) return () => {};

  const post = (message: object) => window.parent.postMessage(message, origin);
  const reportLocation = () =>
    post({
      channel: CHANNEL,
      version: VERSION,
      type: "location",
      path: window.location.pathname || "/",
      search: window.location.search,
      hash: window.location.hash,
    });
  const announce = () => {
    reportLocation();
    post({
      channel: CHANNEL,
      version: VERSION,
      type: "routes",
      paths: ["/", "/settings"],
    });
    post({ channel: CHANNEL, version: VERSION, type: "ready" });
  };

  const originalPush = window.history.pushState.bind(window.history);
  const originalReplace = window.history.replaceState.bind(window.history);
  const isRoot = () => {
    const state = window.history.state;
    return Boolean(state && typeof state === "object" && (state as Record<string, unknown>)[ROOT_KEY] === true);
  };
  try {
    const current = window.history.state;
    const tagged = current !== null && typeof current === "object" && Object.prototype.hasOwnProperty.call(current, ROOT_KEY);
    if (!tagged) {
      const marked = current && typeof current === "object" ? { ...current, [ROOT_KEY]: window.history.length <= 1 } : { [ROOT_KEY]: window.history.length <= 1 };
      originalReplace(marked, "", window.location.href);
    }
  } catch {
    /* document cannot be marked */
  }

  const onMessage = (event: MessageEvent) => {
    if (event.source !== window.parent || event.origin !== origin) return;
    const data = event.data as { channel?: string; version?: number; type?: string; path?: string; delta?: number } | null;
    if (!data || data.channel !== CHANNEL || data.version !== VERSION || typeof data.type !== "string") return;
    if (data.type === "hello") announce();
    else if (data.type === "navigate" && typeof data.path === "string" && safePath(data.path)) {
      navigate(stripBase(data.path));
      queueMicrotask(reportLocation);
    } else if (data.type === "history" && (data.delta === -1 || data.delta === 1)) {
      if (data.delta === -1 && isRoot()) return;
      window.history.go(data.delta);
    }
  };

  window.history.pushState = (data, unused, url) => {
    const next = data && typeof data === "object" ? { ...data, [ROOT_KEY]: false } : data;
    originalPush(next, unused, url);
    reportLocation();
  };
  window.history.replaceState = (data, unused, url) => {
    const next = isRoot() ? { ...(data && typeof data === "object" ? data : {}), [ROOT_KEY]: true } : data;
    originalReplace(next, unused, url);
    reportLocation();
  };

  window.addEventListener("message", onMessage);
  window.addEventListener("popstate", reportLocation);
  announce();
  return () => {
    window.removeEventListener("message", onMessage);
    window.removeEventListener("popstate", reportLocation);
    window.history.pushState = originalPush;
    window.history.replaceState = originalReplace;
  };
}
