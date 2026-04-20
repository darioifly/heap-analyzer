/**
 * 12-color palette for material categories.
 * MUST stay byte-identical to python-engine/src/heap_analyzer/report/palette.py CATEGORY_PALETTE.
 * If you change one, change the other in the same commit.
 */
export const CATEGORY_PALETTE: readonly string[] = [
  "#ef4444",
  "#f97316",
  "#f59e0b",
  "#eab308",
  "#84cc16",
  "#22c55e",
  "#14b8a6",
  "#06b6d4",
  "#3b82f6",
  "#8b5cf6",
  "#a855f7",
  "#ec4899",
] as const;

export const UNCLASSIFIED_COLOR = "#6b7280";

/**
 * Get the color for a material category based on its position in the project's category list.
 */
export function categoryColor(
  category: string | null,
  projectCategories: string[],
): string {
  if (category === null) return UNCLASSIFIED_COLOR;
  const idx = projectCategories.indexOf(category);
  if (idx === -1) return UNCLASSIFIED_COLOR;
  return CATEGORY_PALETTE[idx % CATEGORY_PALETTE.length];
}
