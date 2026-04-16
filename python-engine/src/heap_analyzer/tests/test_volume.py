"""Tests for volumetric calculation — MOST CRITICAL test file in the project.

Every volume is validated against analytical ground truth.
Tolerances from SPEC.md [PERF].
"""

import json
import re
from pathlib import Path

import numpy as np
import pytest

from heap_analyzer.config import ProcessingConfig
from heap_analyzer.processing.dsm import generate_dsm
from heap_analyzer.processing.dtm import estimate_dtm
from heap_analyzer.processing.segmentation import compute_ndsm, segment_heaps
from heap_analyzer.processing.volume import HeapMetrics, compute_heap_metrics

# ---------------------------------------------------------------------------
# Tolerances from SPEC.md [PERF]
# ---------------------------------------------------------------------------

VOLUME_ERROR_PCT_MAX = 5.0  # < 5% error vs analytical
AREA_ERROR_PCT_MAX = 5.0  # +/-5%
HEIGHT_MAX_ERROR_M = 0.15  # +/-0.15m
CENTROID_ERROR_M_MAX = 2.0  # +/-2m for centroid position

# ---------------------------------------------------------------------------
# Test data paths
# ---------------------------------------------------------------------------

TEST_DATA_DIR = Path(__file__).resolve().parents[4] / "test-data"
OUTPUT_DIR = TEST_DATA_DIR / "output"
GT_PATH = TEST_DATA_DIR / "ground_truth.json"


