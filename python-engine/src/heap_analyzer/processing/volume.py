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
import rasterio.features
from affine import Affine
from pydantic import BaseModel
from scipy.ndimage import maximum as ndimage_maximum
from scipy.ndimage import sum as ndimage_sum
from shapely.geometry import shape as shapely_shape

from heap_analyzer.config import ProcessingConfig
from heap_analyzer.processing.segmentation import HeapPolygon
from heap_analyzer.utils.logging import get_stderr_logger

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


def _compute_metrics_for_mask(
    ndsm: np.ndarray,
    mask: np.ndarray,
    transform: Affine,
    base_elevation: float,
    height_threshold: float,
) -> HeapMetrics:
    """Vectorized metrics for a single heap given a pre-computed boolean mask.

    Uses the same formulas as compute_heap_metrics (batch version) but
    operates directly on a boolean mask instead of a label map.

    Invariants:
      - NO Python loops over pixels.
      - Returns HeapMetrics with volume, areas, heights, centroid, bbox.
    """
    resolution = abs(transform.a)
    cell_area = resolution * resolution

    # Threshold: only pixels above height_threshold contribute
    thresholded = ndsm.copy()
    thresholded[ndsm <= height_threshold] = 0.0

    # Volume = sum(thresholded[mask]) * cell_area
    masked_thresholded = thresholded[mask]
    volume = float(np.sum(masked_thresholded) * cell_area)

    # Planimetric area = count of above-threshold pixels * cell_area
    above_threshold = (ndsm[mask] > height_threshold)
    pixel_count = float(np.sum(above_threshold))
    planimetric_area = pixel_count * cell_area

    # Height statistics (from full nDSM, not thresholded)
    masked_ndsm = ndsm[mask]
    max_height = float(np.max(masked_ndsm)) if masked_ndsm.size > 0 else 0.0
    mean_height = (
        float(np.sum(masked_thresholded) / pixel_count)
        if pixel_count > 0
        else 0.0
    )

    # Surface area: 3D area element = cell_area * sqrt(1 + (dh/dx)^2 + (dh/dy)^2)
    dy, dx = np.gradient(ndsm, resolution, resolution)
    surface_element = cell_area * np.sqrt(1.0 + dx ** 2 + dy ** 2)
    above_mask_full = np.zeros_like(ndsm, dtype=bool)
    above_mask_full[mask] = ndsm[mask] > height_threshold
    surface_area = float(np.sum(surface_element[above_mask_full]))

    # Volume-weighted centroid
    height, width = ndsm.shape
    row_coords, col_coords = np.mgrid[0:height, 0:width]
    easting = transform.c + (col_coords + 0.5) * transform.a
    northing = transform.f + (row_coords + 0.5) * transform.e

    weights = thresholded[mask]
    sum_w = float(np.sum(weights))
    if sum_w > 0:
        centroid_e = float(np.sum(weights * easting[mask]) / sum_w)
        centroid_n = float(np.sum(weights * northing[mask]) / sum_w)
    else:
        centroid_e = float(np.mean(easting[mask]))
        centroid_n = float(np.mean(northing[mask]))

    # Bounding box from mask pixel extent
    rows_with_data = np.any(mask, axis=1)
    cols_with_data = np.any(mask, axis=0)
    row_min, row_max = np.where(rows_with_data)[0][[0, -1]]
    col_min, col_max = np.where(cols_with_data)[0][[0, -1]]
    bbox_min_e = transform.c + col_min * transform.a
    bbox_max_e = transform.c + (col_max + 1) * transform.a
    bbox_max_n = transform.f + row_min * transform.e
    bbox_min_n = transform.f + (row_max + 1) * transform.e

    return HeapMetrics(
        heap_id=0,
        polygon_geojson={},
        volume_m3=volume,
        planimetric_area_m2=planimetric_area,
        surface_area_m2=surface_area,
        max_height_m=max_height,
        mean_height_m=mean_height,
        base_elevation_m=base_elevation,
        centroid_e=centroid_e,
        centroid_n=centroid_n,
        bbox_min_e=bbox_min_e,
        bbox_min_n=bbox_min_n,
        bbox_max_e=bbox_max_e,
        bbox_max_n=bbox_max_n,
    )


