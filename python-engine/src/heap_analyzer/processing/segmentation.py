"""nDSM computation and heap segmentation from DSM/DTM rasters.

Segmentation pipeline (Sequential Thinking — planned before implementation):

1. **nDSM = DSM - DTM**: subtract terrain to get above-ground heights.
   Clip negatives to 0 (numerical noise at terrain level).

2. **Threshold**: binary mask = nDSM > height_threshold (default 0.5m).
   Removes ground-level noise from the analysis.

3. **Morphological opening** (kernel 3px): erosion then dilation removes
   isolated noise pixels (small bright spots). Binary structuring element,
   8-connectivity (3x3 ones). Must happen BEFORE closing to avoid
   noise pixels bridging separate heaps.

4. **Morphological closing** (kernel 7px): dilation then erosion fills
   small holes and gaps inside heap interiors. Larger kernel than opening
   because gaps inside heaps are typically larger than noise pixels.

5. **Connected components labeling** (scipy.ndimage.label, 8-connectivity):
   assigns unique integer label to each contiguous blob.

6. **Per-component statistics** (vectorized with scipy.ndimage):
   area, compactness (4pi*area/perimeter^2), height mean/std/max.
   Computed WITHOUT Python loops over pixels.

7. **Multi-criteria filters** (from SPEC.md [PIPELINE] Phase 3):
   - area < min_heap_area (50 m^2): noise/vegetation
   - area > max_heap_area (50000 m^2): flag for review (don't filter)
   - compactness > 0.85 AND area < 500 m^2: likely machinery
   - height_std < 0.2m AND height_mean > 2m: likely structure (container)
   Filter reasons in Italian for UI display.

8. **Polygon extraction**: rasterio.features.shapes converts label raster
   to GeoJSON polygons. Simplification with shapely (tolerance = resolution)
   to reduce vertex count without losing accuracy.

9. **Watershed fallback**: if a single label has 2+ local maxima separated
   by more than min_distance pixels, it's likely two merged heaps.
   Split with skimage.segmentation.watershed using peak_local_max markers.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from pydantic import BaseModel
from rasterio.features import shapes as rasterio_shapes
from scipy.ndimage import (
    binary_closing,
    binary_opening,
    label as ndimage_label,
    maximum as ndimage_maximum,
    mean as ndimage_mean,
    standard_deviation as ndimage_std,
    sum as ndimage_sum,
)
from shapely.geometry import Polygon, shape as shapely_shape

from heap_analyzer.config import ProcessingConfig
from heap_analyzer.utils.logging import get_stderr_logger

logger = get_stderr_logger(__name__)


class HeapPolygon(BaseModel):
    """Vector representation of a detected heap."""

    heap_id: int
    polygon_geojson: dict  # type: ignore[type-arg]
    area_m2: float
    compactness: float
    height_std: float
    height_mean: float
    height_max: float
    is_filtered: bool = False
    filter_reason: str | None = None


class SegmentationResult(BaseModel):
    """Result of heap segmentation."""

    label_map_path: Path
    heaps: list[HeapPolygon]
    accepted_count: int
    filtered_count: int


def compute_ndsm(
    dsm_path: Path,
    dtm_path: Path,
    output_path: Path,
) -> Path:
    """Compute nDSM = DSM - DTM. Output GeoTIFF, same CRS/transform/dimensions.

    Args:
        dsm_path: Path to DSM GeoTIFF.
        dtm_path: Path to DTM GeoTIFF.
        output_path: Path for output nDSM GeoTIFF.

    Returns:
        Path to the generated nDSM GeoTIFF.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(str(dsm_path)) as ds_dsm:
        dsm = ds_dsm.read(1).astype(np.float64)
        profile = ds_dsm.profile.copy()
        nodata_dsm = ds_dsm.nodata

    with rasterio.open(str(dtm_path)) as ds_dtm:
        dtm = ds_dtm.read(1).astype(np.float64)
        nodata_dtm = ds_dtm.nodata

    # Replace nodata with NaN
    if nodata_dsm is not None:
        dsm[dsm == nodata_dsm] = np.nan
    if nodata_dtm is not None:
        dtm[dtm == nodata_dtm] = np.nan

    ndsm = dsm - dtm
    # Clip small negatives to 0 (numerical noise at terrain level)
    ndsm = np.clip(ndsm, -0.05, None)
    ndsm[ndsm < 0] = 0.0

    nodata_out = -9999.0
    ndsm_out = np.where(np.isnan(ndsm), nodata_out, ndsm).astype(np.float32)

    profile.update(dtype=np.float32, count=1, nodata=nodata_out)

    with rasterio.open(str(output_path), "w", **profile) as dst:
        dst.write(ndsm_out, 1)

    logger.debug("nDSM written: %s", output_path)
    return output_path


