/**
 * Comparison state colors — must match python-engine comparison/palette.py.
 * Guarded by test_comparison_palette_matches_frontend in Python tests.
 */

export type ComparisonState =
  | "unchanged"
  | "grown"
  | "decreased"
  | "added"
  | "removed"
  | "ambiguous";

export const COMPARISON_STATE_COLORS: Readonly<Record<ComparisonState, string>> = {
  unchanged: "#9ca3af",
  grown: "#ef4444",
  decreased: "#3b82f6",
  added: "#22c55e",
  removed: "#4b5563",
  ambiguous: "#f97316",
} as const;

export const COMPARISON_STATE_LABELS: Readonly<Record<ComparisonState, string>> = {
  unchanged: "Invariato",
  grown: "Cresciuto",
  decreased: "Diminuito",
  added: "Nuovo",
  removed: "Rimosso",
  ambiguous: "Ambiguo",
} as const;
