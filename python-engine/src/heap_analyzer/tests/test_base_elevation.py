"""Tests for F3.S02 — base elevation override and ground sampling.

Validates:
  - recompute_all_heaps: batch recompute with new base elevation
  - sample_dsm_in_polygons: ground reference polygon sampling
  - ΔV approximation accuracy: client-side formula validated server-side
  - CLI commands: recompute-all-heaps, sample-ground
"""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import rasterio
import shapely.geometry

from heap_analyzer.config import ProcessingConfig
from heap_analyzer.processing.dsm import generate_dsm
from heap_analyzer.processing.dtm import estimate_dtm
from heap_analyzer.processing.ground_sampling import sample_dsm_in_polygons
from heap_analyzer.processing.segmentation import compute_ndsm, segment_heaps
from heap_analyzer.processing.volume import (
    compute_heap_metrics,
    recompute_all_heaps,
)

TEST_DATA_DIR = Path(__file__).resolve().parents[4] / "test-data"
OUTPUT_DIR = TEST_DATA_DIR / "output"


@pytest.fixture(scope="module")
def pipeline_data() -> dict:  # type: ignore[type-arg]
    """Run full pipeline and return metrics + polygon GeoJSON per heap."""
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

    result = segment_heaps(ndsm_path, config)
    accepted = [h for h in result.heaps if not h.is_filtered]

    base_elevation = 100.0
    metrics = compute_heap_metrics(
        ndsm_path, result.label_map_path, accepted, base_elevation, config
    )

    return {
        "ndsm_path": ndsm_path,
        "dsm_path": dsm_path,
        "metrics": metrics,
        "polygons": {m.heap_id: m.polygon_geojson for m in metrics},
        "base_elevation": base_elevation,
        "config": config,
        "bounds": (500000.0, 5000000.0, 500200.0, 5000200.0),
    }


class TestRecomputeAllHeaps:
    """Tests for batch recompute with new base elevation."""

    def test_higher_base_reduces_volumes(self, pipeline_data: dict) -> None:  # type: ignore[type-arg]
        """Raising the base elevation must reduce all volumes."""
        original_base = pipeline_data["base_elevation"]
        new_base = original_base + 0.5

        heaps_input = [
            {"id": hid, "polygon_geojson": poly}
            for hid, poly in pipeline_data["polygons"].items()
        ]
        results = recompute_all_heaps(
            pipeline_data["ndsm_path"], heaps_input, new_base, pipeline_data["config"],
            original_base_elevation=original_base,
        )

        for r in results:
            orig = next(m for m in pipeline_data["metrics"] if m.heap_id == r["id"])
            new_vol = r["metrics"]["volume_m3"]
            assert new_vol < orig.volume_m3, (
                f"Heap {r['id']}: raising base by 0.5m should reduce volume "
                f"(was {orig.volume_m3:.2f}, got {new_vol:.2f})"
            )

    def test_zero_delta_matches_original(self, pipeline_data: dict) -> None:  # type: ignore[type-arg]
        """Same base elevation -> volumes within +/-1% of original (regression guard)."""
        heaps_input = [
            {"id": hid, "polygon_geojson": poly}
            for hid, poly in pipeline_data["polygons"].items()
        ]
        results = recompute_all_heaps(
            pipeline_data["ndsm_path"],
            heaps_input,
            pipeline_data["base_elevation"],
            pipeline_data["config"],
        )

        for r in results:
            orig = next(m for m in pipeline_data["metrics"] if m.heap_id == r["id"])
            if orig.volume_m3 == 0:
                continue
            rel_err = abs(r["metrics"]["volume_m3"] - orig.volume_m3) / orig.volume_m3
            assert rel_err < 0.01, (
                f"Heap {r['id']}: same-base recompute drift {rel_err * 100:.2f}%"
            )

    def test_returns_all_heaps(self, pipeline_data: dict) -> None:  # type: ignore[type-arg]
        """Batch recompute must return results for all valid heaps."""
        heaps_input = [
            {"id": hid, "polygon_geojson": poly}
            for hid, poly in pipeline_data["polygons"].items()
        ]
        results = recompute_all_heaps(
            pipeline_data["ndsm_path"],
            heaps_input,
            pipeline_data["base_elevation"],
            pipeline_data["config"],
        )
        assert len(results) == len(heaps_input)


class TestDeltaVApproximation:
    """Validate the client-side ΔV ≈ -δ × Σ area formula."""

    def test_approximation_accuracy_flat_terrain(self, pipeline_data: dict) -> None:  # type: ignore[type-arg]
        """On flat synthetic terrain, ΔV ≈ -δ × Σ area should match within 15%.

        Tolerance is 15% (not 5%) because pixels near the height threshold
        get excluded when nDSM decreases, causing a nonlinear edge effect
        that the linear approximation cannot capture. The formula is still
        useful for real-time slider feedback (correct direction and order
        of magnitude).
        """
        delta = 0.10  # raise base by 10 cm
        original_base = pipeline_data["base_elevation"]
        new_base = original_base + delta

        heaps_input = [
            {"id": hid, "polygon_geojson": poly}
            for hid, poly in pipeline_data["polygons"].items()
        ]

        new_results = recompute_all_heaps(
            pipeline_data["ndsm_path"], heaps_input, new_base, pipeline_data["config"],
            original_base_elevation=original_base,
        )

        total_area = sum(m.planimetric_area_m2 for m in pipeline_data["metrics"])
        approx_delta_v = -delta * total_area

        total_original_v = sum(m.volume_m3 for m in pipeline_data["metrics"])
        total_new_v = sum(r["metrics"]["volume_m3"] for r in new_results)
        precise_delta_v = total_new_v - total_original_v

        # Only check if the delta is meaningful
        if abs(precise_delta_v) > 1.0:
            rel_err = abs(approx_delta_v - precise_delta_v) / abs(precise_delta_v)
            assert rel_err < 0.15, (
                f"ΔV approximation error {rel_err * 100:.1f}%: "
                f"approx={approx_delta_v:.1f} precise={precise_delta_v:.1f}"
            )


