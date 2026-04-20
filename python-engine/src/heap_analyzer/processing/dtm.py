"""DTM (Digital Terrain Model) estimation from DSM.

Strategy decision tree (Sequential Thinking — planned before implementation):

1. Manual mode: user provides base elevation → flat DTM at that Z.
   Confidence = 1.0.

2. Ground regions mode: user provides polygons over known terrain →
   mean DSM Z in those polygons → flat DTM.
   Confidence = 1.0.

3. Ground-classification mode (F2.S10): when a LAS path is provided AND the
   file carries ASPRS ground classification (class 2), rasterise those points
   onto the DSM grid (min Z per cell), then nearest-neighbour fill the empty
   cells. This is the correct DTM for industrial sites with mixed pavement
   levels, where morphological opening fails because the kernel cannot exceed
   the widest heap. Coverage ≥ 5% of DSM cells is required; otherwise fall
   through to strategy 4. Confidence = 0.95.

4. Auto mode (default, fallback):
   a. Morphological opening: scipy.ndimage.grey_opening removes peaks
      shorter than kernel. The opened raster approximates the terrain.
   b. Peripheral percentile: outer 10% border of DSM → low percentile
      (5th by default). Cross-validation against morphological result.
   c. Confidence scoring:
      - |morpho - periph| < 0.1m → 0.9 (high)
      - |morpho - periph| < 0.5m → 0.7 (medium)
      - Otherwise → 0.5, prefer peripheral, emit warning

The DTM raster output is the chosen strategy's spatially-varying surface.
The estimated_base_elevation scalar is a summary value derived from it.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from pathlib import Path

import laspy
import numpy as np
import rasterio
from pydantic import BaseModel
from scipy.ndimage import distance_transform_edt, grey_opening

from heap_analyzer.config import ProcessingConfig
from heap_analyzer.utils.logging import get_stderr_logger

logger = get_stderr_logger(__name__)

# Minimum fraction of DSM cells that must receive at least one ground-classified
# LAS point for the ground-classification strategy to be considered reliable.
# Below this the algorithm falls back to morphological opening.
_GROUND_COVERAGE_THRESHOLD = 0.05

# Chunk size for laspy iteration — balances memory and per-chunk overhead.
_LAS_CHUNK_SIZE = 1_000_000

# ASPRS standard classification code for ground points.
_ASPRS_GROUND = 2


class DtmMethod(StrEnum):
    """DTM estimation method used."""

    MORPHOLOGICAL = "morphological"
    PERCENTILE = "percentile"
    GROUND_REGIONS = "ground_regions"
    GROUND_CLASSIFICATION = "ground_classification"
    MANUAL = "manual"


class DtmResult(BaseModel):
    """Result of DTM estimation."""

    output_path: Path
    method: DtmMethod
    estimated_base_elevation: float
    confidence: float
    notes: str


def estimate_dtm_from_ground_classification(
    las_path: Path,
    dsm_shape: tuple[int, int],
    dsm_transform: rasterio.Affine,
) -> tuple[np.ndarray, float] | None:
    """Build a DTM by rasterising ASPRS class=2 ground points from a LAS file.

    For each DSM cell, the minimum Z among ground-classified points landing
    in that cell is recorded (ground surface is the lowest return). Empty
    cells are then filled with the nearest populated cell's value (Voronoi-
    style fill via scipy distance transform).

    Args:
        las_path: Path to the LAS/LAZ file (must carry classification).
        dsm_shape: (height, width) of the DSM grid.
        dsm_transform: rasterio Affine transform of the DSM (for pixel lookup).

    Returns:
        Tuple of (dtm_array, coverage_ratio) or ``None`` if the file has no
        classification field, no ground points were found, or coverage is
        below :data:`_GROUND_COVERAGE_THRESHOLD`. A ``None`` return is the
        caller's signal to fall back to morphological estimation.
    """
    height, width = dsm_shape
    # Use +inf as sentinel for "no ground seen"; np.minimum vs inf preserves actual minima.
    min_z = np.full((height, width), np.inf, dtype=np.float64)
    ground_points_seen = 0

    try:
        with laspy.open(str(las_path)) as reader:
            dim_names = [d.name for d in reader.header.point_format.dimensions]
            if "classification" not in dim_names:
                logger.info(
                    "LAS %s has no classification field — skipping ground strategy",
                    las_path,
                )
                return None

            inv_transform = ~dsm_transform

            for chunk in reader.chunk_iterator(_LAS_CHUNK_SIZE):
                cls = np.asarray(chunk.classification, dtype=np.uint8)
                mask = cls == _ASPRS_GROUND
                if not np.any(mask):
                    continue

                xs = np.asarray(chunk.x, dtype=np.float64)[mask]
                ys = np.asarray(chunk.y, dtype=np.float64)[mask]
                zs = np.asarray(chunk.z, dtype=np.float64)[mask]

                # Rasterio Affine multiplies as (x, y) -> (col, row).
                cols_f, rows_f = inv_transform * (xs, ys)
                cols = np.floor(cols_f).astype(np.int64)
                rows = np.floor(rows_f).astype(np.int64)

                in_bounds = (
                    (rows >= 0) & (rows < height) & (cols >= 0) & (cols < width)
                )
                if not np.any(in_bounds):
                    continue

                rr = rows[in_bounds]
                cc = cols[in_bounds]
                zz = zs[in_bounds]
                ground_points_seen += len(zz)

                # Cell-wise minimum Z. np.minimum.at handles duplicate indices.
                np.minimum.at(min_z, (rr, cc), zz)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Ground-classification DTM failed to read LAS: %s", exc)
        return None

    if ground_points_seen == 0:
        logger.info("LAS %s has zero ground-classified points", las_path)
        return None

    # Coverage: fraction of cells that received at least one ground point.
    populated = np.isfinite(min_z)
    coverage = float(np.sum(populated)) / float(height * width)
    logger.debug(
        "Ground classification: %d points in file, %.2f%% DSM coverage",
        ground_points_seen,
        coverage * 100.0,
    )

    if coverage < _GROUND_COVERAGE_THRESHOLD:
        logger.info(
            "Ground coverage %.2f%% below threshold %.1f%% — falling back",
            coverage * 100.0,
            _GROUND_COVERAGE_THRESHOLD * 100.0,
        )
        return None

    # Nearest-neighbour fill on empty cells. distance_transform_edt with
    # return_indices gives us, per pixel, the (row, col) of the nearest
    # non-empty cell — a fast Voronoi fill without interpolation artefacts.
    if not np.all(populated):
        _, (nearest_r, nearest_c) = distance_transform_edt(
            ~populated, return_indices=True,
        )
        dtm = min_z[nearest_r, nearest_c]
    else:
        dtm = min_z.copy()

    return dtm.astype(np.float64), coverage


def estimate_dtm(
    dsm_path: Path,
    output_path: Path,
    config: ProcessingConfig,
    ground_regions: list[tuple[float, ...]] | None = None,
    manual_base_elevation: float | None = None,
    las_path: Path | None = None,
    progress_callback: Callable[[int, str], None] | None = None,
) -> DtmResult:
    """Estimate DTM (Digital Terrain Model) from DSM.

    Args:
        dsm_path: Path to the input DSM GeoTIFF.
        output_path: Path for the output DTM GeoTIFF.
        config: Processing configuration.
        ground_regions: Optional list of polygon coordinates for terrain sampling.
        manual_base_elevation: Optional manual elevation override.
        las_path: Optional LAS file. When provided and the file carries ASPRS
            ground classification with sufficient coverage, the DTM is built
            from those points (far more accurate on industrial sites than
            morphological opening). Falls through silently if unavailable.
        progress_callback: Optional callback(percent, message).

    Returns:
        DtmResult with output path, method, elevation, confidence, notes.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    def _progress(pct: int, msg: str) -> None:
        if progress_callback is not None:
            progress_callback(pct, msg)

    # --- Read DSM ---
    _progress(5, "Lettura DSM...")
    with rasterio.open(str(dsm_path)) as ds:
        dsm = ds.read(1).astype(np.float64)
        dsm_profile = ds.profile.copy()
        dsm_transform = ds.transform
        nodata = ds.nodata

    # Replace nodata with NaN for processing
    if nodata is not None:
        dsm[dsm == nodata] = np.nan

    height, width = dsm.shape

    # --- Strategy 1: Manual ---
    if manual_base_elevation is not None:
        _progress(50, "DTM manuale...")
        dtm = np.full_like(dsm, manual_base_elevation, dtype=np.float32)
        _write_dtm(output_path, dtm, dsm_profile)
        _progress(100, "DTM completato (manuale)")
        return DtmResult(
            output_path=output_path,
            method=DtmMethod.MANUAL,
            estimated_base_elevation=manual_base_elevation,
            confidence=1.0,
            notes=f"Quota base impostata manualmente: {manual_base_elevation:.2f} m.",
        )

    # --- Strategy 2: Ground regions ---
    if ground_regions is not None and len(ground_regions) > 0:
        _progress(50, "DTM da regioni terreno...")
        # Sample DSM values within ground region polygons
        # For simplicity, compute mean of DSM in bounding boxes
        z_samples: list[float] = []
        for region in ground_regions:
            # region is a flat tuple of (x1, y1, x2, y2, ...) polygon coords
            # For now, use bounding box approach
            xs = [region[i] for i in range(0, len(region), 2)]
            ys = [region[i] for i in range(1, len(region), 2)]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)

            # Convert to pixel coordinates
            inv_transform = ~dsm_transform
            c1, r1 = inv_transform * (min_x, max_y)
            c2, r2 = inv_transform * (max_x, min_y)
            r_min = max(0, int(min(r1, r2)))
            r_max = min(height, int(max(r1, r2)) + 1)
            c_min = max(0, int(min(c1, c2)))
            c_max = min(width, int(max(c1, c2)) + 1)

            patch = dsm[r_min:r_max, c_min:c_max]
            valid = patch[~np.isnan(patch)]
            if len(valid) > 0:
                z_samples.extend(valid.tolist())

        base_elev = float(np.mean(z_samples)) if len(z_samples) > 0 else float(np.nanmean(dsm))

        dtm = np.full_like(dsm, base_elev, dtype=np.float32)
        _write_dtm(output_path, dtm, dsm_profile)
        _progress(100, "DTM completato (regioni terreno)")
        return DtmResult(
            output_path=output_path,
            method=DtmMethod.GROUND_REGIONS,
            estimated_base_elevation=base_elev,
            confidence=1.0,
            notes=f"Quota base stimata da {len(ground_regions)} regioni terreno: "
            f"{base_elev:.2f} m.",
        )

    # --- Strategy 3: Ground classification from LAS (F2.S10) ---
    if las_path is not None and las_path.exists():
        _progress(15, "Stima DTM da classificazione ground LAS...")
        result = estimate_dtm_from_ground_classification(
            las_path, dsm.shape, dsm_transform,
        )
        if result is not None:
            dtm_ground, coverage = result
            # Restore NaN in cells that were NaN in the DSM (outside survey area).
            dtm_ground = np.where(np.isnan(dsm), np.nan, dtm_ground)

            # Summary scalar: low percentile of the ground raster.
            finite = dtm_ground[np.isfinite(dtm_ground)]
            base_elev = float(np.percentile(finite, config.base_percentile))

            _progress(95, "Scrittura DTM (classificazione ground)...")
            _write_dtm(output_path, dtm_ground.astype(np.float32), dsm_profile)
            _progress(100, "DTM completato (classificazione ground)")
            logger.info(
                "DTM from ASPRS ground classification: coverage=%.1f%%, base=%.2f m",
                coverage * 100.0, base_elev,
            )
            return DtmResult(
                output_path=output_path,
                method=DtmMethod.GROUND_CLASSIFICATION,
                estimated_base_elevation=base_elev,
                confidence=0.95,
                notes=(
                    f"DTM generato da punti classificati come terreno nel LAS "
                    f"(ASPRS class=2, copertura {coverage * 100:.1f}%). "
                    f"Quota base percentile {config.base_percentile}%: {base_elev:.2f} m."
                ),
            )

    # --- Strategy 4: Auto (morphological + peripheral cross-validation) ---
    _progress(20, "Apertura morfologica...")

    # Morphological opening: erosion + dilation removes peaks
    kernel = config.morpho_kernel_size
    dsm_for_morpho = np.where(np.isnan(dsm), 0.0, dsm)
    opened = grey_opening(dsm_for_morpho, size=kernel)

    # Restore NaN positions
    opened[np.isnan(dsm)] = np.nan

    # Morphological estimate: low percentile of opened raster
    morpho_values = opened[~np.isnan(opened)]
    morpho_estimate = float(np.percentile(morpho_values, config.base_percentile))

    _progress(50, "Calcolo percentile periferico...")

    # Peripheral percentile: outer 10% border of DSM
    border_frac = 0.10
    border_px = max(1, int(min(height, width) * border_frac))

    # Create border mask
    border_mask = np.zeros((height, width), dtype=bool)
    border_mask[:border_px, :] = True  # top
    border_mask[-border_px:, :] = True  # bottom
    border_mask[:, :border_px] = True  # left
    border_mask[:, -border_px:] = True  # right

    peripheral_values = dsm[border_mask & ~np.isnan(dsm)]
    if len(peripheral_values) > 0:
        periph_estimate = float(
            np.percentile(peripheral_values, config.base_percentile)
        )
    else:
        periph_estimate = morpho_estimate

    _progress(70, "Cross-validazione...")

    # Cross-validation
    diff = abs(morpho_estimate - periph_estimate)
    logger.debug(
        "DTM estimates: morpho=%.4f, periph=%.4f, diff=%.4f",
        morpho_estimate,
        periph_estimate,
        diff,
    )

    if diff < 0.1:
        confidence = 0.9
        estimated = (morpho_estimate + periph_estimate) / 2.0
        method = DtmMethod.MORPHOLOGICAL
        notes = (
            f"Quota base stimata con metodo morfologico (kernel {kernel}px). "
            f"Morfologico: {morpho_estimate:.3f} m, periferico: {periph_estimate:.3f} m. "
            f"Confidenza alta."
        )
    elif diff < 0.5:
        confidence = 0.7
        estimated = (morpho_estimate + periph_estimate) / 2.0
        method = DtmMethod.MORPHOLOGICAL
        notes = (
            f"Quota base stimata con metodo morfologico (kernel {kernel}px). "
            f"Morfologico: {morpho_estimate:.3f} m, periferico: {periph_estimate:.3f} m. "
            f"Confidenza media — verificare manualmente."
        )
    else:
        confidence = 0.5
        estimated = periph_estimate
        method = DtmMethod.PERCENTILE
        notes = (
            f"Attenzione: metodo morfologico ({morpho_estimate:.3f} m) e periferico "
            f"({periph_estimate:.3f} m) non concordano (diff={diff:.3f} m). "
            f"Usato valore periferico. Verificare e correggere manualmente."
        )

    _progress(80, "Scrittura DTM...")

    # DTM raster: use morphological opening result (spatially varying)
    dtm = opened.astype(np.float32)

    _write_dtm(output_path, dtm, dsm_profile)

    _progress(100, "DTM completato")
    logger.debug(
        "DTM: estimated_base=%.4f, method=%s, confidence=%.2f",
        estimated,
        method.value,
        confidence,
    )

    return DtmResult(
        output_path=output_path,
        method=method,
        estimated_base_elevation=estimated,
        confidence=confidence,
        notes=notes,
    )


def _write_dtm(
    output_path: Path,
    dtm: np.ndarray,
    profile: dict,  # type: ignore[type-arg]
) -> None:
    """Write DTM raster to GeoTIFF."""
    nodata = -9999.0
    dtm_out = np.where(np.isnan(dtm), nodata, dtm).astype(np.float32)

    profile.update(
        dtype=np.float32,
        count=1,
        nodata=nodata,
    )

    with rasterio.open(str(output_path), "w", **profile) as dst:
        dst.write(dtm_out, 1)