def segment_heaps(
    ndsm_path: Path,
    config: ProcessingConfig,
    progress_callback: Callable[[int, str], None] | None = None,
) -> SegmentationResult:
    """Segment heaps from nDSM raster.

    Args:
        ndsm_path: Path to nDSM GeoTIFF.
        config: Processing configuration.
        progress_callback: Optional callback(percent, message).

    Returns:
        SegmentationResult with label map path, detected heaps, counts.
    """

    def _progress(pct: int, msg: str) -> None:
        if progress_callback is not None:
            progress_callback(pct, msg)

    # --- Read nDSM ---
    _progress(5, "Lettura nDSM...")
    with rasterio.open(str(ndsm_path)) as ds:
        ndsm = ds.read(1).astype(np.float64)
        profile = ds.profile.copy()
        transform = ds.transform
        crs = str(ds.crs)
        nodata = ds.nodata

    if nodata is not None:
        ndsm[np.isclose(ndsm, nodata)] = 0.0

    resolution = abs(transform.a)  # pixel size in meters

    # --- Step 1: Threshold ---
    _progress(10, "Sogliatura nDSM...")
    binary_mask = ndsm > config.height_threshold

    # --- Step 2: Morphological opening (3px kernel) ---
    _progress(20, "Apertura morfologica...")
    struct_open = np.ones((3, 3), dtype=bool)
    opened = binary_opening(binary_mask, structure=struct_open)

    # --- Step 3: Morphological closing (7px kernel) ---
    _progress(30, "Chiusura morfologica...")
    struct_close = np.ones((7, 7), dtype=bool)
    closed = binary_closing(opened, structure=struct_close)

    # --- Step 4: Connected components labeling ---
    _progress(40, "Etichettatura componenti connesse...")
    struct_8conn = np.ones((3, 3), dtype=int)
    label_map, n_labels = ndimage_label(closed, structure=struct_8conn)

    logger.debug("Connected components: %d labels found", n_labels)

    if n_labels == 0:
        # No heaps found — write empty label map and return
        label_map_path = ndsm_path.parent / "label_map.tif"
        _write_label_map(label_map, label_map_path, profile)
        return SegmentationResult(
            label_map_path=label_map_path,
            heaps=[],
            accepted_count=0,
            filtered_count=0,
        )

    # --- Step 5: Per-component statistics (vectorized) ---
    _progress(50, "Calcolo statistiche per componente...")
    label_indices = np.arange(1, n_labels + 1)

    # Area in pixels → m²
    pixel_counts = ndimage_sum(
        np.ones_like(ndsm), labels=label_map, index=label_indices
    )
    areas_m2 = np.asarray(pixel_counts) * resolution * resolution

    # Height statistics using scipy.ndimage (fully vectorized)
    height_means = np.asarray(
        ndimage_mean(ndsm, labels=label_map, index=label_indices)
    )
    height_stds = np.asarray(
        ndimage_std(ndsm, labels=label_map, index=label_indices)
    )
    height_maxs = np.asarray(
        ndimage_maximum(ndsm, labels=label_map, index=label_indices)
    )

    # Compactness: 4*pi*area / perimeter^2
    # Perimeter approximation: count of boundary pixels (label pixel with
    # at least one non-label 4-connected neighbor)
    _progress(55, "Calcolo compattezza...")
    compactness_values = _compute_compactness_vectorized(
        label_map, n_labels, areas_m2, resolution
    )

    # --- Step 6: Apply filters ---
    _progress(65, "Applicazione filtri...")
    heaps: list[HeapPolygon] = []

    for i, lbl in enumerate(label_indices):
        area = float(areas_m2[i])
        compact = float(compactness_values[i])
        h_std = float(height_stds[i])
        h_mean = float(height_means[i])
        h_max = float(height_maxs[i])

        is_filtered = False
        filter_reason: str | None = None

        if area < config.min_heap_area:
            is_filtered = True
            filter_reason = f"Area troppo piccola ({area:.1f} < {config.min_heap_area:.0f} m²)"
        elif compact > 0.85 and area < 500.0 and h_std < 1.0:
            is_filtered = True
            filter_reason = (
                f"Compattezza alta ({compact:.2f}) + area piccola ({area:.1f} m²) "
                f"+ altezza uniforme (std={h_std:.2f}m) — probabile macchinario"
            )
        elif h_std < 0.2 and h_mean > 2.0:
            is_filtered = True
            filter_reason = (
                f"Altezza uniforme (std={h_std:.2f}m, media={h_mean:.2f}m) "
                f"— probabile struttura"
            )

        heap = HeapPolygon(
            heap_id=int(lbl),
            polygon_geojson={},  # filled after polygonization
            area_m2=area,
            compactness=compact,
            height_std=h_std,
            height_mean=h_mean,
            height_max=h_max,
            is_filtered=is_filtered,
            filter_reason=filter_reason,
        )
        heaps.append(heap)

        if area > config.max_heap_area:
            logger.debug(
                "Heap %d: area %.0f m² exceeds max_heap_area (%.0f), flagged for review",
                lbl, area, config.max_heap_area,
            )

    # --- Step 7: Polygonize accepted labels ---
    _progress(75, "Estrazione poligoni...")

    # Build a filtered label map (set filtered labels to 0)
    accepted_label_map = label_map.copy()
    for heap in heaps:
        if heap.is_filtered:
            accepted_label_map[label_map == heap.heap_id] = 0

    # Polygonize all labels (including filtered, for completeness)
    polygons_by_label = labels_to_polygons(
        label_map, transform, crs, simplify_tolerance=resolution
    )

    # Assign polygon GeoJSON to each heap
    for heap in heaps:
        if heap.heap_id in polygons_by_label:
            poly = polygons_by_label[heap.heap_id]
            heap.polygon_geojson = _polygon_to_geojson(poly)

    # --- Step 8: Write label map ---
    _progress(90, "Scrittura label map...")
    label_map_path = ndsm_path.parent / "label_map.tif"
    _write_label_map(label_map, label_map_path, profile)

    accepted_count = sum(1 for h in heaps if not h.is_filtered)
    filtered_count = sum(1 for h in heaps if h.is_filtered)

    _progress(100, "Segmentazione completata")
    logger.debug(
        "Segmentation: %d accepted, %d filtered, %d total",
        accepted_count, filtered_count, len(heaps),
    )

    return SegmentationResult(
        label_map_path=label_map_path,
        heaps=heaps,
        accepted_count=accepted_count,
        filtered_count=filtered_count,
    )


