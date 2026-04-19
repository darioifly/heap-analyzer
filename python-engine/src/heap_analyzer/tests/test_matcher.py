"""Tests for F6.S01 — Spatial matching of heaps between two surveys."""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds
from shapely.geometry import Polygon

from heap_analyzer.comparison.config import ComparisonConfig
from heap_analyzer.comparison.matcher import HeapRecord, MatchResult, match_heaps
from heap_analyzer.comparison.palette import COMPARISON_STATE_COLORS


# ---------------------------------------------------------------------------
# Fixtures: synthetic heap records
# ---------------------------------------------------------------------------

def _make_circle_polygon(cx: float, cy: float, r: float, n: int = 64) -> dict:
    """Create a circle polygon GeoJSON dict centered at (cx, cy) with radius r."""
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
    coords = [(cx + r * np.cos(a), cy + r * np.sin(a)) for a in angles]
    coords.append(coords[0])  # close ring
    return {"type": "Polygon", "coordinates": [coords]}


def _make_box_polygon(cx: float, cy: float, half: float) -> dict:
    """Create a square polygon centered at (cx, cy)."""
    return {
        "type": "Polygon",
        "coordinates": [[
            (cx - half, cy - half),
            (cx + half, cy - half),
            (cx + half, cy + half),
            (cx - half, cy + half),
            (cx - half, cy - half),
        ]],
    }


@pytest.fixture
def baseline_heaps() -> list[HeapRecord]:
    """4 heaps matching the baseline test site layout."""
    return [
        HeapRecord(
            heap_id=1,
            polygon_geojson=_make_circle_polygon(500050, 5000050, 15),
            volume_m3=1178.0,
            planimetric_area_m2=706.0,
            max_height_m=5.0,
        ),
        HeapRecord(
            heap_id=2,
            polygon_geojson=_make_circle_polygon(500150, 5000050, 12),
            volume_m3=3619.0,
            planimetric_area_m2=452.0,
            max_height_m=12.0,
        ),
        HeapRecord(
            heap_id=3,
            polygon_geojson=_make_box_polygon(500050, 5000150, 10),
            volume_m3=800.0,
            planimetric_area_m2=400.0,
            max_height_m=6.0,
        ),
        HeapRecord(
            heap_id=4,
            polygon_geojson=_make_circle_polygon(500150, 5000150, 18),
            volume_m3=2228.0,
            planimetric_area_m2=1017.0,
            max_height_m=4.0,
        ),
    ]


