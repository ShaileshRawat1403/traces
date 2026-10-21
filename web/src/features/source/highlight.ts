// Syntax highlighting with Shiki, loaded lazily (only when a source panel opens).
// Tokens are rendered as React text nodes; source text is never inserted as HTML.
import type { HighlighterCore, ThemedToken } from "shiki/core";

const LANG_BY_EXT: Record<string, string> = {
  ts: "typescript",
  mts: "typescript",
  cts: "typescript",
  tsx: "tsx",
  js: "javascript",
  mjs: "javascript",
  cjs: "javascript",
  jsx: "jsx",
  py: "python",
  pyi: "python",
  json: "json",
  yml: "yaml",
  yaml: "yaml",
  toml: "toml",
  md: "markdown",
  css: "css",
  html: "html",
  sh: "shellscript",
  bash: "shellscript",
  go: "go",
  rs: "rust",
  java: "java",
  sql: "sql",
};

export function langFor(path: string): string | null {
  const name = path.split("/").pop() ?? "";
  if (/^dockerfile$/i.test(name)) return "dockerfile";
  const ext = name.includes(".") ? name.split(".").pop()!.toLowerCase() : "";
  return LANG_BY_EXT[ext] ?? null;
}

export const THEME = "github-light-high-contrast";
let highlighter: Promise<HighlighterCore> | null = null;

function load(): Promise<HighlighterCore> {
  highlighter ??= (async () => {
    const [{ createHighlighterCore }, { createJavaScriptRegexEngine }] = await Promise.all([import("shiki/core"), import("shiki/engine/javascript")]);
    return createHighlighterCore({
      themes: [import("@shikijs/themes/github-light-high-contrast")],
      langs: [
        import("@shikijs/langs/typescript"),
        import("@shikijs/langs/tsx"),
        import("@shikijs/langs/javascript"),
        import("@shikijs/langs/jsx"),
        import("@shikijs/langs/python"),
        import("@shikijs/langs/json"),
        import("@shikijs/langs/yaml"),
        import("@shikijs/langs/toml"),
        import("@shikijs/langs/markdown"),
        import("@shikijs/langs/css"),
        import("@shikijs/langs/html"),
        import("@shikijs/langs/shellscript"),
        import("@shikijs/langs/dockerfile"),
        import("@shikijs/langs/go"),
        import("@shikijs/langs/rust"),
        import("@shikijs/langs/java"),
        import("@shikijs/langs/sql"),
      ],
      engine: createJavaScriptRegexEngine(),
    });
  })();
  return highlighter;
}

/** Tokens per line, or null when the language is not supported (plain text is shown instead). */
export async function tokenize(lines: readonly string[], path: string): Promise<ThemedToken[][] | null> {
  const lang = langFor(path);
  if (!lang) return null;
  const h = await load();
  return h.codeToTokensBase(lines.join("\n"), { lang, theme: THEME });
}
