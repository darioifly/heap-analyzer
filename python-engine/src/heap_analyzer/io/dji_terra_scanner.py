"""Scan a DJI Terra output folder and build a manifest of its assets.

DJI Terra produces a well-known folder layout with orthophoto, DSM, LAS point
cloud (classified via ASPRS codes) and metadata. This module discovers the
relevant files, extracts CRS/date/bbox, and reports whether the LAS already
contains ground classification (enabling a much better DTM than morphological
opening on an industrial site).

The companion ``task.json`` in ``map/`` is **encrypted** by DJI (hex blob, not
plain JSON) and is intentionally ignored. CRS comes from the ``.prj`` sidecars
(WKT) with fallback to the LAS VLR. Survey date comes from file mtime with
optional user override in the UI.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import laspy
import numpy as np
import rasterio
from pydantic import BaseModel

from heap_analyzer.utils.logging import get_stderr_logger

logger = get_stderr_logger(__name__)


# Canonical asset locations inside a DJI Terra root folder.
_DSM_PRIMARY = ("map", "dsm.tif")
_DSM_FALLBACK = ("models", "pc", "0", "terra_dem", "dem.tif")
_ORTHO = ("map", "result.tif")
_LAS = ("models", "pc", "0", "terra_las", "cloud_merged.las")
_PIPELINE_SENTINEL = ("map", "2dPipeline_done")

# Only sample a small prefix when probing classification so large clouds
# (1-2 GB) don't cost seconds; 100k is enough to tell if class==2 is populated.
_CLASSIFICATION_SAMPLE_SIZE = 100_000


class DJITerraIncompleteError(Exception):
    """Raised when a required DJI Terra asset is missing from the folder."""


class DJITerraManifest(BaseModel):
    """Discovered assets + metadata for a DJI Terra folder."""

    orthophoto_path: Path
    dsm_path: Path
    las_path: Path
    crs: str | None = None
    survey_date: date | None = None
    bbox: tuple[float, float, float, float] | None = None
    has_ground_classification: bool = False
    pipeline_complete: bool = True
    warnings: list[str] = []


def scan_dji_terra_folder(folder: Path) -> DJITerraManifest:
    """Scan a DJI Terra output folder and return a populated manifest.

    Args:
        folder: Path to the DJI Terra root (contains ``map/`` and ``models/``).

    Returns:
        A :class:`DJITerraManifest` with discovered paths and extracted metadata.

    Raises:
        FileNotFoundError: If ``folder`` does not exist or is not a directory.
        DJITerraIncompleteError: If orthophoto, LAS, or any DSM source is missing.
    """
    if not folder.exists():
        raise FileNotFoundError(f"Cartella DJI Terra non trovata: {folder}")
    if not folder.is_dir():
        raise FileNotFoundError(f"Il percorso non è una cartella: {folder}")

    warnings: list[str] = []

    # --- DSM: prefer map/dsm.tif, fall back to terra_dem/dem.tif ---
    dsm_path = folder.joinpath(*_DSM_PRIMARY)
    dsm_fallback = folder.joinpath(*_DSM_FALLBACK)
    if dsm_path.exists():
        logger.debug("DSM found at primary location: %s", dsm_path)
    elif dsm_fallback.exists():
        logger.debug("Using DSM fallback: %s", dsm_fallback)
        warnings.append(
            "DSM preferito map/dsm.tif assente — uso fallback terra_dem/dem.tif"
        )
        dsm_path = dsm_fallback
    else:
        raise DJITerraIncompleteError(
            "DSM non trovato. Cercato map/dsm.tif e models/pc/0/terra_dem/dem.tif."
        )

    # --- Orthophoto ---
    ortho_path = folder.joinpath(*_ORTHO)
    if not ortho_path.exists():
        raise DJITerraIncompleteError(
            "Ortofoto non trovata. Atteso: map/result.tif"
        )

    # --- LAS point cloud ---
    las_path = folder.joinpath(*_LAS)
    if not las_path.exists():
        raise DJITerraIncompleteError(
            "Nuvola di punti non trovata. Atteso: "
            "models/pc/0/terra_las/cloud_merged.las"
        )

    # --- Pipeline sentinel ---
    pipeline_complete = folder.joinpath(*_PIPELINE_SENTINEL).exists()
    if not pipeline_complete:
        warnings.append(
            "Sentinel map/2dPipeline_done assente — la pipeline DJI Terra "
            "potrebbe non essere terminata correttamente."
        )

    # --- CRS: .prj of DSM → .prj of orthophoto → LAS VLR ---
    crs = _extract_crs(dsm_path, ortho_path, las_path, warnings)

    # --- BBox from DSM raster ---
    bbox = _read_dsm_bbox(dsm_path, warnings)

    # --- Ground classification probe on first chunk ---
    has_ground = _probe_ground_classification(las_path, warnings)

    # --- Survey date: earliest mtime among LAS/DSM/ortho as best proxy ---
    survey_date = _infer_survey_date(las_path, dsm_path, ortho_path)

    return DJITerraManifest(
        orthophoto_path=ortho_path,
        dsm_path=dsm_path,
        las_path=las_path,
        crs=crs,
        survey_date=survey_date,
        bbox=bbox,
        has_ground_classification=has_ground,
        pipeline_complete=pipeline_complete,
        warnings=warnings,
    )


def _extract_crs(
    dsm_path: Path,
    ortho_path: Path,
    las_path: Path,
    warnings: list[str],
) -> str | None:
    """Try each CRS source in priority order, returning 'EPSG:<code>' or None."""
    # 1. DSM .prj (WKT sidecar)
    dsm_prj = dsm_path.with_suffix(".prj")
    epsg = _epsg_from_prj(dsm_prj)
    if epsg:
        return epsg

    # 2. Ortho .prj
    ortho_prj = ortho_path.with_suffix(".prj")
    epsg = _epsg_from_prj(ortho_prj)
    if epsg:
        return epsg

    # 3. DSM via rasterio (GeoTIFF tags)
    try:
        with rasterio.open(str(dsm_path)) as ds:
            if ds.crs is not None:
                code = ds.crs.to_epsg()
                if code is not None:
                    return f"EPSG:{code}"
    except (rasterio.errors.RasterioIOError, ValueError) as exc:
        logger.debug("CRS from DSM raster failed: %s", exc)

    # 4. LAS VLR
    try:
        with laspy.open(str(las_path)) as reader:
            parsed = reader.header.parse_crs()
            if parsed is not None:
                code = parsed.to_epsg()
                if code is not None:
                    return f"EPSG:{code}"
    except Exception as exc:  # noqa: BLE001
        logger.debug("CRS from LAS VLR failed: %s", exc)

    warnings.append("CRS non rilevabile dai metadati (prj/GeoTIFF/LAS)")
    return None


def _epsg_from_prj(prj_path: Path) -> str | None:
    """Parse a .prj WKT file and extract EPSG:<code> if present."""
    if not prj_path.exists():
        return None
    try:
        import pyproj

        wkt = prj_path.read_text(encoding="utf-8", errors="replace")
        crs = pyproj.CRS.from_wkt(wkt)
        code = crs.to_epsg()
        if code is not None:
            return f"EPSG:{code}"
    except (OSError, ValueError, pyproj.exceptions.CRSError) as exc:
        logger.debug("Failed to parse %s: %s", prj_path, exc)
    return None


def _read_dsm_bbox(
    dsm_path: Path, warnings: list[str]
) -> tuple[float, float, float, float] | None:
    """Return (min_e, min_n, max_e, max_n) from the DSM's geospatial extent."""
    try:
        with rasterio.open(str(dsm_path)) as ds:
            b = ds.bounds
            return (float(b.left), float(b.bottom), float(b.right), float(b.top))
    except (rasterio.errors.RasterioIOError, ValueError) as exc:
        warnings.append(f"BBox DSM non leggibile: {exc}")
        return None


