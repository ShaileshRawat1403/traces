// Local record of everything sent to a provider, kept on this device only and viewable in the app. No keys, ever:
// entries are built from OutboundRequest.shownHeaders, which carry a placeholder instead of the key.
import type { OutboundItem } from "../../api/client";

export interface SentEntry {
  id: string;
  at: string;
  repoId: string;
  sha: string;
  provider: string;
  host: string;
  url: string;
  model: string;
  headers: Record<string, string>;
  body: Record<string, unknown>;
  manifest: OutboundItem[];
  removed: string[];
  outcome: { ok: boolean; detail: string; grounded?: boolean; valid?: number; invalid?: number };
}

const LOG = "traces.chat.sent";
export const LOG_CAP = 50;

function ls(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function readLog(): SentEntry[] {
  try {
    const v = JSON.parse(ls()?.getItem(LOG) ?? "[]") as unknown;
    return Array.isArray(v) ? (v as SentEntry[]) : [];
  } catch {
    return [];
  }
}

export function appendLog(e: SentEntry): void {
  const next = [e, ...readLog()].slice(0, LOG_CAP);
  ls()?.setItem(LOG, JSON.stringify(next));
  window.dispatchEvent(new Event("traces-sent-log"));
}

export function clearLog(): void {
  ls()?.removeItem(LOG);
  window.dispatchEvent(new Event("traces-sent-log"));
}
