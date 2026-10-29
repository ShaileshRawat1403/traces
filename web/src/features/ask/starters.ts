/** Questions the no-key explainer can route. A route question is only offered for a stored method and path. */
export function starterQuestions(sha: string, routes: readonly { method: string; path: string }[]): string[] {
  const route = routes.find((r) => r.method !== "UNKNOWN" && r.method !== "USE" && r.path.startsWith("/"));
  const hash = sha.slice(0, 12);
  const base = [
    "Which routes are declared?",
    "How is data persisted?",
    "Which files changed together?",
    ...(hash.length >= 7 ? [`What changed in commit ${hash}?`] : []),
  ];
  return route ? [`What does ${route.method} ${route.path} do?`, ...base] : base;
}
