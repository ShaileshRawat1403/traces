// Post-check of a model answer: every bracketed claim id must be one that was actually sent. Answers with no valid
// citation are ungrounded. The model text is never trusted to be correct; this only checks what it points at.

export interface CitationCheck {
  valid: string[];
  invalid: string[];
  grounded: boolean;
}

const BRACKET = /\[([^[\]\n]{1,600})\]/g;
const CLAIM = /^c_[0-9a-f]{6,64}$/i;

export function checkCitations(answer: string, sentIds: readonly string[]): CitationCheck {
  const sent = new Set(sentIds);
  const valid: string[] = [];
  const invalid: string[] = [];
  for (const m of answer.matchAll(BRACKET)) {
    for (const raw of (m[1] ?? "").split(/[,;\s]+/)) {
      const id = raw.trim();
      if (!id) continue;
      const looksLikeClaim = CLAIM.test(id) || sent.has(id);
      if (!looksLikeClaim) continue;
      const bucket = sent.has(id) ? valid : invalid;
      if (!bucket.includes(id)) bucket.push(id);
    }
  }
  return { valid, invalid, grounded: valid.length > 0 };
}

/** Split the answer into text and citation tokens so citations can be rendered as checked chips. Text stays plain text. */
export type Piece = { t: "text"; v: string } | { t: "cite"; v: string; ok: boolean };

export function pieces(answer: string, sentIds: readonly string[]): Piece[] {
  const sent = new Set(sentIds);
  const out: Piece[] = [];
  let last = 0;
  for (const m of answer.matchAll(BRACKET)) {
    const ids = (m[1] ?? "").split(/[,;\s]+/).map((s) => s.trim()).filter(Boolean);
    if (!ids.length || !ids.every((id) => CLAIM.test(id) || sent.has(id))) continue;
    if (m.index > last) out.push({ t: "text", v: answer.slice(last, m.index) });
    for (const id of ids) out.push({ t: "cite", v: id, ok: sent.has(id) });
    last = m.index + m[0].length;
  }
  if (last < answer.length) out.push({ t: "text", v: answer.slice(last) });
  return out;
}

/** Short, still-distinguishable form of a claim id: head and tail. */
export const shortId = (id: string) => (id.length > 18 ? `${id.slice(0, 8)}…${id.slice(-6)}` : id);
