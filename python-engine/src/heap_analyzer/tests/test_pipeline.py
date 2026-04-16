"""Tests for the integrated processing pipeline."""

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from heap_analyzer.config import ProcessingConfig
from heap_analyzer.pipeline import PipelineResult, ProcessingPipeline

# ---------------------------------------------------------------------------
# Test data paths
# ---------------------------------------------------------------------------

TEST_DATA_DIR = Path(__file__).resolve().parents[4] / "test-data"
GT_PATH = TEST_DATA_DIR / "ground_truth.json"


@pytest.fixture(scope="module")
def ground_truth() -> dict:
    """Load ground truth data."""
    return json.loads(GT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def pipeline_result() -> PipelineResult:
    """Run full pipeline on synthetic data."""
    config = ProcessingConfig()
    pipeline = ProcessingPipeline(config)
    output_dir = TEST_DATA_DIR / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    return pipeline.run(
        las_path=TEST_DATA_DIR / "test.las",
        tiff_path=TEST_DATA_DIR / "test.tif",
        output_dir=output_dir,
    )


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


class TestValidation:
    def test_validate_synthetic(self) -> None:
        """Returns no errors for valid synthetic inputs."""
        pipeline = ProcessingPipeline()
        errors = pipeline.validate_inputs(
            TEST_DATA_DIR / "test.las", TEST_DATA_DIR / "test.tif",
        )
        assert errors == [], f"Unexpected validation errors: {errors}"

    def test_validate_missing_las(self) -> None:
        """Returns error for non-existent LAS."""
        pipeline = ProcessingPipeline()
        errors = pipeline.validate_inputs(
            Path("/nonexistent/file.las"), TEST_DATA_DIR / "test.tif",
        )
        assert len(errors) >= 1
        assert any("LAS" in e for e in errors)

    def test_validate_crs_mismatch(self, tmp_path: Path) -> None:
        """Returns error for mismatched CRS files."""
        # Create a temp TIFF in EPSG:4326
        bad_tiff = tmp_path / "bad_crs.tif"
        data = np.ones((10, 10), dtype=np.float32)
        transform = from_origin(0, 1, 0.1, 0.1)

        with rasterio.open(
            str(bad_tiff), "w", driver="GTiff",
            height=10, width=10, count=3, dtype=np.uint8,
            crs="EPSG:4326", transform=transform,
        ) as dst:
            for i in range(3):
                dst.write(np.ones((10, 10), dtype=np.uint8) * 128, i + 1)

        pipeline = ProcessingPipeline()
        errors = pipeline.validate_inputs(TEST_DATA_DIR / "test.las", bad_tiff)
        assert len(errors) >= 1
        assert any("CRS" in e for e in errors)


# ---------------------------------------------------------------------------
# Pipeline run tests
# ---------------------------------------------------------------------------


class TestPipelineRun:
    def test_pipeline_run_synthetic_end_to_end(
        self, pipeline_result: PipelineResult, ground_truth: dict
    ) -> None:
        """Pipeline returns 4 heaps, total volume within 5%."""
        assert len(pipeline_result.heap_metrics) == 4

        expected_total = sum(h["volume_m3"] for h in ground_truth["heaps"])
        got_total = sum(m.volume_m3 for m in pipeline_result.heap_metrics)
        error_pct = abs(got_total - expected_total) / expected_total * 100
        assert error_pct < 5.0, (
            f"Total volume error {error_pct:.2f}%: got {got_total:.1f}, "
            f"expected {expected_total:.1f}"
        )

    def test_pipeline_intermediate_files_exist(
        self, pipeline_result: PipelineResult
    ) -> None:
        """DSM, DTM, nDSM, label_map all exist after run."""
        for name in ["dsm", "dtm", "ndsm", "label_map"]:
            path = pipeline_result.intermediate_files[name]
            assert Path(path).exists(), f"Intermediate file {name} missing: {path}"

    def test_pipeline_results_json_saved(
        self, pipeline_result: PipelineResult
    ) -> None:
        """results.json exists, parses, contains heap_metrics."""
        output_dir = Path(pipeline_result.survey_metadata["output_dir"])
        results_path = output_dir / "results.json"
        assert results_path.exists()

        data = json.loads(results_path.read_text(encoding="utf-8"))
        assert "heap_metrics" in data
        assert len(data["heap_metrics"]) == 4

    def test_pipeline_progress_monotonic(self) -> None:
        """Progress percents are monotonically non-decreasing."""
        config = ProcessingConfig()
        pipeline = ProcessingPipeline(config)
        output_dir = TEST_DATA_DIR / "output"

        progress_calls: list[tuple[int, str]] = []

        def on_progress(pct: int, msg: str) -> None:
            progress_calls.append((pct, msg))

        pipeline.run(
            TEST_DATA_DIR / "test.las",
            TEST_DATA_DIR / "test.tif",
            output_dir,
            progress_callback=on_progress,
        )

        pcts = [p[0] for p in progress_calls]
        for i in range(1, len(pcts)):
            assert pcts[i] >= pcts[i - 1], (
                f"Progress not monotonic: {pcts[i-1]} -> {pcts[i]} "
                f"at step {i}: {progress_calls[i][1]}"
            )

    def test_pipeline_progress_reaches_100(self) -> None:
        """Final progress hits 100."""
        config = ProcessingConfig()
        pipeline = ProcessingPipeline(config)
        output_dir = TEST_DATA_DIR / "output"

        progress_calls: list[tuple[int, str]] = []

        def on_progress(pct: int, msg: str) -> None:
            progress_calls.append((pct, msg))

        pipeline.run(
            TEST_DATA_DIR / "test.las",
            TEST_DATA_DIR / "test.tif",
            output_dir,
            progress_callback=on_progress,
        )

        assert progress_calls[-1][0] == 100

    def test_pipeline_custom_config(self) -> None:
        """Pass custom ProcessingConfig -> still works."""
        config = ProcessingConfig(height_threshold=0.3)
        pipeline = ProcessingPipeline(config)
        output_dir = TEST_DATA_DIR / "output"

        result = pipeline.run(
            TEST_DATA_DIR / "test.las",
            TEST_DATA_DIR / "test.tif",
            output_dir,
        )
        assert len(result.heap_metrics) >= 4
