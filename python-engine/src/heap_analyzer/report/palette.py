"""Shared color palette for report rendering.

MUST stay byte-identical to frontend/src/utils/categoryColors.ts CATEGORY_PALETTE.
If you change one, change the other in the same commit.
"""

from __future__ import annotations

from typing import Final

CATEGORY_PALETTE: Final[tuple[str, ...]] = (
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
)

UNCLASSIFIED_COLOR: Final[str] = "#6b7280"


def category_color(category: str | None, project_categories: list[str]) -> str:
    """Return the hex color for a material category.

    Args:
        category: Category name, or None for unclassified.
        project_categories: Ordered list of project categories.

    Returns:
        Hex color string (e.g. '#ef4444').
    """
    if category is None:
        return UNCLASSIFIED_COLOR
    try:
        idx = project_categories.index(category)
    except ValueError:
        return UNCLASSIFIED_COLOR
    return CATEGORY_PALETTE[idx % len(CATEGORY_PALETTE)]