class TestSampleDsmInPolygons:
    """Tests for ground-reference polygon sampling."""

    def test_ground_polygon_mean_matches_terrain(self, pipeline_data: dict) -> None:  # type: ignore[type-arg]
        """Ground polygons in known-flat area -> mean ≈ base_elevation ± 0.05m."""
        # Use bottom-left corner of the 200x200m site (ground-only, no heaps)
        bounds = pipeline_data["bounds"]
        ground_poly = shapely.geometry.box(
            bounds[0] + 5,   # min_e + 5m
            bounds[1] + 5,   # min_n + 5m
            bounds[0] + 25,  # 20m × 20m square
            bounds[1] + 25,
        )
        result = sample_dsm_in_polygons(
            str(pipeline_data["dsm_path"]),
            [shapely.geometry.mapping(ground_poly)],
        )
        assert abs(result["mean_elevation"] - pipeline_data["base_elevation"]) < 0.05
        assert result["num_pixels"] > 100  # 20m×20m @ 0.1m/px = 40000 px
        assert result["std_elevation"] < 0.10  # flat terrain -> low std

    def test_multiple_ground_polygons(self, pipeline_data: dict) -> None:  # type: ignore[type-arg]
        """Multiple ground polygons are combined correctly."""
        bounds = pipeline_data["bounds"]
        poly1 = shapely.geometry.box(bounds[0] + 5, bounds[1] + 5, bounds[0] + 15, bounds[1] + 15)
        poly2 = shapely.geometry.box(bounds[2] - 15, bounds[3] - 15, bounds[2] - 5, bounds[3] - 5)

        result = sample_dsm_in_polygons(
            str(pipeline_data["dsm_path"]),
            [shapely.geometry.mapping(poly1), shapely.geometry.mapping(poly2)],
        )
        assert len(result["per_polygon"]) == 2
        assert result["num_pixels"] > 0
        # Both polygons should have data
        for pp in result["per_polygon"]:
            assert pp["num_pixels"] > 0

    def test_no_intersection_raises(self, pipeline_data: dict) -> None:  # type: ignore[type-arg]
        """Polygon outside DSM extent -> ValueError."""
        far_poly = shapely.geometry.box(0, 0, 10, 10)
        with pytest.raises(ValueError, match="No ground polygons intersect"):
            sample_dsm_in_polygons(
                str(pipeline_data["dsm_path"]),
                [shapely.geometry.mapping(far_poly)],
            )

    def test_nonexistent_dsm_raises(self) -> None:
        """Non-existent DSM file -> FileNotFoundError."""
        poly = shapely.geometry.box(0, 0, 10, 10)
        with pytest.raises(FileNotFoundError):
            sample_dsm_in_polygons(
                "/nonexistent/dsm.tif",
                [shapely.geometry.mapping(poly)],
            )


class TestCliRecomputeAll:
    """CLI recompute-all-heaps emits JSON Lines."""

    def test_cli_emits_json_lines(self, pipeline_data: dict) -> None:  # type: ignore[type-arg]
        """CLI recompute-all-heaps returns progress + result as JSON Lines."""
        ndsm_path = pipeline_data["ndsm_path"]
        heaps_input = [
            {"id": hid, "polygon_geojson": poly}
            for hid, poly in pipeline_data["polygons"].items()
        ]
        heaps_json = json.dumps(heaps_input)

        result = subprocess.run(
            [
                sys.executable, "-m", "heap_analyzer.cli",
                "recompute-all-heaps",
                "--ndsm", str(ndsm_path),
                "--heaps-json", heaps_json,
                "--base-elevation", "100.5",
                "--original-base-elevation", "100.0",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        assert len(lines) >= 2, f"Expected >=2 lines (progress+result), got {len(lines)}"

        for line in lines:
            msg = json.loads(line)
            assert "type" in msg

        # Last line should be result
        last = json.loads(lines[-1])
        assert last["type"] == "result"
        assert "heaps" in last["data"]
        assert last["data"]["base_elevation"] == 100.5


class TestCliSampleGround:
    """CLI sample-ground emits JSON Lines."""

    def test_cli_emits_json_lines(self, pipeline_data: dict) -> None:  # type: ignore[type-arg]
        """CLI sample-ground returns result as JSON Lines."""
        dsm_path = pipeline_data["dsm_path"]
        bounds = pipeline_data["bounds"]
        ground_poly = shapely.geometry.box(
            bounds[0] + 5, bounds[1] + 5, bounds[0] + 25, bounds[1] + 25
        )
        polygons_json = json.dumps([shapely.geometry.mapping(ground_poly)])

        result = subprocess.run(
            [
                sys.executable, "-m", "heap_analyzer.cli",
                "sample-ground",
                "--dsm", str(dsm_path),
                "--polygons-json", polygons_json,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        assert len(lines) >= 1

        last = json.loads(lines[-1])
        assert last["type"] == "result"
        assert "mean_elevation" in last["data"]
        assert last["data"]["num_pixels"] > 0
