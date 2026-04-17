"""Ground elevation sampling from DSM within user-drawn reference polygons.

Used by F3.S02 base-elevation override: the user draws polygons on known
bare-ground areas, and this module computes the mean Z to suggest as the
new base elevation.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
import rasterio.features
from shapely.geometry import shape as shapely_shape

from heap_analyzer.utils.logging import get_stderr_logger

logger = get_stderr_logger(__name__)


def sample_dsm_in_polygons(
    dsm_path: str | Path,
    polygons_geojson: list[dict],  # type: ignore[type-arg]
) -> dict:  # type: ignore[type-arg]
    """Sample the DSM within user-drawn ground-reference polygons.

    Args:
        dsm_path: Path to the DSM GeoTIFF.
        polygons_geojson: List of GeoJSON geometry dicts (Polygon).

    Returns:
        {
            "mean_elevation": float,
            "std_elevation": float,
            "num_pixels": int,
            "per_polygon": [
                {"mean": float|None, "std": float|None, "num_pixels": int},
                ...
            ]
        }

    Raises:
        ValueError: If no polygon intersects the DSM raster.
        FileNotFoundError: If dsm_path does not exist.
    """
    dsm_path = Path(dsm_path)
    if not dsm_path.is_file():
        raise FileNotFoundError(f"DSM file not found: {dsm_path}")

    with rasterio.open(str(dsm_path)) as src:
        dsm = src.read(1).astype(np.float64)
        transform = src.transform
        nodata = src.nodata

    all_values: list[np.ndarray] = []
    per_polygon: list[dict] = []  # type: ignore[type-arg]

    for pg in polygons_geojson:
        geom = shapely_shape(pg)
        if not geom.is_valid:
            geom = geom.buffer(0)

        mask = rasterio.features.rasterize(
            [(geom, 1)],
            out_shape=dsm.shape,
            transform=transform,
            fill=0,
            dtype=np.uint8,
        ).astype(bool)

        # Exclude nodata pixels
        if nodata is not None:
            mask &= ~np.isclose(dsm, nodata)

        vals = dsm[mask]

        if len(vals) == 0:
            per_polygon.append({"mean": None, "std": None, "num_pixels": 0})
            continue

        per_polygon.append({
            "mean": float(np.mean(vals)),
            "std": float(np.std(vals)),
            "num_pixels": int(len(vals)),
        })
        all_values.append(vals)

    if not all_values:
        raise ValueError("No ground polygons intersect the DSM raster")

    combined = np.concatenate(all_values)
    result = {
        "mean_elevation": float(np.mean(combined)),
        "std_elevation": float(np.std(combined)),
        "num_pixels": int(len(combined)),
        "per_polygon": per_polygon,
    }

    logger.debug(
        "Ground sampling: mean=%.3f std=%.3f pixels=%d polygons=%d",
        result["mean_elevation"],
        result["std_elevation"],
        result["num_pixels"],
        len(polygons_geojson),
    )
    return result