def labels_to_polygons(
    label_map: np.ndarray,
    transform: Affine,
    crs: str,
    simplify_tolerance: float,
) -> dict[int, Polygon]:
    """Extract one polygon per label using rasterio.features.shapes + shapely simplify.

    Args:
        label_map: 2D integer array with label IDs (0 = background).
        transform: Affine transform for the raster.
        crs: CRS string.
        simplify_tolerance: Simplification tolerance in CRS units.

    Returns:
        Dictionary mapping label_id to shapely Polygon.
    """
    result: dict[int, Polygon] = {}

    # rasterio.features.shapes yields (geometry_dict, value) pairs
    label_int32 = label_map.astype(np.int32)
    mask = label_int32 > 0

    for geom_dict, value in rasterio_shapes(label_int32, mask=mask, transform=transform):
        lbl = int(value)
        poly = shapely_shape(geom_dict)
        if not poly.is_valid:
            poly = poly.buffer(0)  # fix self-intersections
        poly = poly.simplify(simplify_tolerance, preserve_topology=True)
        if lbl in result:
            # Merge with existing (multi-part label)
            result[lbl] = result[lbl].union(poly)
        else:
            result[lbl] = poly

    return result


def split_with_watershed(
    ndsm: np.ndarray,
    label_map: np.ndarray,
    label_id: int,
    min_distance: int = 10,
) -> np.ndarray:
    """Watershed split for a single label containing multiple local maxima.

    Args:
        ndsm: 2D nDSM array.
        label_map: 2D label array (modified in place with new sub-labels).
        label_id: Label to split.
        min_distance: Minimum distance between peaks in pixels.

    Returns:
        Updated label_map with new sub-labels replacing label_id.
    """
    from skimage.feature import peak_local_max
    from skimage.segmentation import watershed

    mask = label_map == label_id
    local_ndsm = ndsm * mask

    # Find local maxima
    coords = peak_local_max(
        local_ndsm, min_distance=min_distance, labels=mask.astype(int)
    )

    if len(coords) <= 1:
        # No split needed
        return label_map

    # Create markers
    markers = np.zeros_like(label_map, dtype=np.int32)
    next_label = label_map.max() + 1
    for i, (r, c) in enumerate(coords):
        markers[r, c] = next_label + i

    # Watershed: invert nDSM (watershed fills basins)
    ws = watershed(-local_ndsm, markers=markers, mask=mask)

    # Update label_map
    label_map[mask] = ws[mask]

    logger.debug(
        "Watershed split label %d into %d sub-labels",
        label_id, len(coords),
    )
    return label_map