@pytest.fixture(scope="module")
def ground_truth() -> dict:
    """Load ground truth data."""
    return json.loads(GT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def pipeline_outputs() -> tuple[Path, Path, Path]:
    """Ensure DSM, DTM, nDSM exist."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config = ProcessingConfig()

    dsm_path = OUTPUT_DIR / "dsm.tif"
    if not dsm_path.exists():
        generate_dsm(TEST_DATA_DIR / "test.las", dsm_path, config)

    dtm_path = OUTPUT_DIR / "dtm.tif"
    if not dtm_path.exists():
        estimate_dtm(dsm_path, dtm_path, config)

    ndsm_path = OUTPUT_DIR / "ndsm.tif"
    compute_ndsm(dsm_path, dtm_path, ndsm_path)

    return dsm_path, dtm_path, ndsm_path


@pytest.fixture(scope="module")
def heap_metrics(pipeline_outputs: tuple[Path, Path, Path]) -> list[HeapMetrics]:
    """Run segmentation + volume calculation on synthetic data."""
    _, _, ndsm_path = pipeline_outputs
    config = ProcessingConfig()

    result = segment_heaps(ndsm_path, config)
    accepted = [h for h in result.heaps if not h.is_filtered]

    metrics = compute_heap_metrics(
        ndsm_path, result.label_map_path, accepted, 100.0, config
    )
    return metrics


def _find_match(
    metric: HeapMetrics, gt_heaps: list[dict],
) -> dict:
    """Match a detected heap to ground truth by closest centroid."""
    return min(
        gt_heaps,
        key=lambda g: (
            (g["center_e"] - metric.centroid_e) ** 2
            + (g["center_n"] - metric.centroid_n) ** 2
        ),
    )


# ---------------------------------------------------------------------------
# Metrics count
# ---------------------------------------------------------------------------


class TestMetricsCount:
    def test_metrics_count(self, heap_metrics: list[HeapMetrics]) -> None:
        """4 heaps in -> 4 HeapMetrics out."""
        assert len(heap_metrics) == 4


# ---------------------------------------------------------------------------
# Volume tests — per heap
# ---------------------------------------------------------------------------


class TestVolumes:
    def test_volume_cone(
        self, heap_metrics: list[HeapMetrics], ground_truth: dict
    ) -> None:
        """Cone volume within 5% of analytical (1178.097 m^3)."""
        gt_cone = next(h for h in ground_truth["heaps"] if h["type"] == "cone")
        match = _find_by_type(heap_metrics, ground_truth, "cone")
        error_pct = abs(match.volume_m3 - gt_cone["volume_m3"]) / gt_cone["volume_m3"] * 100
        assert error_pct < VOLUME_ERROR_PCT_MAX, (
            f"Cone volume error {error_pct:.2f}%: got {match.volume_m3:.2f}, "
            f"expected {gt_cone['volume_m3']:.2f}"
        )

    def test_volume_hemisphere(
        self, heap_metrics: list[HeapMetrics], ground_truth: dict
    ) -> None:
        """Hemisphere volume within 5% of analytical (3619.115 m^3)."""
        gt = next(h for h in ground_truth["heaps"] if h["type"] == "hemisphere")
        match = _find_by_type(heap_metrics, ground_truth, "hemisphere")
        error_pct = abs(match.volume_m3 - gt["volume_m3"]) / gt["volume_m3"] * 100
        assert error_pct < VOLUME_ERROR_PCT_MAX, (
            f"Hemisphere volume error {error_pct:.2f}%: got {match.volume_m3:.2f}, "
            f"expected {gt['volume_m3']:.2f}"
        )

    def test_volume_pyramid(
        self, heap_metrics: list[HeapMetrics], ground_truth: dict
    ) -> None:
        """Pyramid volume within 5% of analytical (800.0 m^3)."""
        gt = next(h for h in ground_truth["heaps"] if h["type"] == "pyramid")
        match = _find_by_type(heap_metrics, ground_truth, "pyramid")
        error_pct = abs(match.volume_m3 - gt["volume_m3"]) / gt["volume_m3"] * 100
        assert error_pct < VOLUME_ERROR_PCT_MAX, (
            f"Pyramid volume error {error_pct:.2f}%: got {match.volume_m3:.2f}, "
            f"expected {gt['volume_m3']:.2f}"
        )

    def test_volume_truncated_cone(
        self, heap_metrics: list[HeapMetrics], ground_truth: dict
    ) -> None:
        """Truncated cone volume within 5% of analytical (2228.436 m^3)."""
        gt = next(h for h in ground_truth["heaps"] if h["type"] == "truncated_cone")
        match = _find_by_type(heap_metrics, ground_truth, "truncated_cone")
        error_pct = abs(match.volume_m3 - gt["volume_m3"]) / gt["volume_m3"] * 100
        assert error_pct < VOLUME_ERROR_PCT_MAX, (
            f"Truncated cone volume error {error_pct:.2f}%: got {match.volume_m3:.2f}, "
            f"expected {gt['volume_m3']:.2f}"
        )

    def test_total_volume(
        self, heap_metrics: list[HeapMetrics], ground_truth: dict
    ) -> None:
        """Sum of all volumes within 3% of expected total (7825.6 m^3)."""
        expected_total = sum(h["volume_m3"] for h in ground_truth["heaps"])
        got_total = sum(m.volume_m3 for m in heap_metrics)
        error_pct = abs(got_total - expected_total) / expected_total * 100
        assert error_pct < 3.0, (
            f"Total volume error {error_pct:.2f}%: got {got_total:.2f}, "
            f"expected {expected_total:.2f}"
        )


# ---------------------------------------------------------------------------
# Area tests
# ---------------------------------------------------------------------------


class TestAreas:
    def test_planimetric_area_cone(
        self, heap_metrics: list[HeapMetrics], ground_truth: dict
    ) -> None:
        """Cone area above threshold, within 5% of thresholded analytical."""
        import math

        gt_cone = next(h for h in ground_truth["heaps"] if h["type"] == "cone")
        # Cone with height h and radius R: at height_threshold t,
        # the effective radius is R * (1 - t/h)
        r = gt_cone["radius"]
        h = gt_cone["max_height"]
        t = 0.5  # height_threshold
        r_eff = r * (1.0 - t / h)
        expected = math.pi * r_eff ** 2
        match = _find_by_type(heap_metrics, ground_truth, "cone")
        error_pct = abs(match.planimetric_area_m2 - expected) / expected * 100
        assert error_pct < AREA_ERROR_PCT_MAX, (
            f"Cone area error {error_pct:.2f}%: got {match.planimetric_area_m2:.1f}, "
            f"expected {expected:.1f} (thresholded at {t}m)"
        )

    def test_surface_area_greater_than_planimetric(
        self, heap_metrics: list[HeapMetrics]
    ) -> None:
        """Surface area >= planimetric area for every heap."""
        for m in heap_metrics:
            assert m.surface_area_m2 >= m.planimetric_area_m2, (
                f"Heap {m.heap_id}: surface {m.surface_area_m2:.1f} < "
                f"planimetric {m.planimetric_area_m2:.1f}"
            )


# ---------------------------------------------------------------------------
# Height tests
# ---------------------------------------------------------------------------


class TestHeights:
    def test_max_height_cone(
        self, heap_metrics: list[HeapMetrics], ground_truth: dict
    ) -> None:
        """Cone max_height = 5.0m +/- 0.15m."""
        gt = next(h for h in ground_truth["heaps"] if h["type"] == "cone")
        match = _find_by_type(heap_metrics, ground_truth, "cone")
        assert abs(match.max_height_m - gt["max_height"]) < HEIGHT_MAX_ERROR_M, (
            f"Cone max height error: got {match.max_height_m:.2f}, "
            f"expected {gt['max_height']:.2f}"
        )

    def test_max_height_hemisphere(
        self, heap_metrics: list[HeapMetrics], ground_truth: dict
    ) -> None:
        """Hemisphere max_height = 12.0m +/- 0.15m."""
        gt = next(h for h in ground_truth["heaps"] if h["type"] == "hemisphere")
        match = _find_by_type(heap_metrics, ground_truth, "hemisphere")
        assert abs(match.max_height_m - gt["max_height"]) < HEIGHT_MAX_ERROR_M, (
            f"Hemisphere max height error: got {match.max_height_m:.2f}, "
            f"expected {gt['max_height']:.2f}"
        )


# ---------------------------------------------------------------------------
# Centroid and bbox tests
# ---------------------------------------------------------------------------


class TestCentroids:
    def test_centroid_cone(
        self, heap_metrics: list[HeapMetrics], ground_truth: dict
    ) -> None:
        """Cone centroid within 2m of (500050, 5000050)."""
        gt = next(h for h in ground_truth["heaps"] if h["type"] == "cone")
        match = _find_by_type(heap_metrics, ground_truth, "cone")
        dist = (
            (match.centroid_e - gt["center_e"]) ** 2
            + (match.centroid_n - gt["center_n"]) ** 2
        ) ** 0.5
        assert dist < CENTROID_ERROR_M_MAX, (
            f"Cone centroid distance {dist:.2f}m from expected"
        )

    def test_centroid_all_heaps(
        self, heap_metrics: list[HeapMetrics], ground_truth: dict
    ) -> None:
        """Every centroid within 2m of expected ground truth center."""
        for m in heap_metrics:
            gt_match = _find_match(m, ground_truth["heaps"])
            dist = (
                (m.centroid_e - gt_match["center_e"]) ** 2
                + (m.centroid_n - gt_match["center_n"]) ** 2
            ) ** 0.5
            assert dist < CENTROID_ERROR_M_MAX, (
                f"Heap {m.heap_id} ({gt_match['type']}): centroid distance "
                f"{dist:.2f}m from expected"
            )

    def test_bbox_contains_centroid(
        self, heap_metrics: list[HeapMetrics]
    ) -> None:
        """Bounding box always contains centroid."""
        for m in heap_metrics:
            assert m.bbox_min_e <= m.centroid_e <= m.bbox_max_e, (
                f"Heap {m.heap_id}: centroid_e {m.centroid_e} outside bbox "
                f"[{m.bbox_min_e}, {m.bbox_max_e}]"
            )
            assert m.bbox_min_n <= m.centroid_n <= m.bbox_max_n, (
                f"Heap {m.heap_id}: centroid_n {m.centroid_n} outside bbox "
                f"[{m.bbox_min_n}, {m.bbox_max_n}]"
            )


# ---------------------------------------------------------------------------
# Integrity tests
# ---------------------------------------------------------------------------


class TestIntegrity:
    def test_no_negative_volumes(self, heap_metrics: list[HeapMetrics]) -> None:
        """All volumes > 0."""
        for m in heap_metrics:
            assert m.volume_m3 > 0, f"Heap {m.heap_id}: negative volume {m.volume_m3}"

    def test_no_nan_in_metrics(self, heap_metrics: list[HeapMetrics]) -> None:
        """No NaN in any field of any metric."""
        for m in heap_metrics:
            for field_name, value in m.model_dump().items():
                if isinstance(value, float):
                    assert not np.isnan(value), (
                        f"Heap {m.heap_id}: NaN in field {field_name}"
                    )

    def test_metrics_match_polygon_order(
        self, heap_metrics: list[HeapMetrics]
    ) -> None:
        """Returned list order matches input polygon order (by heap_id)."""
        # heap_ids should be monotonically increasing (labels are assigned sequentially)
        ids = [m.heap_id for m in heap_metrics]
        assert ids == sorted(ids), f"Heap IDs not in order: {ids}"

    def test_progress_emitted(
        self, pipeline_outputs: tuple[Path, Path, Path]
    ) -> None:
        """Progress callbacks fired."""
        _, _, ndsm_path = pipeline_outputs
        config = ProcessingConfig()

        result = segment_heaps(ndsm_path, config)
        accepted = [h for h in result.heaps if not h.is_filtered]

        progress_calls: list[tuple[int, str]] = []

        def on_progress(pct: int, msg: str) -> None:
            progress_calls.append((pct, msg))

        compute_heap_metrics(
            ndsm_path, result.label_map_path, accepted, 100.0, config,
            progress_callback=on_progress,
        )

        assert len(progress_calls) >= 5, (
            f"Expected at least 5 progress calls, got {len(progress_calls)}"
        )

    def test_vectorization_no_pixel_loops(self) -> None:
        """Inspect volume.py source — no pixel for-loops."""
        volume_src = Path(__file__).resolve().parent.parent / "processing" / "volume.py"
        content = volume_src.read_text(encoding="utf-8")

        # Check for patterns like "for row in range" or "for col in range"
        pixel_loop_patterns = [
            r"for\s+row\s+in\s+range",
            r"for\s+col\s+in\s+range",
            r"for\s+r\s+in\s+range",
            r"for\s+c\s+in\s+range",
            r"for\s+i\s+in\s+range.*height",
            r"for\s+j\s+in\s+range.*width",
        ]
        for pattern in pixel_loop_patterns:
            assert not re.search(pattern, content), (
                f"Found pixel loop pattern '{pattern}' in volume.py — "
                f"must use vectorized numpy/scipy operations"
            )


# ---------------------------------------------------------------------------
# Helper to match metric to ground truth by type
# ---------------------------------------------------------------------------


def _find_by_type(
    metrics: list[HeapMetrics], ground_truth: dict, heap_type: str
) -> HeapMetrics:
    """Find the metric that matches a specific ground truth heap type."""
    gt_heap = next(h for h in ground_truth["heaps"] if h["type"] == heap_type)
    # Match by centroid proximity
    best = min(
        metrics,
        key=lambda m: (
            (m.centroid_e - gt_heap["center_e"]) ** 2
            + (m.centroid_n - gt_heap["center_n"]) ** 2
        ),
    )
    return best
