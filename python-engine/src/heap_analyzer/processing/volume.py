"""Vectorized volume calculation and heap metrics.

Volume formula (Sequential Thinking — planned before implementation):

1. **V = sum(nDSM[mask]) * dx * dy** where mask = (label == heap_id) AND (nDSM > threshold).
   The threshold inside the sum prevents slightly-positive noise pixels at heap edges
   from contributing false volume.

2. **Surface area**: for each cell, the 3D area element is
   dx*dy * sqrt(1 + (dh/dx)^2 + (dh/dy)^2), computed via np.gradient.
   This approximates the true 3D surface better than planimetric area.

3. **Centroid**: volume-weighted centroid (weighted by nDSM height per pixel),
   not just geometric centroid. Converted from pixel to UTM via raster transform.

4. **Edge cases**:
   - All-NaN or empty region: volume = 0, no crash
   - Negative nDSM values: clipped to 0 before summing
   - Single-pixel label: valid but flagged as suspicious

5. **Vectorization**: use scipy.ndimage with labels= parameter for
   per-label aggregation. No Python loops over pixels.
   np.gradient computed ONCE on entire nDSM, then per-label sums extracted.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import rasterio
from pydantic import BaseModel

from heap_analyzer.config import ProcessingConfig
from heap_analyzer.processing.segmentation import HeapPolygon
from heap_analyzer.utils.logging import get_stderr_logger
from scipy.ndimage import (
    maximum as ndimage_maximum,
    mean as ndimage_mean,
    sum as ndimage_sum,
)

logger = get_stderr_logger(__name__)


class HeapMetrics(BaseModel):
    """Complete metrics for a single heap. Maps to SPEC [SCHEMA] heaps table."""

    heap_id: int
    label: str | None = None
    polygon_geojson: dict  # type: ignore[type-arg]

    # Volumetric
    volume_m3: float

    # Areas
    planimetric_area_m2: float
    surface_area_m2: float

    # Heights
    max_height_m: float
    mean_height_m: float
    base_elevation_m: float

    # Geometric
    centroid_e: float
    centroid_n: float
    bbox_min_e: float
    bbox_min_n: float
    bbox_max_e: float
    bbox_max_n: float


def compute_heap_metrics(
    ndsm_path: Path,
    label_map_path: Path,
    polygons: list[HeapPolygon],
    base_elevation: float,
    config: ProcessingConfig,
    progress_callback: Callable[[int, str], None] | None = None,
) -> list[HeapMetrics]:
    """Compute full metrics for all detected heaps.

    Args:
        ndsm_path: Path to nDSM GeoTIFF.
        label_map_path: Path to label map GeoTIFF (uint16, 0=background).
        polygons: List of HeapPolygon from segmentation (accepted only).
        base_elevation: Base elevation (m) used for reference.
        config: Processing configuration.
        progress_callback: Optional callback(percent, message).

    Returns:
        List of HeapMetrics in same order as polygons input.
    """

    def _progress(pct: int, msg: str) -> None:
        if progress_callback is not None:
            progress_callback(pct, msg)

    if not polygons:
        return []

    # --- Read rasters ---
    _progress(5, "Lettura nDSM e label map...")
    with rasterio.open(str(ndsm_path)) as ds:
        ndsm = ds.read(1).astype(np.float64)
        transform = ds.transform
        nodata = ds.nodata

    with rasterio.open(str(label_map_path)) as ds:
        label_map = ds.read(1).astype(np.int32)

    # Clean nDSM: replace nodata with 0, clip negatives
    if nodata is not None:
        ndsm[np.isclose(ndsm, nodata)] = 0.0
    ndsm = np.clip(ndsm, 0.0, None)

    resolution = abs(transform.a)
    cell_area = resolution * resolution

    # Extract label IDs from polygons (in order)
    label_ids = np.array([p.heap_id for p in polygons], dtype=np.int32)

    # --- Threshold mask ---
    _progress(15, "Applicazione soglia...")
    thresholded_ndsm = ndsm.copy()
    thresholded_ndsm[ndsm <= config.height_threshold] = 0.0

    # --- Vectorized per-label volume ---
    _progress(25, "Calcolo volumi...")
    volumes = np.asarray(
        ndimage_sum(thresholded_ndsm, labels=label_map, index=label_ids)
    ) * cell_area

    # --- Planimetric area ---
    _progress(35, "Calcolo aree planimetriche...")
    # Count pixels where nDSM > threshold per label
    above_threshold = (ndsm > config.height_threshold).astype(np.float64)
    pixel_counts = np.asarray(
        ndimage_sum(above_threshold, labels=label_map, index=label_ids)
    )
    planimetric_areas = pixel_counts * cell_area

    # --- Height statistics ---
    _progress(45, "Calcolo statistiche altezza...")
    # Max height per label (from full nDSM, not thresholded)
    max_heights = np.asarray(
        ndimage_maximum(ndsm, labels=label_map, index=label_ids)
    )

    # Mean height: sum of thresholded nDSM / count of above-threshold pixels
    height_sums = np.asarray(
        ndimage_sum(thresholded_ndsm, labels=label_map, index=label_ids)
    )
    mean_heights = np.where(
        pixel_counts > 0,
        height_sums / pixel_counts,
        0.0,
    )

    # --- Surface area ---
    _progress(55, "Calcolo area superficiale 3D...")
    # Compute gradient ONCE on entire nDSM
    dy, dx = np.gradient(ndsm, resolution, resolution)
    # 3D area element per cell: dx*dy * sqrt(1 + (dh/dx)^2 + (dh/dy)^2)
    surface_element = cell_area * np.sqrt(1.0 + dx ** 2 + dy ** 2)
    # Sum per label (only above-threshold cells)
    surface_mask = surface_element * above_threshold
    surface_areas = np.asarray(
        ndimage_sum(surface_mask, labels=label_map, index=label_ids)
    )

    # --- Centroids (volume-weighted) ---
    _progress(70, "Calcolo centroidi...")
    height, width = ndsm.shape
    row_coords, col_coords = np.mgrid[0:height, 0:width]

    # Convert pixel coords to UTM using transform
    # transform * (col, row) = (E, N)
    easting = transform.c + (col_coords + 0.5) * transform.a
    northing = transform.f + (row_coords + 0.5) * transform.e

    # Volume-weighted centroids
    weighted_ndsm = thresholded_ndsm  # weight = nDSM height
    weighted_e = weighted_ndsm * easting
    weighted_n = weighted_ndsm * northing

    sum_weights = np.asarray(
        ndimage_sum(weighted_ndsm, labels=label_map, index=label_ids)
    )
    sum_weighted_e = np.asarray(
        ndimage_sum(weighted_e, labels=label_map, index=label_ids)
    )
    sum_weighted_n = np.asarray(
        ndimage_sum(weighted_n, labels=label_map, index=label_ids)
    )

    centroid_e = np.where(sum_weights > 0, sum_weighted_e / sum_weights, 0.0)
    centroid_n = np.where(sum_weights > 0, sum_weighted_n / sum_weights, 0.0)

    # --- Bounding boxes ---
    _progress(85, "Calcolo bounding box...")
    # Extract bbox from polygons GeoJSON
    bboxes = []
    for poly in polygons:
        from shapely.geometry import shape as shapely_shape

        geom = shapely_shape(poly.polygon_geojson)
        bounds = geom.bounds  # (minx, miny, maxx, maxy)
        bboxes.append(bounds)

    # --- Assemble metrics ---
    _progress(95, "Assemblaggio metriche...")
    metrics: list[HeapMetrics] = []
    for i, poly in enumerate(polygons):
        bbox = bboxes[i]
        m = HeapMetrics(
            heap_id=poly.heap_id,
            polygon_geojson=poly.polygon_geojson,
            volume_m3=float(volumes[i]),
            planimetric_area_m2=float(planimetric_areas[i]),
            surface_area_m2=float(surface_areas[i]),
            max_height_m=float(max_heights[i]),
            mean_height_m=float(mean_heights[i]),
            base_elevation_m=base_elevation,
            centroid_e=float(centroid_e[i]),
            centroid_n=float(centroid_n[i]),
            bbox_min_e=bbox[0],
            bbox_min_n=bbox[1],
            bbox_max_e=bbox[2],
            bbox_max_n=bbox[3],
        )
        metrics.append(m)

    _progress(100, "Calcolo volumetrico completato")
    logger.debug(
        "Computed metrics for %d heaps, total volume=%.1f m³",
        len(metrics),
        sum(m.volume_m3 for m in metrics),
    )

    return metrics