def _compute_compactness_vectorized(
    label_map: np.ndarray,
    n_labels: int,
    areas_m2: np.ndarray,
    resolution: float,
) -> np.ndarray:
    """Compute compactness = 4*pi*area / perimeter^2 for each label.

    Perimeter is estimated by counting boundary pixels: label pixels that
    have at least one 4-connected neighbor with a different label.
    """
    # Detect boundary pixels: shift in 4 directions and compare
    pad = np.pad(label_map, 1, mode="constant", constant_values=0)
    boundary = (
        (pad[1:-1, 1:-1] != pad[:-2, 1:-1])   # top
        | (pad[1:-1, 1:-1] != pad[2:, 1:-1])   # bottom
        | (pad[1:-1, 1:-1] != pad[1:-1, :-2])  # left
        | (pad[1:-1, 1:-1] != pad[1:-1, 2:])   # right
    ) & (label_map > 0)

    # Count boundary pixels per label
    label_indices = np.arange(1, n_labels + 1)
    boundary_counts = ndimage_sum(
        boundary.astype(np.float64), labels=label_map, index=label_indices
    )
    perimeters_m = np.asarray(boundary_counts) * resolution

    # Compactness
    areas = np.asarray(areas_m2)
    compactness = np.where(
        perimeters_m > 0,
        4.0 * np.pi * areas / (perimeters_m ** 2),
        0.0,
    )
    # Clamp to [0, 1]
    compactness = np.clip(compactness, 0.0, 1.0)

    return compactness


def _write_label_map(
    label_map: np.ndarray,
    output_path: Path,
    profile: dict,  # type: ignore[type-arg]
) -> None:
    """Write label map as uint16 GeoTIFF."""
    profile.update(dtype=np.uint16, count=1, nodata=0)
    label_out = label_map.astype(np.uint16)

    with rasterio.open(str(output_path), "w", **profile) as dst:
        dst.write(label_out, 1)

    logger.debug("Label map written: %s (max label=%d)", output_path, label_out.max())


def _polygon_to_geojson(poly: Polygon) -> dict:  # type: ignore[type-arg]
    """Convert shapely Polygon to GeoJSON dict."""
    if hasattr(poly, "__geo_interface__"):
        return dict(poly.__geo_interface__)
    return {"type": "Polygon", "coordinates": [list(poly.exterior.coords)]}
