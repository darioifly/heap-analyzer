"""Cross-section profile extraction from DSM/DTM rasters.

Samples elevation values along a line at regular intervals using bilinear
interpolation, producing DSM and DTM profiles for cross-section analysis.
"""

from __future__ import annotations

import sys
from typing import Optional

import numpy as np
import rasterio
from shapely.geometry import LineString

from heap_analyzer.utils.logging import get_stderr_logger

_log = get_stderr_logger(__name__)


def _bilinear_sample(array: np.ndarray, row: float, col: float) -> float:
    """Bilinear interpolation on a 2D numpy array.

    Args:
        array: 2D array of raster values.
        row: Fractional row index.
        col: Fractional column index.

    Returns:
        Interpolated value, or NaN if out of bounds.
    """
    h, w = array.shape
    if row < 0 or row > h - 1 or col < 0 or col > w - 1:
        return float("nan")
    r0, c0 = int(np.floor(row)), int(np.floor(col))
    r1 = min(r0 + 1, h - 1)
    c1 = min(c0 + 1, w - 1)
    dr, dc = row - r0, col - c0
    v = (
        array[r0, c0] * (1 - dr) * (1 - dc)
        + array[r0, c1] * (1 - dr) * dc
        + array[r1, c0] * dr * (1 - dc)
        + array[r1, c1] * dr * dc
    )
    return float(v)


def extract_profile(
    dsm_path: str,
    dtm_path: str,
    line_coords: list[tuple[float, float]],
    sample_spacing: Optional[float] = None,
) -> dict:
    """Extract DSM and DTM elevation profiles along a polyline.

    Args:
        dsm_path: Path to DSM GeoTIFF.
        dtm_path: Path to DTM GeoTIFF (must share CRS and alignment with DSM).
        line_coords: List of (x, y) tuples in the raster CRS.
        sample_spacing: Meters between samples (default: raster pixel size).

    Returns:
        Dict with keys: distance, dsm_z, dtm_z, length, num_samples,
        max_height, section_area, crs, line_coords.

    Raises:
        ValueError: If line has <2 points, zero length, or rasters misaligned.
    """
    if len(line_coords) < 2:
        raise ValueError("Line must have at least 2 points")

    line = LineString(line_coords)
    length = line.length
    if length <= 0:
        raise ValueError("Line has zero length")

    with rasterio.open(dsm_path) as dsm_src, rasterio.open(dtm_path) as dtm_src:
        dsm = dsm_src.read(1).astype(np.float64)
        dtm = dtm_src.read(1).astype(np.float64)
        transform = dsm_src.transform
        nodata_dsm = dsm_src.nodata
        nodata_dtm = dtm_src.nodata
        crs_str = str(dsm_src.crs) if dsm_src.crs else ""
        pixel_size = abs(transform.a)

    if sample_spacing is None:
        sample_spacing = pixel_size
    if sample_spacing <= 0:
        raise ValueError("sample_spacing must be > 0")

    n = max(2, int(np.ceil(length / sample_spacing)) + 1)
    distances = np.linspace(0, length, n)
    dsm_vals = np.empty(n)
    dtm_vals = np.empty(n)

    _log.debug("Sampling %d points along %.2f m line (spacing=%.3f m)", n, length, sample_spacing)

    for i, d in enumerate(distances):
        pt = line.interpolate(d)
        # Convert world (x, y) -> fractional (row, col) via inverse transform
        col = (pt.x - transform.c) / transform.a
        row = (pt.y - transform.f) / transform.e  # transform.e is negative (north-up)
        v_dsm = _bilinear_sample(dsm, row, col)
        v_dtm = _bilinear_sample(dtm, row, col)
        # Honor nodata
        if nodata_dsm is not None and not np.isnan(v_dsm) and abs(v_dsm - nodata_dsm) < 1e-6:
            v_dsm = float("nan")
        if nodata_dtm is not None and not np.isnan(v_dtm) and abs(v_dtm - nodata_dtm) < 1e-6:
            v_dtm = float("nan")
        dsm_vals[i] = v_dsm
        dtm_vals[i] = v_dtm

    # Compute stats (NaN-safe)
    diff = dsm_vals - dtm_vals
    positive = np.where(diff > 0, diff, 0.0)
    valid = ~np.isnan(positive)

    if valid.any():
        ds = np.diff(distances)
        seg_valid = valid[:-1] & valid[1:]
        seg_integrands = 0.5 * (positive[:-1] + positive[1:]) * ds
        seg_integrands = np.where(seg_valid, seg_integrands, 0.0)
        section_area = float(np.sum(seg_integrands))
        max_height = float(np.nanmax(positive))
    else:
        section_area = 0.0
        max_height = 0.0

    return {
        "distance": distances.tolist(),
        "dsm_z": [None if np.isnan(v) else round(float(v), 4) for v in dsm_vals],
        "dtm_z": [None if np.isnan(v) else round(float(v), 4) for v in dtm_vals],
        "length": round(float(length), 4),
        "num_samples": n,
        "max_height": round(max_height, 4),
        "section_area": round(section_area, 4),
        "crs": crs_str,
        "line_coords": [list(c) for c in line_coords],
    }
