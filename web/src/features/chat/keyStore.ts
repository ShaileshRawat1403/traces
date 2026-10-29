// Provider settings and the key live only in this browser. The key goes to sessionStorage by default; "Remember on this
// device" moves it to localStorage. Nothing here is ever logged or sent to the Traces API.
import { PROVIDERS, type ProviderConfig, type ProviderKind } from "./providers";

const CONFIG = "traces.chat.provider";
const KEY = "traces.chat.key";

function store(kind: "session" | "local"): Storage | null {
  try {
    return kind === "session" ? window.sessionStorage : window.localStorage;
  } catch {
    return null; // storage disabled
  }
}

export function loadConfig(): ProviderConfig | null {
  try {
    const raw = store("local")?.getItem(CONFIG);
    if (!raw) return null;
    const c = JSON.parse(raw) as Partial<ProviderConfig>;
    if (!c.kind || !(c.kind in PROVIDERS) || typeof c.baseUrl !== "string" || typeof c.model !== "string") return null;
    return { kind: c.kind as ProviderKind, baseUrl: c.baseUrl, model: c.model };
  } catch {
    return null;
  }
}

/** Provider, base URL and model are not secret and are kept on this device so the form is prefilled. */
export function saveConfig(c: ProviderConfig): void {
  store("local")?.setItem(CONFIG, JSON.stringify(c));
}

export interface StoredKey {
  key: string;
  remembered: boolean;
}

export function loadKey(): StoredKey | null {
  const s = store("session")?.getItem(KEY);
  if (s) return { key: s, remembered: false };
  const l = store("local")?.getItem(KEY);
  return l ? { key: l, remembered: true } : null;
}

/** Store the key in exactly one place, clearing the other. */
export function saveKey(key: string, remember: boolean): void {
  clearKey();
  if (key) store(remember ? "local" : "session")?.setItem(KEY, key);
}

export function clearKey(): void {
  store("session")?.removeItem(KEY);
  store("local")?.removeItem(KEY);
}

export function forgetAll(): void {
  clearKey();
  store("local")?.removeItem(CONFIG);
}

export const STORAGE_KEYS = { CONFIG, KEY } as const;
