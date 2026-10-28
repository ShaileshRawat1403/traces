/**
 * A question the no-key explainer can route, or null.
 * A symbol is asked as a dependency. A file is asked as co-change. A directory is not guessed.
 */
export function recordedQuestion(name: string): string | null {
  const n = name.trim();
  if (!n || n.length > 240 || /\s/.test(n)) return null;
  if (n.startsWith("component::") || n.startsWith("file::") || n.startsWith("commit::")) return null;
  if (n.includes("::") || /^[A-Za-z_][\w$]*$/.test(n)) return `What does ${n} depend on?`;
  if (/(?:^|\/)[^/]+\.[A-Za-z][\w]{0,9}$/.test(n)) return `Which files changed together with ${n}?`;
  return null;
}

export function askHref(base: string, names: readonly string[]): string | null {
  for (const name of names) {
    const q = recordedQuestion(name);
    if (q) return `${base}/ask?q=${encodeURIComponent(q)}`;
  }
  return null;
}
