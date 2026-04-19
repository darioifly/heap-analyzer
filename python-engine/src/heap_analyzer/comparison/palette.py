"""Comparison state colors — must match frontend/src/utils/comparisonColors.ts."""

from __future__ import annotations

from typing import Final, Literal

ComparisonState = Literal[
    "unchanged", "grown", "decreased", "added", "removed", "ambiguous"
]

COMPARISON_STATE_COLORS: Final[dict[str, str]] = {
    "unchanged": "#9ca3af",
    "grown": "#ef4444",
    "decreased": "#3b82f6",
    "added": "#22c55e",
    "removed": "#4b5563",
    "ambiguous": "#f97316",
}

COMPARISON_STATE_LABELS_IT: Final[dict[str, str]] = {
    "unchanged": "Invariato",
    "grown": "Cresciuto",
    "decreased": "Diminuito",
    "added": "Nuovo",
    "removed": "Rimosso",
    "ambiguous": "Ambiguo",
}
