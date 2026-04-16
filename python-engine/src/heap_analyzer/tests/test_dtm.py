"""Tests for DTM estimation."""

import json
from pathlib import Path

import numpy as np
import pytest
import rasterio

from heap_analyzer.config import ProcessingConfig
from heap_analyzer.processing.dtm import DtmMethod, DtmResult, estimate_dtm

TEST_DATA_DIR = Path(__file__).resolve().parents[4] / "test-data"
DSM_PATH = TEST_DATA_DIR / "output" / "dsm.tif"
GT_PATH = TEST_DATA_DIR / "ground_truth.json"
OUTPUT_DIR = TEST_DATA_DIR / "output"


@pytest.fixture(scope="module")
def ground_truth() -> dict:
    return json.loads(GT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def dtm_result_auto() -> DtmResult:
    """Run DTM estimation once for the module."""
    out = OUTPUT_DIR / "dtm.tif"
    config = ProcessingConfig()
    return estimate_dtm(dsm_path=DSM_PATH, output_path=out, config=config)


class TestDtmAuto:
    """Auto mode DTM estimation tests."""

    def test_dtm_auto_synthetic(
        self, dtm_result_auto: DtmResult, ground_truth: dict
    ) -> None:
        expected = ground_truth["terrain_elevation"]
        actual = dtm_result_auto.estimated_base_elevation
        error = abs(actual - expected)
        assert error < 0.05, (
            f"Expected {expected:.4f}m, got {actual:.4f}m, "
            f"error {error*100:.2f}cm exceeds 5cm"
        )

    def test_dtm_method_morphological(self, dtm_result_auto: DtmResult) -> None:
        assert dtm_result_auto.method in (
            DtmMethod.MORPHOLOGICAL,
            DtmMethod.PERCENTILE,
        )

    def test_dtm_confidence_high_on_synthetic(
        self, dtm_result_auto: DtmResult
    ) -> None:
        assert dtm_result_auto.confidence >= 0.7

    def test_dtm_dimensions_match_dsm(self, dtm_result_auto: DtmResult) -> None:
        with rasterio.open(str(DSM_PATH)) as ds_dsm:
            dsm_w, dsm_h = ds_dsm.width, ds_dsm.height
        with rasterio.open(str(dtm_result_auto.output_path)) as ds_dtm:
            assert ds_dtm.width == dsm_w
            assert ds_dtm.height == dsm_h

    def test_dtm_crs_preserved(self, dtm_result_auto: DtmResult) -> None:
        with rasterio.open(str(DSM_PATH)) as ds_dsm:
            dsm_crs = str(ds_dsm.crs)
        with rasterio.open(str(dtm_result_auto.output_path)) as ds_dtm:
            assert str(ds_dtm.crs) == dsm_crs

    def test_dtm_no_negative_volumes(self, dtm_result_auto: DtmResult) -> None:
        """DTM <= DSM everywhere (within numerical noise)."""
        with rasterio.open(str(DSM_PATH)) as ds:
            dsm = ds.read(1).astype(np.float64)
        with rasterio.open(str(dtm_result_auto.output_path)) as ds:
            dtm = ds.read(1).astype(np.float64)

        # Replace nodata
        dsm[dsm < -9000] = np.nan
        dtm[dtm < -9000] = np.nan

        diff = dtm - dsm
        valid = diff[~np.isnan(diff)]
        # DTM should not exceed DSM by more than 0.01m (numerical noise)
        assert np.max(valid) < 0.01, (
            f"DTM exceeds DSM by {np.max(valid):.4f}m"
        )


class TestDtmManual:
    """Manual elevation mode tests."""

    def test_dtm_manual_elevation(self) -> None:
        out = OUTPUT_DIR / "dtm_manual_test.tif"
        result = estimate_dtm(
            dsm_path=DSM_PATH,
            output_path=out,
            config=ProcessingConfig(),
            manual_base_elevation=100.0,
        )
        assert result.method == DtmMethod.MANUAL
        assert result.confidence == 1.0
        assert result.estimated_base_elevation == 100.0

        # Verify raster is constant
        with rasterio.open(str(out)) as ds:
            arr = ds.read(1)
            valid = arr[arr > -9000]
            assert np.allclose(valid, 100.0, atol=0.001)

        out.unlink(missing_ok=True)


class TestDtmGroundRegions:
    """Ground regions mode tests."""

    def test_dtm_ground_regions(self, ground_truth: dict) -> None:
        out = OUTPUT_DIR / "dtm_ground_test.tif"
        gt_b = ground_truth["bounds"]
        # Define a polygon over flat terrain (corner, away from heaps)
        # Use (x1, y1, x2, y2, x3, y3, x4, y4) format
        region = (
            gt_b["min_e"] + 1.0, gt_b["min_n"] + 1.0,
            gt_b["min_e"] + 20.0, gt_b["min_n"] + 1.0,
            gt_b["min_e"] + 20.0, gt_b["min_n"] + 20.0,
            gt_b["min_e"] + 1.0, gt_b["min_n"] + 20.0,
        )
        result = estimate_dtm(
            dsm_path=DSM_PATH,
            output_path=out,
            config=ProcessingConfig(),
            ground_regions=[region],
        )
        assert result.method == DtmMethod.GROUND_REGIONS
        assert result.confidence == 1.0
        assert abs(result.estimated_base_elevation - 100.0) < 0.1

        out.unlink(missing_ok=True)


class TestDtmKernelSensitivity:
    """Verify kernel size sensitivity."""

    def test_dtm_kernel_sensitivity(self, ground_truth: dict) -> None:
        expected = ground_truth["terrain_elevation"]
        results: dict[int, float] = {}

        for kernel in [10, 50, 200]:
            out = OUTPUT_DIR / f"dtm_kernel_{kernel}.tif"
            config = ProcessingConfig(morpho_kernel_size=kernel)
            result = estimate_dtm(
                dsm_path=DSM_PATH, output_path=out, config=config
            )
            results[kernel] = abs(result.estimated_base_elevation - expected)
            out.unlink(missing_ok=True)

        # kernel=50 should give a good result
        assert results[50] < 0.05, (
            f"kernel=50 error {results[50]*100:.2f}cm exceeds 5cm"
        )
