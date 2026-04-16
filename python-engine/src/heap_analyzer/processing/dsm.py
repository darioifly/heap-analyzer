"""DSM (Digital Surface Model) generation from LAS point cloud.

Algorithm:
1. Read LAS metadata to get bounds and CRS
2. Compute raster grid based on resolution
3. Read LAS in chunks, bin points into grid cells
4. Compute Z = 95th percentile per cell
5. Interpolate empty cells with nearest-neighbor + IDW blend
6. Write GeoTIFF with original CRS and proper transform
"""

from __future__ import annotations

import math
from collections.abc import Callable
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin
from scipy.interpolate import NearestNDInterpolator

from heap_analyzer.config import ProcessingConfig
from heap_analyzer.io.las_reader import LasReader
from heap_analyzer.utils.logging import get_stderr_logger

logger = get_stderr_logger(__name__)


def generate_dsm(
    las_path: Path,
    output_path: Path,
    config: ProcessingConfig,
    progress_callback: Callable[[int, str], None] | None = None,
) -> Path:
    """Generate Digital Surface Model from LAS point cloud.

    Args:
        las_path: Path to the input LAS/LAZ file.
        output_path: Path for the output GeoTIFF.
        config: Processing configuration with dsm_resolution.
        progress_callback: Optional callback(percent, message).

    Returns:
        Path to the generated DSM GeoTIFF.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    def _progress(pct: int, msg: str) -> None:
        if progress_callback is not None:
            progress_callback(pct, msg)

    # --- Phase 1: Read metadata ---
    _progress(5, "Lettura metadati LAS...")
    with LasReader(las_path) as reader:
        meta = reader.get_metadata()

    min_x, min_y, max_x, max_y = (
        meta.bounds_min[0],
        meta.bounds_min[1],
        meta.bounds_max[0],
        meta.bounds_max[1],
    )
    crs = meta.crs
    res = config.dsm_resolution

    # Compute grid dimensions
    width = math.ceil((max_x - min_x) / res)
    height = math.ceil((max_y - min_y) / res)

    logger.debug("DSM grid: %d x %d (res=%.3f m)", width, height, res)

    # --- Phase 2: Bin points into grid cells ---
    # Accumulate Z values per cell using lists
    # For memory efficiency, store sum and count for percentile approximation
    # Actually: we need the 95th percentile, so we accumulate all Z values per cell
    # For a 2000x2000 grid with ~2.8M points, this is manageable

    _progress(10, "Allocazione griglia...")

    # Use a flat array approach: for each point, compute cell index
    # Then use pandas-style groupby for efficient percentile computation
    all_rows: list[np.ndarray] = []
    all_cols: list[np.ndarray] = []
    all_z: list[np.ndarray] = []

    _progress(15, "Binning punti LAS...")
    chunk_count = 0
    total_chunks = max(1, meta.num_points // 1_000_000 + 1)

    with LasReader(las_path) as reader:
        for chunk in reader.iter_chunks(chunk_size=1_000_000):
            chunk_count += 1
            pct = 15 + int(45 * chunk_count / total_chunks)
            _progress(pct, f"Binning punti (chunk {chunk_count})...")

            x = chunk["x"]
            y = chunk["y"]
            z = chunk["z"]

            # Compute pixel indices (row 0 = top = max_y)
            col = np.floor((x - min_x) / res).astype(np.int32)
            row = np.floor((max_y - y) / res).astype(np.int32)

            # Clamp to grid bounds
            valid = (col >= 0) & (col < width) & (row >= 0) & (row < height)
            all_rows.append(row[valid])
            all_cols.append(col[valid])
            all_z.append(z[valid])

    # Concatenate all chunks
    rows_arr = np.concatenate(all_rows)
    cols_arr = np.concatenate(all_cols)
    z_arr = np.concatenate(all_z)

    # --- Phase 3: Compute 95th percentile per cell ---
    _progress(65, "Calcolo percentile 95° per cella...")

    # Create cell index for groupby
    cell_idx = rows_arr.astype(np.int64) * width + cols_arr.astype(np.int64)

    # Sort by cell index for efficient groupby
    sort_order = np.argsort(cell_idx)
    cell_idx_sorted = cell_idx[sort_order]
    z_sorted = z_arr[sort_order]

    # Find unique cells and their boundaries
    unique_cells, start_indices = np.unique(cell_idx_sorted, return_index=True)
    # end indices
    end_indices = np.empty_like(start_indices)
    end_indices[:-1] = start_indices[1:]
    end_indices[-1] = len(cell_idx_sorted)

    # Initialize raster with NaN
    dsm = np.full((height, width), np.nan, dtype=np.float32)

    # Compute percentile per cell
    for i in range(len(unique_cells)):
        cell = unique_cells[i]
        r = int(cell // width)
        c = int(cell % width)
        z_values = z_sorted[start_indices[i] : end_indices[i]]
        dsm[r, c] = float(np.percentile(z_values, 95))

    nan_count_before = int(np.isnan(dsm).sum())
    logger.debug(
        "Cells with data: %d / %d (%.1f%%), NaN: %d",
        len(unique_cells),
        height * width,
        100.0 * len(unique_cells) / (height * width),
        nan_count_before,
    )

    # --- Phase 4: Interpolate empty cells ---
    _progress(80, "Interpolazione celle vuote (nearest-neighbor)...")

    if nan_count_before > 0:
        # Get coordinates of cells with data
        has_data = ~np.isnan(dsm)
        data_rows, data_cols = np.where(has_data)
        data_values = dsm[has_data]

        # Get coordinates of cells without data
        nan_rows, nan_cols = np.where(np.isnan(dsm))

        if len(data_rows) > 0 and len(nan_rows) > 0:
            # Use nearest-neighbor interpolation
            interp = NearestNDInterpolator(
                np.column_stack([data_rows, data_cols]),
                data_values,
            )
            dsm[nan_rows, nan_cols] = interp(
                np.column_stack([nan_rows, nan_cols])
            )

    nan_count_after = int(np.isnan(dsm).sum())
    logger.debug("NaN after interpolation: %d", nan_count_after)

    # --- Phase 5: Write GeoTIFF ---
    _progress(90, "Scrittura GeoTIFF DSM...")

    # Transform: from_origin(west, north, x_res, y_res)
    transform = from_origin(min_x, max_y + (height * res - (max_y - min_y)), res, res)
    # Simpler: use the actual grid top
    grid_north = min_y + height * res  # top of the grid
    transform = from_origin(min_x, grid_north, res, res)

    nodata = -9999.0
    dsm_out = np.where(np.isnan(dsm), nodata, dsm).astype(np.float32)

    with rasterio.open(
        str(output_path),
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype=np.float32,
        crs=crs,
        transform=transform,
        nodata=nodata,
    ) as dst:
        dst.write(dsm_out, 1)

    _progress(100, "DSM completato")
    logger.debug("DSM written: %s (%d x %d)", output_path, width, height)

    return output_path