def recompute_single_heap(
    ndsm_path: str | Path,
    polygon_geojson: dict,  # type: ignore[type-arg]
    base_elevation: float,
    config: ProcessingConfig,
) -> HeapMetrics:
    """Recompute metrics for a single heap given a GeoJSON polygon.

    Used by interactive polygon editing (F3.S01). Reuses the same
    vectorized computation as compute_heap_metrics via _compute_metrics_for_mask.

    Args:
        ndsm_path: Path to the survey's nDSM GeoTIFF.
        polygon_geojson: GeoJSON geometry dict (Polygon or MultiPolygon).
        base_elevation: Meters above sea level, used as reference plane.
        config: Processing config (for height_threshold).

    Returns:
        HeapMetrics with volume, areas, heights, centroid, bbox.

    Raises:
        ValueError: If polygon is invalid or does not intersect the nDSM.
    """
    with rasterio.open(str(ndsm_path)) as src:
        ndsm = src.read(1).astype(np.float64)
        transform = src.transform
        raster_shape = ndsm.shape
        nodata = src.nodata

    # Clean nDSM: replace nodata (incl. NaN) with 0, clip negatives.
    # np.isclose does not match NaN, so handle NaN explicitly — a polygon that
    # lands on an all-NaN tile (no LiDAR returns) should yield volume=0, not NaN.
    if nodata is not None and not np.isnan(nodata):
        ndsm[np.isclose(ndsm, nodata)] = 0.0
    ndsm = np.nan_to_num(ndsm, nan=0.0, posinf=0.0, neginf=0.0)
    ndsm = np.clip(ndsm, 0.0, None)

    geom = shapely_shape(polygon_geojson)
    if not geom.is_valid:
        geom = geom.buffer(0)  # attempt repair
    if geom.is_empty or not geom.is_valid:
        raise ValueError("Invalid polygon geometry")

    mask = rasterio.features.rasterize(
        [(geom, 1)],
        out_shape=raster_shape,
        transform=transform,
        fill=0,
        dtype=np.uint8,
    ).astype(bool)

    if not mask.any():
        raise ValueError("Polygon does not intersect the nDSM raster")

    metrics = _compute_metrics_for_mask(
        ndsm, mask, transform, base_elevation, config.height_threshold
    )

    # Attach the polygon and compute bbox from geometry
    bounds = geom.bounds  # (minx, miny, maxx, maxy)
    return HeapMetrics(
        heap_id=metrics.heap_id,
        polygon_geojson=polygon_geojson,
        volume_m3=metrics.volume_m3,
        planimetric_area_m2=metrics.planimetric_area_m2,
        surface_area_m2=metrics.surface_area_m2,
        max_height_m=metrics.max_height_m,
        mean_height_m=metrics.mean_height_m,
        base_elevation_m=base_elevation,
        centroid_e=metrics.centroid_e,
        centroid_n=metrics.centroid_n,
        bbox_min_e=bounds[0],
        bbox_min_n=bounds[1],
        bbox_max_e=bounds[2],
        bbox_max_n=bounds[3],
    )


def recompute_all_heaps(
    ndsm_path: str | Path,
    heaps: list[dict],  # type: ignore[type-arg]
    base_elevation: float,
    config: ProcessingConfig,
    original_base_elevation: float | None = None,
) -> list[dict]:  # type: ignore[type-arg]
    """Recompute metrics for multiple heaps with a shared base elevation.

    Opens the nDSM once, adjusts heights for the base-elevation delta,
    iterates over heaps, returns list of {id, metrics: dict} dicts.

    The nDSM was computed as DSM - DTM with the original base. When the
    user overrides the base elevation by delta, nDSM values are adjusted:
    nDSM_adjusted = nDSM - (new_base - original_base).

    Used by F3.S02 base-elevation override (global recalc).

    Args:
        ndsm_path: Path to the survey's nDSM GeoTIFF.
        heaps: Each dict has 'id' (int) and 'polygon_geojson' (GeoJSON dict).
        base_elevation: New base elevation in meters.
        config: Processing config (for height_threshold).
        original_base_elevation: Original base elevation used to compute
            the nDSM. If None, assumes same as base_elevation (no adjustment).

    Returns:
        List of {'id': int, 'metrics': dict} where metrics is HeapMetrics.model_dump().
    """
    with rasterio.open(str(ndsm_path)) as src:
        ndsm = src.read(1).astype(np.float64)
        transform = src.transform
        raster_shape = ndsm.shape
        nodata = src.nodata

    # Clean nDSM: replace nodata with 0, clip negatives
    if nodata is not None:
        ndsm[np.isclose(ndsm, nodata)] = 0.0

    # Adjust nDSM for base elevation change: raising base reduces heights
    if original_base_elevation is not None:
        delta = base_elevation - original_base_elevation
        if abs(delta) > 1e-6:
            ndsm = ndsm - delta

    ndsm = np.clip(ndsm, 0.0, None)

    results: list[dict] = []  # type: ignore[type-arg]
    for h in heaps:
        geom = shapely_shape(h["polygon_geojson"])
        if not geom.is_valid:
            geom = geom.buffer(0)
        if geom.is_empty:
            logger.warning("Heap %s: empty geometry, skipping", h["id"])
            continue

        mask = rasterio.features.rasterize(
            [(geom, 1)],
            out_shape=raster_shape,
            transform=transform,
            fill=0,
            dtype=np.uint8,
        ).astype(bool)

        if not mask.any():
            logger.warning("Heap %s: polygon does not intersect nDSM, skipping", h["id"])
            continue

        metrics = _compute_metrics_for_mask(
            ndsm, mask, transform, base_elevation, config.height_threshold
        )

        bounds = geom.bounds
        full_metrics = HeapMetrics(
            heap_id=metrics.heap_id,
            polygon_geojson=h["polygon_geojson"],
            volume_m3=metrics.volume_m3,
            planimetric_area_m2=metrics.planimetric_area_m2,
            surface_area_m2=metrics.surface_area_m2,
            max_height_m=metrics.max_height_m,
            mean_height_m=metrics.mean_height_m,
            base_elevation_m=base_elevation,
            centroid_e=metrics.centroid_e,
            centroid_n=metrics.centroid_n,
            bbox_min_e=bounds[0],
            bbox_min_n=bounds[1],
            bbox_max_e=bounds[2],
            bbox_max_n=bounds[3],
        )
        results.append({"id": h["id"], "metrics": full_metrics.model_dump()})

    logger.debug(
        "Recomputed %d heaps with base_elevation=%.2f",
        len(results),
        base_elevation,
    )
    return results
