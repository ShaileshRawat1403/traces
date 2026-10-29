import { useId, useState, type FormEvent } from "react";
import { Button } from "../../ui/States";
import { clearKey, forgetAll, loadConfig, loadKey, saveConfig, saveKey } from "./keyStore";
import { PROVIDERS, checkBaseUrl, hostOf, type ProviderKind } from "./providers";

/** Provider form for browser-side chat. The key input is write-only: a saved key is never shown again. */
export function ProviderSettings() {
  const saved = loadConfig();
  const [kind, setKind] = useState<ProviderKind>(saved?.kind ?? "openai");
  const [baseUrl, setBaseUrl] = useState(saved?.baseUrl ?? PROVIDERS[saved?.kind ?? "openai"].defaultBase);
  const [model, setModel] = useState(saved?.model ?? "");
  const [key, setKey] = useState("");
  const [stored, setStored] = useState(loadKey);
  const [remember, setRemember] = useState(stored?.remembered ?? false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const id = useId();
  const p = PROVIDERS[kind];

  const pick = (k: ProviderKind) => {
    if (baseUrl === p.defaultBase || !baseUrl) setBaseUrl(PROVIDERS[k].defaultBase);
    setKind(k);
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setMsg(null);
    const bad = checkBaseUrl(baseUrl.trim());
    if (bad) return setErr(bad);
    if (!model.trim()) return setErr("Enter a model name.");
    setErr(null);
    saveConfig({ kind, baseUrl: baseUrl.trim(), model: model.trim() });
    if (key) saveKey(key, remember);
    else if (stored && stored.remembered !== remember) saveKey(stored.key, remember);
    setKey("");
    const now = loadKey();
    setStored(now);
    setMsg(`Saved. ${now ? (now.remembered ? "The key is remembered on this device." : "The key is kept for this browser session only.") : p.needsKey ? "No key is stored yet." : "No key is needed."}`);
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-3" aria-label="AI provider" data-testid="provider-settings">
      <fieldset className="flex flex-col gap-1">
        <legend className="mb-1 text-sm font-medium">Provider</legend>
        {(Object.keys(PROVIDERS) as ProviderKind[]).map((k) => (
          <label key={k} className="tap flex items-start gap-2 text-sm">
            <input type="radio" name={`${id}-kind`} value={k} checked={kind === k} onChange={() => pick(k)} className="mt-1" />
            <span>
              {PROVIDERS[k].name}
              <span className="block text-xs text-muted">{PROVIDERS[k].help}</span>
            </span>
          </label>
        ))}
      </fieldset>
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">Base URL</span>
        <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} className="rounded-md border border-line-strong p-2 font-mono text-xs" inputMode="url" autoComplete="off" spellCheck={false} />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">Model</span>
        <input value={model} onChange={(e) => setModel(e.target.value)} className="rounded-md border border-line-strong p-2 font-mono text-xs" autoComplete="off" spellCheck={false} />
      </label>
      {p.needsKey ? (
        <div className="flex flex-col gap-1 text-sm">
          <label htmlFor={`${id}-key`} className="font-medium">
            API key
          </label>
          <input
            id={`${id}-key`}
            type="password"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            className="rounded-md border border-line-strong p-2 font-mono text-xs"
            autoComplete="off"
            spellCheck={false}
            placeholder={stored ? "A key is stored. Type a new one to replace it." : ""}
            aria-describedby={`${id}-keyhelp`}
          />
          <span id={`${id}-keyhelp`} className="text-xs text-muted">
            Sent only to {hostOf(baseUrl)}, from this browser. Never sent to Traces, never logged, never shown again.
          </span>
        </div>
      ) : null}
      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="mt-1" aria-describedby={`${id}-warn`} />
        <span>Remember on this device</span>
      </label>
      <p id={`${id}-warn`} className={`text-xs ${remember ? "rounded-md border border-inferred/60 bg-surface p-2 text-ink" : "text-muted"}`} data-testid="remember-warning">
        {remember
          ? "Warning: the key will be saved in this browser's local storage and stay after you close it. Anyone who uses this browser profile, and any script that runs on this site, could read it. Use a key with a spending limit, and forget it when you are done."
          : "By default the key is kept in session storage and is gone when you close this tab."}
      </p>
      {err ? (
        <p role="alert" className="text-sm text-rejected">
          {err}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="primary">
          Save provider
        </Button>
        <Button
          type="button"
          onClick={() => {
            clearKey();
            setStored(null);
            setMsg("Key forgotten on this device and in this session.");
          }}
          disabled={!stored}
        >
          Forget key
        </Button>
        <Button
          type="button"
          onClick={() => {
            forgetAll();
            setStored(null);
            setModel("");
            setMsg("Provider settings and key removed from this browser.");
          }}
        >
          Remove all chat settings
        </Button>
      </div>
      <p className="text-sm text-ink-2" role="status" data-testid="provider-status">
        {msg ?? (stored ? (stored.remembered ? "A key is remembered on this device." : "A key is stored for this session.") : p.needsKey ? "No key stored." : "")}
      </p>
    </form>
  );
}
