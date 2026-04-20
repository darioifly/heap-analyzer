"""Tests for the ASPRS ground-classification DTM strategy (F2.S10)."""

from __future__ import annotations

from pathlib import Path

import laspy
import numpy as np
import rasterio
from rasterio.transform import from_origin

from heap_analyzer.config import ProcessingConfig
from heap_analyzer.processing.dtm import (
    DtmMethod,
    estimate_dtm,
    estimate_dtm_from_ground_classification,
)

# ---------------------------------------------------------------------------
# Helpers — synthetic LAS and DSM fabricators
# ---------------------------------------------------------------------------


def _write_synthetic_dsm(
    path: Path,
    width: int = 50,
    height: int = 50,
    origin_e: float = 500_000.0,
    origin_n: float = 5_000_000.0,
    resolution: float = 1.0,
    base_z: float = 100.0,
    heap_height: float = 5.0,
) -> None:
    """Create a small synthetic DSM: flat terrain with one central heap."""
    dsm = np.full((height, width), base_z, dtype=np.float32)
    # Central 10x10 mound
    cy, cx = height // 2, width // 2
    dsm[cy - 5 : cy + 5, cx - 5 : cx + 5] = base_z + heap_height

    transform = from_origin(origin_e, origin_n, resolution, resolution)
    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": "float32",
        "crs": "EPSG:32632",
        "transform": transform,
        "nodata": -9999.0,
    }
    with rasterio.open(str(path), "w", **profile) as dst:
        dst.write(dsm, 1)


def _write_synthetic_las(
    path: Path,
    dsm_path: Path,
    *,
    ground_fraction: float = 0.9,
    add_classification_field: bool = True,
) -> None:
    """Create a LAS with points sampled on the DSM surface.

    When ``add_classification_field`` is True (the common case for drone
    surveys) a fraction ``ground_fraction`` of points are tagged ASPRS
    class=2 on the flat terrain — the central heap stays class=1.
    """
    with rasterio.open(str(dsm_path)) as ds:
        dsm = ds.read(1)
        transform = ds.transform
        height, width = dsm.shape

    # Dense grid: one point every cell (cheap and deterministic).
    rows, cols = np.indices((height, width))
    xs, ys = rasterio.transform.xy(transform, rows.flatten(), cols.flatten())
    xs_a = np.asarray(xs, dtype=np.float64)
    ys_a = np.asarray(ys, dtype=np.float64)
    zs_a = dsm.flatten().astype(np.float64)

    # Identify "flat terrain" cells (z at the base elevation, lowest values).
    base_z = float(np.min(zs_a))
    is_flat = zs_a <= base_z + 0.01

    # Random subsample of flat-terrain points get classified as ground.
    rng = np.random.default_rng(42)
    flat_idx = np.where(is_flat)[0]
    n_ground = int(len(flat_idx) * ground_fraction)
    ground_indices = set(rng.choice(flat_idx, size=n_ground, replace=False).tolist())

    classification = np.ones(len(zs_a), dtype=np.uint8)  # class=1 everywhere
    if add_classification_field:
        for i in ground_indices:
            classification[i] = 2

    header = laspy.LasHeader(point_format=3, version="1.4")
    header.offsets = np.array([xs_a.min(), ys_a.min(), zs_a.min()])
    header.scales = np.array([0.001, 0.001, 0.001])
    las = laspy.LasData(header)
    las.x = xs_a
    las.y = ys_a
    las.z = zs_a
    if add_classification_field:
        las.classification = classification
    las.write(str(path))


# ---------------------------------------------------------------------------
# estimate_dtm_from_ground_classification — direct unit tests
# ---------------------------------------------------------------------------


def test_ground_classification_builds_correct_dtm(tmp_path: Path) -> None:
    """A LAS with ample class=2 points produces a DTM close to the true base."""
    dsm_path = tmp_path / "dsm.tif"
    las_path = tmp_path / "cloud.las"
    _write_synthetic_dsm(dsm_path, base_z=100.0, heap_height=5.0)
    _write_synthetic_las(las_path, dsm_path, ground_fraction=0.9)

    with rasterio.open(str(dsm_path)) as ds:
        shape = ds.read(1).shape
        transform = ds.transform

    result = estimate_dtm_from_ground_classification(las_path, shape, transform)

    assert result is not None
    dtm, coverage = result
    assert dtm.shape == shape
    assert coverage > 0.5, f"Expected high coverage, got {coverage:.2%}"

    # DTM should be near the true ground elevation (100.0) everywhere, because
    # even cells covered by the heap get filled with nearest-neighbour ground.
    valid = dtm[np.isfinite(dtm)]
    assert abs(float(np.median(valid)) - 100.0) < 0.5


def test_ground_classification_returns_none_without_classification(tmp_path: Path) -> None:
    """LAS point format without classification → returns None."""
    dsm_path = tmp_path / "dsm.tif"
    las_path = tmp_path / "cloud.las"
    _write_synthetic_dsm(dsm_path)

    # Point format 0 has classification too; use point format 0 with all class=0
    # cannot easily strip the dim. Instead we create points where zero are class 2.
    _write_synthetic_las(las_path, dsm_path, ground_fraction=0.0)

    with rasterio.open(str(dsm_path)) as ds:
        shape = ds.read(1).shape
        transform = ds.transform

    result = estimate_dtm_from_ground_classification(las_path, shape, transform)
    # Zero ground points → returns None
    assert result is None


