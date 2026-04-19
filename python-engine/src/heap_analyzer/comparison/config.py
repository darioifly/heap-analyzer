"""Configuration for temporal comparison."""

from __future__ import annotations

from pydantic import BaseModel


class ComparisonConfig(BaseModel):
    """Configuration thresholds for heap matching and comparison.

    Attributes:
        iou_threshold: Minimum IoU to consider two polygons as the same heap.
        stability_threshold: |delta_V| / V_A below which a matched heap is
            classified as "unchanged".
        grid_resolution: Resolution in meters for delta raster. None = use A's
            resolution.
    """

    iou_threshold: float = 0.3
    stability_threshold: float = 0.05
    grid_resolution: float | None = None