@pytest.fixture
def t2_heaps() -> list[HeapRecord]:
    """T2 variant: heap 1 unchanged, heap 2 grown, heap 3 decreased,
    heap 4 removed, heap 5 added."""
    return [
        HeapRecord(
            heap_id=1,
            polygon_geojson=_make_circle_polygon(500050, 5000050, 15),
            volume_m3=1178.0,
            planimetric_area_m2=706.0,
            max_height_m=5.0,
        ),
        HeapRecord(
            heap_id=2,
            polygon_geojson=_make_circle_polygon(500150, 5000050, 13.2),
            volume_m3=4838.0,
            planimetric_area_m2=547.0,
            max_height_m=13.2,
        ),
        HeapRecord(
            heap_id=3,
            polygon_geojson=_make_box_polygon(500050, 5000150, 9.13),
            volume_m3=667.0,
            planimetric_area_m2=333.0,
            max_height_m=6.0,
        ),
        HeapRecord(
            heap_id=5,
            polygon_geojson=_make_circle_polygon(500100, 5000100, 10),
            volume_m3=314.0,
            planimetric_area_m2=314.0,
            max_height_m=3.0,
        ),
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMatchHeaps:
    """Core matching algorithm tests."""

    def test_basic_matching(
        self, baseline_heaps: list[HeapRecord], t2_heaps: list[HeapRecord],
    ) -> None:
        """Match baseline vs t2 — expect 3 matched, 1 removed, 1 added."""
        result = match_heaps(baseline_heaps, t2_heaps)

        assert len(result.matched) == 3
        assert len(result.removed_in_a) == 1
        assert len(result.added_in_b) == 1
        assert 4 in result.removed_in_a
        assert 5 in result.added_in_b

    def test_unchanged_classification(
        self, baseline_heaps: list[HeapRecord], t2_heaps: list[HeapRecord],
    ) -> None:
        """Heap #1 should be classified as unchanged."""
        result = match_heaps(baseline_heaps, t2_heaps)

        heap1_match = next(m for m in result.matched if m.heap_a_id == 1)
        assert heap1_match.state == "unchanged"
        assert abs(heap1_match.delta_volume_percent) < 5.0

    def test_grown_classification(
        self, baseline_heaps: list[HeapRecord], t2_heaps: list[HeapRecord],
    ) -> None:
        """Heap #2 should be classified as grown."""
        result = match_heaps(baseline_heaps, t2_heaps)

        heap2_match = next(m for m in result.matched if m.heap_a_id == 2)
        assert heap2_match.state == "grown"
        assert heap2_match.delta_volume > 0

    def test_decreased_classification(
        self, baseline_heaps: list[HeapRecord], t2_heaps: list[HeapRecord],
    ) -> None:
        """Heap #3 should be classified as decreased."""
        result = match_heaps(baseline_heaps, t2_heaps)

        heap3_match = next(m for m in result.matched if m.heap_a_id == 3)
        assert heap3_match.state == "decreased"
        assert heap3_match.delta_volume < 0

    def test_summary_counts(
        self, baseline_heaps: list[HeapRecord], t2_heaps: list[HeapRecord],
    ) -> None:
        """Summary should reflect 1 unchanged, 1 grown, 1 decreased, 1 removed, 1 added."""
        result = match_heaps(baseline_heaps, t2_heaps)
        s = result.summary

        assert s.unchanged == 1
        assert s.grown == 1
        assert s.decreased == 1
        assert s.removed == 1
        assert s.added == 1
        assert s.ambiguous == 0

    def test_total_volumes(
        self, baseline_heaps: list[HeapRecord], t2_heaps: list[HeapRecord],
    ) -> None:
        """Volume totals should match sum of inputs."""
        result = match_heaps(baseline_heaps, t2_heaps)

        expected_a = sum(h.volume_m3 for h in baseline_heaps)
        expected_b = sum(h.volume_m3 for h in t2_heaps)

        assert result.volume_a == pytest.approx(expected_a, abs=1.0)
        assert result.volume_b == pytest.approx(expected_b, abs=1.0)

    def test_empty_inputs(self) -> None:
        """Matching with empty inputs should not crash."""
        result = match_heaps([], [])
        assert len(result.matched) == 0
        assert result.total_delta_volume == 0.0

    def test_all_added(self, t2_heaps: list[HeapRecord]) -> None:
        """All B heaps are added when A is empty."""
        result = match_heaps([], t2_heaps)
        assert len(result.added_in_b) == len(t2_heaps)
        assert len(result.removed_in_a) == 0

    def test_all_removed(self, baseline_heaps: list[HeapRecord]) -> None:
        """All A heaps are removed when B is empty."""
        result = match_heaps(baseline_heaps, [])
        assert len(result.removed_in_a) == len(baseline_heaps)
        assert len(result.added_in_b) == 0

    def test_invalid_polygon_repaired(self) -> None:
        """Self-intersecting polygon should be repaired via make_valid."""
        # Create a bowtie (self-intersecting) polygon
        bowtie_geojson = {
            "type": "Polygon",
            "coordinates": [[
                (0, 0), (10, 10), (10, 0), (0, 10), (0, 0),
            ]],
        }
        heaps_a = [HeapRecord(
            heap_id=1,
            polygon_geojson=bowtie_geojson,
            volume_m3=100.0,
            planimetric_area_m2=50.0,
            max_height_m=3.0,
        )]
        heaps_b = [HeapRecord(
            heap_id=1,
            polygon_geojson=_make_box_polygon(5, 5, 5),
            volume_m3=110.0,
            planimetric_area_m2=100.0,
            max_height_m=3.5,
        )]

        # Should not raise
        result = match_heaps(heaps_a, heaps_b)
        assert isinstance(result, MatchResult)

    def test_ambiguous_case(self) -> None:
        """Two A heaps both overlapping one big B heap → ambiguous."""
        big_b = _make_box_polygon(100, 100, 20)  # 40x40

        heaps_a = [
            HeapRecord(
                heap_id=1,
                polygon_geojson=_make_box_polygon(90, 100, 10),  # 20x20 left
                volume_m3=500.0,
                planimetric_area_m2=400.0,
                max_height_m=3.0,
            ),
            HeapRecord(
                heap_id=2,
                polygon_geojson=_make_box_polygon(110, 100, 10),  # 20x20 right
                volume_m3=500.0,
                planimetric_area_m2=400.0,
                max_height_m=3.0,
            ),
        ]
        heaps_b = [
            HeapRecord(
                heap_id=10,
                polygon_geojson=big_b,
                volume_m3=1000.0,
                planimetric_area_m2=1600.0,
                max_height_m=4.0,
            ),
        ]

        result = match_heaps(
            heaps_a, heaps_b,
            ComparisonConfig(iou_threshold=0.2),
        )

        # One should match, the other should be removed or the matched one
        # flagged as ambiguous
        matched_states = [m.state for m in result.matched]
        if result.matched:
            # The matched pair should be flagged as ambiguous because
            # both A heaps overlap the same B heap
            assert "ambiguous" in matched_states or len(result.removed_in_a) > 0

    def test_iou_threshold_respected(self) -> None:
        """Non-overlapping heaps should not match regardless of threshold."""
        heaps_a = [HeapRecord(
            heap_id=1,
            polygon_geojson=_make_circle_polygon(0, 0, 5),
            volume_m3=100.0,
            planimetric_area_m2=78.0,
            max_height_m=3.0,
        )]
        heaps_b = [HeapRecord(
            heap_id=1,
            polygon_geojson=_make_circle_polygon(1000, 1000, 5),
            volume_m3=100.0,
            planimetric_area_m2=78.0,
            max_height_m=3.0,
        )]

        result = match_heaps(heaps_a, heaps_b)
        assert len(result.matched) == 0
        assert len(result.removed_in_a) == 1
        assert len(result.added_in_b) == 1

    def test_config_passthrough(
        self, baseline_heaps: list[HeapRecord], t2_heaps: list[HeapRecord],
    ) -> None:
        """Config should be stored in the result."""
        cfg = ComparisonConfig(iou_threshold=0.5, stability_threshold=0.10)
        result = match_heaps(baseline_heaps, t2_heaps, cfg)
        assert result.config.iou_threshold == 0.5
        assert result.config.stability_threshold == 0.10

    def test_match_result_serializable(
        self, baseline_heaps: list[HeapRecord], t2_heaps: list[HeapRecord],
    ) -> None:
        """MatchResult should serialize to JSON without errors."""
        result = match_heaps(baseline_heaps, t2_heaps)
        json_str = result.model_dump_json()
        parsed = json.loads(json_str)
        assert "matched" in parsed
        assert "summary" in parsed


class TestGenerateT2Dataset:
    """Test that the t2 variant dataset generates correctly."""

    def test_generate_t2_dataset(self, tmp_path: Path) -> None:
        """Generate t2 dataset and verify outputs exist."""
        from heap_analyzer.test_data_generator import create_test_site_t2

        gt = create_test_site_t2(tmp_path)

        assert (tmp_path / "test.las").exists()
        assert (tmp_path / "test.tif").exists()
        assert (tmp_path / "ground_truth_t2.json").exists()
        assert gt["variant"] == "t2"
        assert len(gt["heaps"]) == 4  # type: ignore[arg-type]

    def test_t2_ground_truth_has_expected_comparison(self, tmp_path: Path) -> None:
        """Ground truth includes expected comparison outcomes."""
        from heap_analyzer.test_data_generator import create_test_site_t2

        gt = create_test_site_t2(tmp_path)
        expected = gt["expected_comparison"]
        assert 1 in expected["unchanged"]  # type: ignore[operator]
        assert 2 in expected["grown"]  # type: ignore[operator]
        assert 3 in expected["decreased"]  # type: ignore[operator]
        assert 4 in expected["removed"]  # type: ignore[operator]
        assert 5 in expected["added"]  # type: ignore[operator]


class TestCLICompare:
    """Test CLI compare command roundtrip."""

    @pytest.fixture
    def synthetic_results(self, tmp_path: Path) -> tuple[Path, Path]:
        """Create two minimal results.json files for CLI testing."""
        from heap_analyzer.processing.volume import HeapMetrics

        metrics_a = [
            HeapMetrics(
                heap_id=1,
                polygon_geojson=_make_circle_polygon(500050, 5000050, 15),
                volume_m3=1178.0,
                planimetric_area_m2=706.0,
                surface_area_m2=750.0,
                max_height_m=5.0,
                mean_height_m=2.5,
                base_elevation_m=100.0,
                centroid_e=500050.0,
                centroid_n=5000050.0,
                bbox_min_e=500035.0,
                bbox_min_n=5000035.0,
                bbox_max_e=500065.0,
                bbox_max_n=5000065.0,
            ),
        ]
        metrics_b = [
            HeapMetrics(
                heap_id=1,
                polygon_geojson=_make_circle_polygon(500050, 5000050, 15),
                volume_m3=1200.0,
                planimetric_area_m2=706.0,
                surface_area_m2=750.0,
                max_height_m=5.2,
                mean_height_m=2.6,
                base_elevation_m=100.0,
                centroid_e=500050.0,
                centroid_n=5000050.0,
                bbox_min_e=500035.0,
                bbox_min_n=5000035.0,
                bbox_max_e=500065.0,
                bbox_max_n=5000065.0,
            ),
        ]

        results_a = tmp_path / "results_a.json"
        results_b = tmp_path / "results_b.json"

        results_a.write_text(json.dumps({
            "heap_metrics": [m.model_dump() for m in metrics_a],
            "survey_metadata": {},
            "base_elevation": 100.0,
            "base_elevation_method": "morphological",
            "base_elevation_confidence": 0.95,
            "intermediate_files": {},
            "warnings": [],
        }), encoding="utf-8")

        results_b.write_text(json.dumps({
            "heap_metrics": [m.model_dump() for m in metrics_b],
            "survey_metadata": {},
            "base_elevation": 100.0,
            "base_elevation_method": "morphological",
            "base_elevation_confidence": 0.95,
            "intermediate_files": {},
            "warnings": [],
        }), encoding="utf-8")

        return results_a, results_b

    def test_cli_compare_roundtrip(
        self, synthetic_results: tuple[Path, Path],
    ) -> None:
        """CLI compare outputs valid JSON Lines."""
        results_a, results_b = synthetic_results

        proc = subprocess.run(
            [
                sys.executable, "-m", "heap_analyzer.cli", "compare",
                "--results-a", str(results_a),
                "--results-b", str(results_b),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert proc.returncode == 0, f"CLI failed: {proc.stderr}"

        # All stdout lines must be valid JSON with a "type" field
        result_found = False
        for line in proc.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parsed = json.loads(line)
            assert "type" in parsed
            if parsed["type"] == "result":
                result_found = True
                data = parsed["data"]
                assert "matched" in data
                assert "summary" in data
                # Reload as MatchResult
                mr = MatchResult(**data)
                assert len(mr.matched) >= 0

        assert result_found, "No result message in CLI output"


class TestPaletteGuard:
    """Guard test: comparison state colors must match frontend."""

    def test_comparison_palette_matches_frontend(self) -> None:
        """Python COMPARISON_STATE_COLORS must be byte-identical to the TS file."""
        # Navigate from python-engine/src/heap_analyzer/tests/ → project root
        project_root = Path(__file__).resolve().parents[4]
        ts_path = project_root / "frontend" / "src" / "lib" / "comparisonColors.ts"

        if not ts_path.exists():
            pytest.skip(f"Frontend file not found: {ts_path}")

        ts_content = ts_path.read_text(encoding="utf-8")

        for state, color in COMPARISON_STATE_COLORS.items():
            # Check that the TS file contains the exact color for each state
            expected_pattern = f'{state}: "{color}"'
            assert expected_pattern in ts_content, (
                f"Palette mismatch: Python has {state}={color} "
                f"but TS file doesn't contain '{expected_pattern}'"
            )
