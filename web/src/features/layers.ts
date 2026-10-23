import type { Schemas } from "../api/client";

/** A component layer exactly as the API names it. Adding a value to the contract makes tsc flag every table below. */
export type Layer = Schemas["Component"]["layer"];

/** Display order: code layers first, then support layers. */
export const LAYERS = ["frontend", "api", "backend", "library", "data", "infra", "docs", "tests", "other"] as const satisfies readonly Layer[];

// Compile-time exhaustiveness: fails if the contract gains a layer that LAYERS does not list.
type MissingLayer = Exclude<Layer, (typeof LAYERS)[number]>;
const _allLayersListed: [MissingLayer] extends [never] ? true : MissingLayer = true;
void _allLayersListed;

/** Swatch colour per layer. A Record over Layer, so a missing layer is a type error. */
export const LAYER_COLOR: Record<Layer, string> = {
  frontend: "#8fd9cf",
  api: "#7eb6ff",
  backend: "#d7fff8",
  library: "#a8e6a1",
  data: "#e2b16a",
  infra: "#b7c4ce",
  docs: "#c4b4ea",
  tests: "#ef8d86",
  other: "#8ea399",
};

/** Layers that hold application or library code (as opposed to infra, docs and tests). */
export const CODE_LAYERS: Record<Layer, boolean> = {
  frontend: true,
  api: true,
  backend: true,
  library: true,
  data: true,
  infra: false,
  docs: false,
  tests: false,
  other: false,
};

export function isLayer(x: unknown): x is Layer {
  return typeof x === "string" && (LAYERS as readonly string[]).includes(x);
}

/** Colour for any string (graph data is loosely typed); unknown values get the "other" swatch. */
export function layerColor(x: string | null | undefined): string {
  return isLayer(x) ? LAYER_COLOR[x] : LAYER_COLOR.other;
}

export function assertNever(x: never): never {
  throw new Error(`unexpected value ${String(x)}`);
}
