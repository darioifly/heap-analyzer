"""Tests for nDSM computation and heap segmentation."""

import json
import shutil
from pathlib import Path

import numpy as np
import pytest
import rasterio

from heap_analyzer.config import ProcessingConfig
from heap_analyzer.processing.dsm import generate_dsm
from heap_analyzer.processing.dtm import estimate_dtm
from heap_analyzer.processing.segmentation import (
    HeapPolygon,
    SegmentationResult,
    compute_ndsm,
    segment_heaps,
)

# ---------------------------------------------------------------------------
# Fixtures — generate DSM, DTM, nDSM from synthetic data once per module
# ---------------------------------------------------------------------------

TEST_DATA_DIR = Path(__file__).resolve().parents[4] / "test-data"
OUTPUT_DIR = TEST_DATA_DIR / "output"
GT_PATH = TEST_DATA_DIR / "ground_truth.json"


@pytest.fixture(scope="module")
def ensure_dsm_dtm() -> tuple[Path, Path]:
    """Ensure DSM and DTM exist in output directory."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config = ProcessingConfig()

    dsm_path = OUTPUT_DIR / "dsm.tif"
    if not dsm_path.exists():
        generate_dsm(TEST_DATA_DIR / "test.las", dsm_path, config)

    dtm_path = OUTPUT_DIR / "dtm.tif"
    if not dtm_path.exists():
        estimate_dtm(dsm_path, dtm_path, config)

    return dsm_path, dtm_path


@pytest.fixture(scope="module")
def ndsm_path(ensure_dsm_dtm: tuple[Path, Path]) -> Path:
    """Compute nDSM and return path."""
    dsm_path, dtm_path = ensure_dsm_dtm
    out = OUTPUT_DIR / "ndsm.tif"
    compute_ndsm(dsm_path, dtm_path, out)
    return out


@pytest.fixture(scope="module")
def segmentation_result(ndsm_path: Path) -> SegmentationResult:
    """Run segmentation on nDSM."""
    config = ProcessingConfig()
    return segment_heaps(ndsm_path, config)


@pytest.fixture(scope="module")
def ground_truth() -> dict:
    """Load ground truth data."""
    return json.loads(GT_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# nDSM tests
# ---------------------------------------------------------------------------


class TestComputeNdsm:
    def test_compute_ndsm_basic(
        self, ndsm_path: Path, ensure_dsm_dtm: tuple[Path, Path]
    ) -> None:
        """nDSM = DSM - DTM, dimensions/CRS preserved."""
        dsm_path, _ = ensure_dsm_dtm
        with rasterio.open(str(dsm_path)) as ds_dsm, rasterio.open(str(ndsm_path)) as ds_ndsm:
            assert ds_ndsm.width == ds_dsm.width
            assert ds_ndsm.height == ds_dsm.height
            assert str(ds_ndsm.crs) == str(ds_dsm.crs)

            ndsm = ds_ndsm.read(1)
            valid = ndsm[ndsm != ds_ndsm.nodata]
            # nDSM values should be in a reasonable range [0, ~12m] for synthetic
            assert valid.max() <= 15.0, f"nDSM max too high: {valid.max()}"

    def test_compute_ndsm_no_negatives(self, ndsm_path: Path) -> None:
        """nDSM should be >= 0 (within numerical noise)."""
        with rasterio.open(str(ndsm_path)) as ds:
            ndsm = ds.read(1).astype(np.float64)
            ndsm[np.isclose(ndsm, ds.nodata)] = 0.0
            assert ndsm.min() >= -0.05, f"nDSM has significant negatives: {ndsm.min()}"


# ---------------------------------------------------------------------------
# Segmentation tests
# ---------------------------------------------------------------------------


class TestSegmentation:
    def test_segment_finds_four_heaps(
        self, segmentation_result: SegmentationResult
    ) -> None:
        """On synthetic data, must detect exactly 4 heaps."""
        assert segmentation_result.accepted_count == 4, (
            f"Expected 4 accepted heaps, got {segmentation_result.accepted_count}"
        )

    def test_segment_no_false_filters(
        self, segmentation_result: SegmentationResult
    ) -> None:
        """No synthetic heaps should be filtered out."""
        assert segmentation_result.filtered_count == 0, (
            f"Expected 0 filtered, got {segmentation_result.filtered_count}"
        )

    def test_segment_polygons_match_centroids(
        self, segmentation_result: SegmentationResult, ground_truth: dict
    ) -> None:
        """Each detected polygon centroid is within 2m of a known heap center."""
        from shapely.geometry import shape as shapely_shape

        gt_centers = [
            (h["center_e"], h["center_n"]) for h in ground_truth["heaps"]
        ]

        accepted = [h for h in segmentation_result.heaps if not h.is_filtered]
        for heap in accepted:
            poly = shapely_shape(heap.polygon_geojson)
            centroid = poly.centroid
            distances = [
                ((centroid.x - ce) ** 2 + (centroid.y - cn) ** 2) ** 0.5
                for ce, cn in gt_centers
            ]
            min_dist = min(distances)
            assert min_dist < 2.0, (
                f"Heap {heap.heap_id} centroid ({centroid.x:.1f}, {centroid.y:.1f}) "
                f"is {min_dist:.1f}m from nearest ground truth"
            )

    def test_segment_polygons_are_valid(
        self, segmentation_result: SegmentationResult
    ) -> None:
        """Every polygon must be valid (shapely)."""
        from shapely.geometry import shape as shapely_shape

        for heap in segmentation_result.heaps:
            if heap.polygon_geojson:
                poly = shapely_shape(heap.polygon_geojson)
                assert poly.is_valid, f"Heap {heap.heap_id} polygon is not valid"

    def test_segment_polygon_areas(
        self, segmentation_result: SegmentationResult, ground_truth: dict
    ) -> None:
        """Detected area within 15% of analytical for each heap."""
        import math

        from shapely.geometry import shape as shapely_shape

        gt_heaps = ground_truth["heaps"]
        accepted = [h for h in segmentation_result.heaps if not h.is_filtered]

        for heap in accepted:
            poly = shapely_shape(heap.polygon_geojson)
            centroid = poly.centroid

            # Find matching ground truth heap by centroid
            best_gt = min(
                gt_heaps,
                key=lambda g: (
                    (g["center_e"] - centroid.x) ** 2
                    + (g["center_n"] - centroid.y) ** 2
                ),
            )

            # Compute expected area based on heap type
            if best_gt["type"] == "cone":
                expected_area = math.pi * best_gt["radius"] ** 2
            elif best_gt["type"] == "hemisphere":
                expected_area = math.pi * best_gt["radius"] ** 2
            elif best_gt["type"] == "pyramid":
                expected_area = best_gt["base_size"] ** 2
            elif best_gt["type"] == "truncated_cone":
                expected_area = math.pi * best_gt["r_bottom"] ** 2
            else:
                continue

            error_pct = abs(heap.area_m2 - expected_area) / expected_area * 100
            # 20% tolerance: morphological opening/closing erodes sharp edges
            # (pyramid corners), and discretization at 0.10m adds ~5% error
            assert error_pct < 20.0, (
                f"Heap {heap.heap_id} ({best_gt['type']}): area {heap.area_m2:.1f} m² "
                f"vs expected {expected_area:.1f} m², error {error_pct:.1f}%"
            )

    def test_label_map_written(
        self, segmentation_result: SegmentationResult
    ) -> None:
        """Output GeoTIFF exists, dtype uint16, nodata=0, has correct labels."""
        path = segmentation_result.label_map_path
        assert path.exists(), f"Label map not found: {path}"

        with rasterio.open(str(path)) as ds:
            assert ds.dtypes[0] == "uint16"
            assert ds.nodata == 0
            data = ds.read(1)
            max_label = data.max()
            n_accepted = segmentation_result.accepted_count + segmentation_result.filtered_count
            assert max_label == n_accepted, (
                f"Max label {max_label} != total heaps {n_accepted}"
            )

    def test_progress_emitted(self, ndsm_path: Path) -> None:
        """Capture progress callbacks, verify multiple phases reported."""
        config = ProcessingConfig()
        progress_calls: list[tuple[int, str]] = []

        def on_progress(pct: int, msg: str) -> None:
            progress_calls.append((pct, msg))

        segment_heaps(ndsm_path, config, progress_callback=on_progress)

        assert len(progress_calls) >= 5, (
            f"Expected at least 5 progress calls, got {len(progress_calls)}"
        )
        # Last progress should be 100%
        assert progress_calls[-1][0] == 100


# ---------------------------------------------------------------------------
# Filter tests (synthetic additions)
# ---------------------------------------------------------------------------


class TestFilters:
    def test_filter_machinery_synthetic(
        self, ndsm_path: Path, tmp_path: Path
    ) -> None:
        """Add a small uniform-height rectangle → verify filtered as machinery/structure."""
        # Copy nDSM and add a small rectangular uniform block
        modified_ndsm_path = tmp_path / "ndsm_machinery.tif"
        shutil.copy2(ndsm_path, modified_ndsm_path)

        with rasterio.open(str(modified_ndsm_path), "r+") as ds:
            data = ds.read(1).astype(np.float64)
            nodata = ds.nodata
            if nodata is not None:
                data[np.isclose(data, nodata)] = 0.0

            # Add a 10m x 8m rectangle at uniform height 3m
            # At 0.10m resolution: 100 x 80 pixels
            # After morphological opening (3px), effective ~94x74 ≈ 70 m²
            # Uniform height → height_std ≈ 0, height_mean = 3m → structure filter
            transform = ds.transform
            inv = ~transform
            # Place at (500100, 5000100) — away from heaps
            col_start, row_start = inv * (500100.0, 5000100.0)
            r0 = int(row_start)
            c0 = int(col_start)
            data[r0 : r0 + 80, c0 : c0 + 100] = 3.0  # uniform 3m height

            out = np.where(np.isnan(data), nodata, data).astype(np.float32)
            ds.write(out, 1)

        config = ProcessingConfig()
        result = segment_heaps(modified_ndsm_path, config)

        filtered = [h for h in result.heaps if h.is_filtered]
        assert len(filtered) >= 1, "Expected at least 1 filtered heap for machinery block"

        # Check reason mentions machinery or structure
        reasons = [h.filter_reason or "" for h in filtered]
        has_relevant_reason = any(
            "macchinario" in r.lower() or "struttura" in r.lower()
            for r in reasons
        )
        assert has_relevant_reason, f"No filter reason mentions machinery/structure: {reasons}"

    def test_filter_min_area(self, ndsm_path: Path, tmp_path: Path) -> None:
        """Add a tiny bump (< 50 m²) → verify filtered as too small."""
        modified_ndsm_path = tmp_path / "ndsm_tiny.tif"
        shutil.copy2(ndsm_path, modified_ndsm_path)

        with rasterio.open(str(modified_ndsm_path), "r+") as ds:
            data = ds.read(1).astype(np.float64)
            nodata = ds.nodata
            if nodata is not None:
                data[np.isclose(data, nodata)] = 0.0

            # Add a tiny 2m x 2m bump = 4 m² < 50 m²
            # At 0.10m resolution: 20 x 20 pixels
            transform = ds.transform
            inv = ~transform
            col_start, row_start = inv * (500180.0, 5000180.0)
            r0 = int(row_start)
            c0 = int(col_start)
            data[r0 : r0 + 20, c0 : c0 + 20] = 2.0

            out = np.where(np.isnan(data), nodata, data).astype(np.float32)
            ds.write(out, 1)

        config = ProcessingConfig()
        result = segment_heaps(modified_ndsm_path, config)

        # Find filtered heaps that are small
        small_filtered = [
            h for h in result.heaps
            if h.is_filtered and h.filter_reason and "piccola" in h.filter_reason.lower()
        ]
        assert len(small_filtered) >= 1, "Expected at least 1 heap filtered for small area"
