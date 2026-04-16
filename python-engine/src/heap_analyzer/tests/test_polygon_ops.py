"""Tests for polygon split and merge operations (F3.S01)."""

import json
import subprocess
import sys

import pytest

from heap_analyzer.processing.polygon_ops import merge_polygons, split_polygon_by_line


def _square(x: float, y: float, size: float) -> dict:
    """Create a GeoJSON square polygon."""
    return {
        "type": "Polygon",
        "coordinates": [[
            [x, y],
            [x + size, y],
            [x + size, y + size],
            [x, y + size],
            [x, y],
        ]],
    }


class TestSplitPolygon:
    """Tests for split_polygon_by_line."""

    def test_horizontal_split_produces_two_parts(self) -> None:
        """Square + horizontal line → 2 rectangles."""
        from shapely.geometry import shape

        square = _square(0, 0, 10)
        line = {"type": "LineString", "coordinates": [[-1, 5], [11, 5]]}
        parts = split_polygon_by_line(square, line)
        assert len(parts) == 2
        # Both parts should have area ~50
        for part in parts:
            area = shape(part).area
            assert abs(area - 50.0) < 1.0, f"Part area {area} != ~50"

    def test_diagonal_split_produces_two_triangles(self) -> None:
        """Square + diagonal line → 2 triangles."""
        square = _square(0, 0, 10)
        line = {
            "type": "LineString",
            "coordinates": [[-1, -1], [11, 11]],
        }
        parts = split_polygon_by_line(square, line)
        assert len(parts) == 2
        from shapely.geometry import shape
        total_area = sum(shape(p).area for p in parts)
        assert abs(total_area - 100.0) < 1.0

    def test_non_intersecting_line_raises(self) -> None:
        """Line outside polygon → ValueError."""
        square = _square(0, 0, 10)
        line = {"type": "LineString", "coordinates": [[20, 20], [30, 30]]}
        with pytest.raises(ValueError, match="does not intersect"):
            split_polygon_by_line(square, line)

    def test_tangent_line_raises(self) -> None:
        """Line touching boundary only → ValueError (no >= 2 parts)."""
        square = _square(0, 0, 10)
        # Line along one edge
        line = {"type": "LineString", "coordinates": [[0, 0], [10, 0]]}
        with pytest.raises(ValueError, match="did not produce"):
            split_polygon_by_line(square, line)

    def test_splitter_must_be_linestring(self) -> None:
        """Polygon as splitter → ValueError."""
        square = _square(0, 0, 10)
        with pytest.raises(ValueError, match="must be a LineString"):
            split_polygon_by_line(square, _square(2, 2, 3))


class TestMergePolygons:
    """Tests for merge_polygons."""

    def test_merge_two_touching_squares(self) -> None:
        """Two adjacent squares → single rectangle, area = sum."""
        sq1 = _square(0, 0, 10)
        sq2 = _square(10, 0, 10)
        merged = merge_polygons([sq1, sq2])
        from shapely.geometry import shape
        area = shape(merged).area
        assert abs(area - 200.0) < 1.0

    def test_merge_overlapping_squares(self) -> None:
        """Two overlapping squares → union, area < sum."""
        sq1 = _square(0, 0, 10)
        sq2 = _square(5, 0, 10)
        merged = merge_polygons([sq1, sq2])
        from shapely.geometry import shape
        area = shape(merged).area
        expected = 10 * 15  # 150, since overlap is 5x10=50
        assert abs(area - expected) < 1.0

    def test_merge_one_raises(self) -> None:
        """Single polygon → ValueError."""
        with pytest.raises(ValueError, match="requires >= 2"):
            merge_polygons([_square(0, 0, 10)])

    def test_merge_three_polygons(self) -> None:
        """Three touching squares merge correctly."""
        squares = [_square(i * 10, 0, 10) for i in range(3)]
        merged = merge_polygons(squares)
        from shapely.geometry import shape
        area = shape(merged).area
        assert abs(area - 300.0) < 1.0


class TestPolygonOpsCli:
    """CLI subprocess tests."""

    def test_split_cli(self) -> None:
        """CLI split-polygon emits JSON Lines result."""
        square = _square(0, 0, 10)
        line = {"type": "LineString", "coordinates": [[-1, 5], [11, 5]]}
        result = subprocess.run(
            [
                sys.executable, "-m", "heap_analyzer.cli",
                "split-polygon",
                "--polygon-json", json.dumps(square),
                "--line-json", json.dumps(line),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        lines = [
            ln.strip()
            for ln in result.stdout.strip().splitlines()
            if ln.strip()
        ]
        assert len(lines) == 1
        msg = json.loads(lines[0])
        assert msg["type"] == "result"
        assert len(msg["data"]["parts"]) == 2

    def test_merge_cli(self) -> None:
        """CLI merge-polygons emits JSON Lines result."""
        polygons = [_square(0, 0, 10), _square(10, 0, 10)]
        result = subprocess.run(
            [
                sys.executable, "-m", "heap_analyzer.cli",
                "merge-polygons",
                "--polygons-json", json.dumps(polygons),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        lines = [
            ln.strip()
            for ln in result.stdout.strip().splitlines()
            if ln.strip()
        ]
        assert len(lines) == 1
        msg = json.loads(lines[0])
        assert msg["type"] == "result"
        assert "merged" in msg["data"]