def _probe_ground_classification(las_path: Path, warnings: list[str]) -> bool:
    """Return True if at least one point in the first sampled chunk is class==2."""
    try:
        with laspy.open(str(las_path)) as reader:
            dim_names = [d.name for d in reader.header.point_format.dimensions]
            if "classification" not in dim_names:
                warnings.append("LAS senza campo 'classification'")
                return False

            try:
                chunk = next(reader.chunk_iterator(_CLASSIFICATION_SAMPLE_SIZE))
            except StopIteration:
                warnings.append("LAS vuoto (nessun punto)")
                return False

            cls = np.asarray(chunk.classification, dtype=np.uint8)
            ground_count = int(np.sum(cls == 2))
            logger.debug(
                "Classification sample: %d / %d points are class=2 (%.1f%%)",
                ground_count,
                len(cls),
                100.0 * ground_count / max(len(cls), 1),
            )
            return ground_count > 0
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Probe classificazione fallito: {exc}")
        return False


def _infer_survey_date(*paths: Path) -> date | None:
    """Pick the earliest existing mtime across paths as survey date proxy."""
    candidates = [p for p in paths if p.exists()]
    if not candidates:
        return None
    mtimes = [p.stat().st_mtime for p in candidates]
    earliest = min(mtimes)
    try:
        return datetime.fromtimestamp(earliest, tz=UTC).date()
    except (OSError, ValueError):
        return None
