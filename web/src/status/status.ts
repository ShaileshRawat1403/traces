// Presentation of claim status and label. The UI shows the API's own `label`; it never derives or promotes a status.
// Mapping source: docs/CONTRACTS.md section 2 (user-facing labels) and section 1.3 (status rules).

export type Status = "verified" | "observed" | "unvalidated" | "missing_location" | "rejected";
export type Label = "verified" | "observed" | "inferred" | "rejected";
/** Where a claim is shown. Rejected claims are only presented in reviewer contexts (review view, evidence drawer). */
export type Context = "default" | "reviewer";
export type LineStyle = "solid" | "thin" | "dashed" | "dotted" | "none";
export type Tone = "verified" | "observed" | "inferred" | "rejected" | "unknown";

export interface StatusInput {
  status: string | null | undefined;
  label: string | null | undefined;
  flags?: readonly string[] | null;
}

export interface StatusPresentation {
  /** Text shown to users, taken from the API label. */
  text: string;
  tone: Tone;
  line: LineStyle;
  /** Extra plain-language note shown next to the label (for example "No source location"). */
  note: string | null;
  /** True when this claim must not be shown in the current context (rejected outside reviewer views). */
  hidden: boolean;
  /** True when status and label do not form an allowed pair; the UI shows a warning instead of choosing one. */
  inconsistent: boolean;
  /** Accessible description, used for aria-label and tooltips. */
  description: string;
}

const LABEL_TEXT: Record<Label, string> = {
  verified: "Verified",
  observed: "Observed",
  inferred: "Inferred",
  rejected: "Rejected",
};

// Allowed status -> label pairs (CONTRACTS.md section 2).
export const EXPECTED_LABEL: Record<Status, Label> = {
  verified: "verified",
  observed: "observed",
  unvalidated: "inferred",
  missing_location: "inferred",
  rejected: "rejected",
};

const LINE: Record<Status, LineStyle> = {
  verified: "solid",
  observed: "thin",
  unvalidated: "dashed",
  missing_location: "dotted",
  rejected: "none",
};

const DESCRIPTION: Record<Status, string> = {
  verified: "Verified: the relationship is established by an independent check (syntax, binding resolution or a documented rule).",
  observed: "Observed: present in the source text at this location. Not a runtime observation.",
  unvalidated: "Inferred: an analyzer's claim that is not established. See the status reason.",
  missing_location: "Inferred, with no source location: the claim could not be tied to source lines. Never verified.",
  rejected: "Rejected: an independent check failed. Kept for review; never shown as architecture.",
};

export function isStatus(s: unknown): s is Status {
  return typeof s === "string" && s in EXPECTED_LABEL;
}

export function isLabel(l: unknown): l is Label {
  return typeof l === "string" && l in LABEL_TEXT;
}

export function presentStatus(input: StatusInput, context: Context = "default"): StatusPresentation {
  const { status, label } = input;
  const flags = input.flags ?? [];
  const labelText = isLabel(label) ? LABEL_TEXT[label] : label ? String(label) : "Unlabeled";

  if (!isStatus(status) || !isLabel(label)) {
    return {
      text: labelText,
      tone: "unknown",
      line: "dashed",
      note: "Unrecognized status or label",
      hidden: false,
      inconsistent: true,
      description: `Unrecognized record: status ${String(status)}, label ${String(label)}. Shown as recorded, not interpreted.`,
    };
  }

  const inconsistent = EXPECTED_LABEL[status] !== label;
  // Rejected is reviewer-only, whichever field says so.
  const rejected = status === "rejected" || label === "rejected";
  const hidden = rejected && context !== "reviewer";
  const noLocation = status === "missing_location" || flags.includes("no_source_location");

  // Inconsistent pairs (for example missing_location labelled verified) get a neutral tone, never the verified one.
  const tone: Tone = inconsistent ? "unknown" : label;
  const notes: string[] = [];
  if (noLocation) notes.push("No source location");
  if (inconsistent) notes.push(`Status ${status} does not match label ${label}`);

  return {
    text: labelText,
    tone,
    line: LINE[status],
    note: notes.length ? notes.join("; ") : null,
    hidden,
    inconsistent,
    description: DESCRIPTION[status] + (inconsistent ? ` Warning: the record's label is ${label}, which does not match status ${status}.` : ""),
  };
}

/** Display name for a status key in hidden-count summaries. */
export function statusName(status: string): string {
  switch (status) {
    case "verified":
      return "verified";
    case "observed":
      return "observed";
    case "unvalidated":
      return "inferred (unvalidated)";
    case "missing_location":
      return "inferred (no source location)";
    case "rejected":
      return "rejected";
    default:
      return status;
  }
}

export const STATIC_DISCLAIMER = "Static analysis only. No runtime behavior has been observed.";
