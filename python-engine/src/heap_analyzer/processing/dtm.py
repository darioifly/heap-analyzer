"""DTM (Digital Terrain Model) estimation from DSM.

Strategy decision tree (Sequential Thinking — planned before implementation):

1. Manual mode: user provides base elevation → flat DTM at that Z.
   Confidence = 1.0.

2. Ground regions mode: user provides polygons over known terrain →
   mean DSM Z in those polygons → flat DTM.
   Confidence = 1.0.

3. Auto mode (default):
   a. Morphological opening: scipy.ndimage.grey_opening removes peaks
      shorter than kernel. The opened raster approximates the terrain.
   b. Peripheral percentile: outer 10% border of DSM → low percentile
      (5th by default). Cross-validation against morphological result.
   c. Confidence scoring:
      - |morpho - periph| < 0.1m → 0.9 (high)
      - |morpho - periph| < 0.5m → 0.7 (medium)
      - Otherwise → 0.5, prefer peripheral, emit warning

The DTM raster output is the morphological opening result (spatially varying),
which preserves gentle terrain slopes. The estimated_base_elevation scalar
is the low percentile of this raster.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from pathlib import Path

import numpy as np
import rasterio
from pydantic import BaseModel
from scipy.ndimage import grey_opening

from heap_analyzer.config import ProcessingConfig
from heap_analyzer.utils.logging import get_stderr_logger

logger = get_stderr_logger(__name__)


class DtmMethod(StrEnum):
    """DTM estimation method used."""

    MORPHOLOGICAL = "morphological"
    PERCENTILE = "percentile"
    GROUND_REGIONS = "ground_regions"
    MANUAL = "manual"


class DtmResult(BaseModel):
    """Result of DTM estimation."""

    output_path: Path
    method: DtmMethod
    estimated_base_elevation: float
    confidence: float
    notes: str


def estimate_dtm(
    dsm_path: Path,
    output_path: Path,
    config: ProcessingConfig,
    ground_regions: list[tuple[float, ...]] | None = None,
    manual_base_elevation: float | None = None,
    progress_callback: Callable[[int, str], None] | None = None,
) -> DtmResult:
    """Estimate DTM (Digital Terrain Model) from DSM.

    Args:
        dsm_path: Path to the input DSM GeoTIFF.
        output_path: Path for the output DTM GeoTIFF.
        config: Processing configuration.
        ground_regions: Optional list of polygon coordinates for terrain sampling.
        manual_base_elevation: Optional manual elevation override.
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

    # --- Strategy 3: Auto (morphological + peripheral cross-validation) ---
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
