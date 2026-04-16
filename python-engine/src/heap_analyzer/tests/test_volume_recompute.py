"""Tests for recompute_single_heap — regression guard for F3.S01 editing.

Key invariant: identical polygon → volume within ±1% of batch pipeline result.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import rasterio

from heap_analyzer.config import ProcessingConfig
from heap_analyzer.processing.dsm import generate_dsm
from heap_analyzer.processing.dtm import estimate_dtm
from heap_analyzer.processing.segmentation import (
    compute_ndsm,
    segment_heaps,
)
from heap_analyzer.processing.volume import (
    compute_heap_metrics,
    recompute_single_heap,
)

TEST_DATA_DIR = Path(__file__).resolve().parents[4] / "test-data"
OUTPUT_DIR = TEST_DATA_DIR / "output"


@pytest.fixture(scope="module")
def pipeline_data() -> dict:
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
        "metrics": metrics,
        "polygons": {m.heap_id: m.polygon_geojson for m in metrics},
        "base_elevation": base_elevation,
        "config": config,
    }


class TestRecomputeMatchesOriginal:
    """REGRESSION GUARD: identical polygon → volume within ±1% of batch result."""

    def test_recompute_matches_within_1pct(self, pipeline_data: dict) -> None:
        """Each heap recomputed individually must match batch result."""
        ndsm_path = pipeline_data["ndsm_path"]
        base_elevation = pipeline_data["base_elevation"]
        config = pipeline_data["config"]

        for original in pipeline_data["metrics"]:
            poly_geojson = pipeline_data["polygons"][original.heap_id]
            recomputed = recompute_single_heap(
                ndsm_path, poly_geojson, base_elevation, config
            )
            rel_err = abs(recomputed.volume_m3 - original.volume_m3) / original.volume_m3
            assert rel_err < 0.01, (
                f"Heap {original.heap_id}: recomputed {recomputed.volume_m3:.2f} m³ "
                f"vs original {original.volume_m3:.2f} m³, rel err {rel_err * 100:.2f}%"
            )

    def test_recompute_area_matches(self, pipeline_data: dict) -> None:
        """Planimetric area within 5% of batch result."""
        ndsm_path = pipeline_data["ndsm_path"]
        base_elevation = pipeline_data["base_elevation"]
        config = pipeline_data["config"]

        for original in pipeline_data["metrics"]:
            poly_geojson = pipeline_data["polygons"][original.heap_id]
            recomputed = recompute_single_heap(
                ndsm_path, poly_geojson, base_elevation, config
            )
            if original.planimetric_area_m2 > 0:
                rel_err = (
                    abs(recomputed.planimetric_area_m2 - original.planimetric_area_m2)
                    / original.planimetric_area_m2
                )
                assert rel_err < 0.05, (
                    f"Heap {original.heap_id}: area {recomputed.planimetric_area_m2:.1f} "
                    f"vs {original.planimetric_area_m2:.1f}, err {rel_err * 100:.1f}%"
                )


class TestRecomputeEdgeCases:
    """Validation errors for invalid inputs."""

    def test_invalid_polygon_raises(self, pipeline_data: dict) -> None:
        """Empty polygon → ValueError."""
        ndsm_path = pipeline_data["ndsm_path"]
        with pytest.raises(ValueError, match="Invalid polygon|does not intersect"):
            recompute_single_heap(
                ndsm_path,
                {"type": "Polygon", "coordinates": []},
                100.0,
                ProcessingConfig(),
            )

    def test_polygon_outside_raster_raises(self, pipeline_data: dict) -> None:
        """Polygon far outside nDSM extent → ValueError."""
        ndsm_path = pipeline_data["ndsm_path"]
        far_polygon = {
            "type": "Polygon",
            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
        }
        with pytest.raises(ValueError, match="does not intersect"):
            recompute_single_heap(
                ndsm_path, far_polygon, 100.0, ProcessingConfig()
            )

    def test_self_intersecting_polygon_repaired(self, pipeline_data: dict) -> None:
        """Self-intersecting (bowtie) polygon is auto-repaired via buffer(0)."""
        ndsm_path = pipeline_data["ndsm_path"]
        # Get the extent of the nDSM to create a polygon inside it
        with rasterio.open(str(ndsm_path)) as src:
            bounds = src.bounds

        cx = (bounds.left + bounds.right) / 2
        cy = (bounds.bottom + bounds.top) / 2
        d = 5.0  # small polygon

        # Bowtie: self-intersecting
        bowtie = {
            "type": "Polygon",
            "coordinates": [[
                [cx - d, cy - d],
                [cx + d, cy + d],
                [cx + d, cy - d],
                [cx - d, cy + d],
                [cx - d, cy - d],
            ]],
        }
        # Should not raise — buffer(0) repairs it
        result = recompute_single_heap(ndsm_path, bowtie, 100.0, ProcessingConfig())
        assert result.volume_m3 >= 0


class TestRecomputeCli:
    """CLI `recompute-heap` emits JSON Lines on stdout."""

    def test_cli_emits_json_result(self, pipeline_data: dict) -> None:
        """CLI recompute-heap returns valid JSON with type=result."""
        ndsm_path = pipeline_data["ndsm_path"]
        first_poly = list(pipeline_data["polygons"].values())[0]
        poly_json = json.dumps(first_poly)

        result = subprocess.run(
            [
                sys.executable, "-m", "heap_analyzer.cli",
                "recompute-heap",
                "--ndsm", str(ndsm_path),
                "--polygon-json", poly_json,
                "--base-elevation", "100.0",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        # Parse stdout — should be exactly one JSON line with type=result
        lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        assert len(lines) == 1, f"Expected 1 line, got {len(lines)}: {lines}"

        msg = json.loads(lines[0])
        assert msg["type"] == "result"
        assert "data" in msg
        assert "volume_m3" in msg["data"]
        assert msg["data"]["volume_m3"] > 0