def test_ground_classification_returns_none_when_coverage_below_threshold(
    tmp_path: Path,
) -> None:
    """Coverage < 5% of DSM cells → function returns None to trigger fallback."""
    dsm_path = tmp_path / "dsm.tif"
    las_path = tmp_path / "cloud.las"
    _write_synthetic_dsm(dsm_path, width=100, height=100)

    # Only 0.1% of flat cells become ground — forces below-threshold coverage.
    _write_synthetic_las(las_path, dsm_path, ground_fraction=0.001)

    with rasterio.open(str(dsm_path)) as ds:
        shape = ds.read(1).shape
        transform = ds.transform

    result = estimate_dtm_from_ground_classification(las_path, shape, transform)
    assert result is None


# ---------------------------------------------------------------------------
# estimate_dtm integration — end-to-end with and without LAS
# ---------------------------------------------------------------------------


def test_estimate_dtm_selects_ground_classification_when_available(
    tmp_path: Path,
) -> None:
    """End-to-end: LAS with class=2 → method == GROUND_CLASSIFICATION."""
    dsm_path = tmp_path / "dsm.tif"
    las_path = tmp_path / "cloud.las"
    dtm_path = tmp_path / "dtm.tif"
    _write_synthetic_dsm(dsm_path)
    _write_synthetic_las(las_path, dsm_path, ground_fraction=0.9)

    result = estimate_dtm(
        dsm_path=dsm_path,
        output_path=dtm_path,
        config=ProcessingConfig(),
        las_path=las_path,
    )

    assert result.method == DtmMethod.GROUND_CLASSIFICATION
    assert result.confidence >= 0.9
    assert abs(result.estimated_base_elevation - 100.0) < 0.5
    assert dtm_path.exists()


def test_estimate_dtm_falls_back_when_las_has_no_ground(tmp_path: Path) -> None:
    """LAS with no class=2 points → ground strategy skipped, morphological used."""
    dsm_path = tmp_path / "dsm.tif"
    las_path = tmp_path / "cloud.las"
    dtm_path = tmp_path / "dtm.tif"
    _write_synthetic_dsm(dsm_path)
    _write_synthetic_las(las_path, dsm_path, ground_fraction=0.0)

    result = estimate_dtm(
        dsm_path=dsm_path,
        output_path=dtm_path,
        config=ProcessingConfig(),
        las_path=las_path,
    )

    assert result.method != DtmMethod.GROUND_CLASSIFICATION
    assert result.method in (DtmMethod.MORPHOLOGICAL, DtmMethod.PERCENTILE)


def test_estimate_dtm_ignores_las_when_file_missing(tmp_path: Path) -> None:
    """A non-existent las_path silently falls back — no exception."""
    dsm_path = tmp_path / "dsm.tif"
    dtm_path = tmp_path / "dtm.tif"
    _write_synthetic_dsm(dsm_path)

    result = estimate_dtm(
        dsm_path=dsm_path,
        output_path=dtm_path,
        config=ProcessingConfig(),
        las_path=tmp_path / "does-not-exist.las",
    )

    assert result.method != DtmMethod.GROUND_CLASSIFICATION


def test_estimate_dtm_backward_compatible_without_las(tmp_path: Path) -> None:
    """Calling estimate_dtm without las_path (legacy) still works."""
    dsm_path = tmp_path / "dsm.tif"
    dtm_path = tmp_path / "dtm.tif"
    _write_synthetic_dsm(dsm_path)

    result = estimate_dtm(
        dsm_path=dsm_path,
        output_path=dtm_path,
        config=ProcessingConfig(),
    )

    assert result.method in (DtmMethod.MORPHOLOGICAL, DtmMethod.PERCENTILE)


# ---------------------------------------------------------------------------
# Pipeline — precomputed_dsm_path skips DSM generation
# ---------------------------------------------------------------------------


def test_pipeline_precomputed_dsm_skips_generation(tmp_path: Path) -> None:
    """When config.precomputed_dsm_path is set, the file is copied verbatim
    into the output layout without re-running DSM generation."""
    from heap_analyzer.pipeline import ProcessingPipeline

    # Build: external DSM + minimal LAS + minimal TIFF for the pipeline.
    dsm_source = tmp_path / "precomputed_dsm.tif"
    las_path = tmp_path / "cloud.las"
    tiff_path = tmp_path / "ortho.tif"
    _write_synthetic_dsm(dsm_source, base_z=200.0, heap_height=3.0)
    _write_synthetic_las(las_path, dsm_source, ground_fraction=0.9)

    # Minimal ortho (same grid, 3-band uint8)
    with rasterio.open(str(dsm_source)) as ds:
        transform = ds.transform
        crs = ds.crs
        w, h = ds.width, ds.height
    with rasterio.open(
        str(tiff_path), "w", driver="GTiff",
        height=h, width=w, count=3, dtype=np.uint8,
        crs=crs, transform=transform,
    ) as dst:
        for i in range(3):
            dst.write(np.full((h, w), 128, dtype=np.uint8), i + 1)

    # Instrument DSM generation: if the pipeline tried to regenerate it,
    # the file's first byte would change. We capture the source bytes and
    # compare after run.
    source_bytes = dsm_source.read_bytes()

    output_dir = tmp_path / "out"
    config = ProcessingConfig(precomputed_dsm_path=dsm_source)
    pipeline = ProcessingPipeline(config)

    try:
        pipeline.run(las_path, tiff_path, output_dir)
    except Exception:
        # Pipeline can fail downstream (tiny synthetic DSM) — we only assert
        # the DSM was imported, not that the whole pipeline succeeds.
        pass

    imported_dsm = output_dir / "dsm.tif"
    assert imported_dsm.exists(), "DSM must be copied to output dir"
    assert imported_dsm.read_bytes() == source_bytes, (
        "Pipeline should copy the precomputed DSM verbatim, not regenerate it."
    )
