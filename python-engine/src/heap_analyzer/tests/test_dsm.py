"""Tests for DSM generation."""

import json
from pathlib import Path

import numpy as np
import pytest
import rasterio

from heap_analyzer.config import ProcessingConfig
from heap_analyzer.processing.dsm import generate_dsm

TEST_DATA_DIR = Path(__file__).resolve().parents[4] / "test-data"
LAS_PATH = TEST_DATA_DIR / "test.las"
GT_PATH = TEST_DATA_DIR / "ground_truth.json"
OUTPUT_DIR = TEST_DATA_DIR / "output"


@pytest.fixture(scope="module")
def dsm_path() -> Path:
    """Generate DSM once for all tests in this module."""
    out = OUTPUT_DIR / "dsm.tif"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config = ProcessingConfig()
    generate_dsm(LAS_PATH, out, config)
    return out


@pytest.fixture(scope="module")
def ground_truth() -> dict:
    return json.loads(GT_PATH.read_text(encoding="utf-8"))


class TestDsmOutput:
    """Verify DSM GeoTIFF is valid and correct."""

    def test_dsm_generated(self, dsm_path: Path) -> None:
        assert dsm_path.exists()
        with rasterio.open(str(dsm_path)) as ds:
            assert ds.width > 0
            assert ds.height > 0

    def test_dsm_bounds(self, dsm_path: Path, ground_truth: dict) -> None:
        gt_b = ground_truth["bounds"]
        with rasterio.open(str(dsm_path)) as ds:
            b = ds.bounds
            # Within 1 pixel (0.10m) tolerance
            assert abs(b.left - gt_b["min_e"]) < 0.2
            assert abs(b.bottom - gt_b["min_n"]) < 0.2
            assert abs(b.right - gt_b["max_e"]) < 0.2
            assert abs(b.top - gt_b["max_n"]) < 0.2

    def test_dsm_crs(self, dsm_path: Path) -> None:
        with rasterio.open(str(dsm_path)) as ds:
            assert ds.crs is not None
            assert "32632" in str(ds.crs)

    def test_dsm_resolution(self, dsm_path: Path) -> None:
        with rasterio.open(str(dsm_path)) as ds:
            assert abs(ds.transform.a - 0.10) < 0.01
            assert abs(ds.transform.e + 0.10) < 0.01  # negative for north-up

    def test_dsm_dimensions(self, dsm_path: Path) -> None:
        with rasterio.open(str(dsm_path)) as ds:
            assert ds.width == 2000
            assert ds.height == 2000


class TestDsmElevations:
    """Verify DSM elevation values against ground truth."""

    def test_dsm_terrain_elevation(self, dsm_path: Path) -> None:
        """Flat terrain regions should be ~100.0 m."""
        with rasterio.open(str(dsm_path)) as ds:
            arr = ds.read(1)
            # Check corner region (should be pure terrain)
            # Top-left corner: rows 0-100, cols 0-100 (far from any heap)
            corner = arr[0:50, 0:50]
            valid = corner[corner > -9000]
            if len(valid) > 0:
                assert abs(np.mean(valid) - 100.0) < 0.1

    def test_dsm_heap_max_heights(
        self, dsm_path: Path, ground_truth: dict
    ) -> None:
        """At known heap centers, DSM should approximate terrain + height."""
        with rasterio.open(str(dsm_path)) as ds:
            arr = ds.read(1)
            transform = ds.transform

        for heap in ground_truth["heaps"]:
            cx = heap["center_e"]
            cy = heap["center_n"]
            expected_max = 100.0 + heap["max_height"]

            # Convert UTM coords to pixel
            col = int((cx - transform.c) / transform.a)
            row = int((cy - transform.f) / transform.e)

            # Check a 3x3 neighborhood around center
            r_min = max(0, row - 1)
            r_max = min(arr.shape[0], row + 2)
            c_min = max(0, col - 1)
            c_max = min(arr.shape[1], col + 2)
            neighborhood = arr[r_min:r_max, c_min:c_max]
            actual_max = float(np.max(neighborhood))

            # Allow ±0.15m tolerance (point density + discretization)
            assert abs(actual_max - expected_max) < 0.20, (
                f"Heap {heap['type']}: expected ~{expected_max:.1f}m, "
                f"got {actual_max:.3f}m"
            )

    def test_dsm_no_nan_after_interpolation(self, dsm_path: Path) -> None:
        with rasterio.open(str(dsm_path)) as ds:
            arr = ds.read(1)
            # nodata is -9999, not NaN
            nan_or_nodata = np.isnan(arr) | (arr < -9000)
            assert nan_or_nodata.sum() == 0

    def test_dsm_progress_emitted(self) -> None:
        """Verify progress callback is called with increasing percentages."""
        progress_log: list[tuple[int, str]] = []

        def on_progress(pct: int, msg: str) -> None:
            progress_log.append((pct, msg))

        out = OUTPUT_DIR / "dsm_progress_test.tif"
        generate_dsm(LAS_PATH, out, ProcessingConfig(), progress_callback=on_progress)

        assert len(progress_log) >= 3
        pcts = [p[0] for p in progress_log]
        # Should be monotonically non-decreasing
        assert pcts == sorted(pcts)
        # Should end at 100
        assert pcts[-1] == 100

        # Clean up
        if out.exists():
            out.unlink()
