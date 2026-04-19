"""Tests for cross-section profile extraction."""

from __future__ import annotations

import ast
import json
import math
import subprocess
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds

from heap_analyzer.processing.cross_section import _bilinear_sample, extract_profile


@pytest.fixture
def synthetic_rasters(tmp_path: Path) -> tuple[str, str, dict]:
    """Create synthetic DSM and DTM rasters with a cone heap.

    100x100m area, 0.5m resolution, centered at (500050, 4500050).
    DTM: flat at 100.0 m.
    DSM: flat at 100.0 m + cone at center (radius=20m, height=5m).

    Returns:
        Tuple of (dsm_path, dtm_path, metadata_dict).
    """
    size = 100  # meters
    res = 0.5
    nx = ny = int(size / res)

    origin_e, origin_n = 500000.0, 4500000.0
    transform = from_bounds(origin_e, origin_n, origin_e + size, origin_n + size, nx, ny)

    dtm_data = np.full((ny, nx), 100.0, dtype=np.float32)
    dsm_data = np.full((ny, nx), 100.0, dtype=np.float32)

    cone_center_px = nx // 2
    cone_center_py = ny // 2
    cone_radius_px = int(20 / res)
    cone_height = 5.0

    for row in range(ny):
        for col in range(nx):
            dist = math.sqrt((col - cone_center_px) ** 2 + (row - cone_center_py) ** 2)
            if dist < cone_radius_px:
                h = cone_height * (1.0 - dist / cone_radius_px)
                dsm_data[row, col] = 100.0 + h

    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "width": nx,
        "height": ny,
        "count": 1,
        "crs": "EPSG:32632",
        "transform": transform,
    }

    dsm_path = str(tmp_path / "dsm.tif")
    dtm_path = str(tmp_path / "dtm.tif")

    with rasterio.open(dsm_path, "w", **profile) as ds:
        ds.write(dsm_data, 1)
    with rasterio.open(dtm_path, "w", **profile) as ds:
        ds.write(dtm_data, 1)

    meta = {
        "origin_e": origin_e,
        "origin_n": origin_n,
        "size": size,
        "cone_center": (origin_e + size / 2, origin_n + size / 2),
        "cone_radius": 20.0,
        "cone_height": cone_height,
    }

    return dsm_path, dtm_path, meta


class TestBilinearSample:
    """Tests for the bilinear interpolation helper."""

    def test_exact_corner(self) -> None:
        """Exact corner pixel returns exact value."""
        arr = np.array([[1.0, 2.0], [3.0, 4.0]])
        assert _bilinear_sample(arr, 0, 0) == pytest.approx(1.0)
        assert _bilinear_sample(arr, 0, 1) == pytest.approx(2.0)
        assert _bilinear_sample(arr, 1, 0) == pytest.approx(3.0)
        assert _bilinear_sample(arr, 1, 1) == pytest.approx(4.0)

    def test_center_interpolation(self) -> None:
        """Center of 4 pixels returns the mean."""
        arr = np.array([[1.0, 2.0], [3.0, 4.0]])
        assert _bilinear_sample(arr, 0.5, 0.5) == pytest.approx(2.5)

    def test_out_of_bounds(self) -> None:
        """Out-of-bounds coordinates return NaN."""
        arr = np.array([[1.0, 2.0], [3.0, 4.0]])
        assert np.isnan(_bilinear_sample(arr, -0.1, 0))
        assert np.isnan(_bilinear_sample(arr, 0, 5.0))


class TestExtractProfile:
    """Tests for extract_profile function."""

    def test_basic_profile_through_cone(self, synthetic_rasters: tuple[str, str, dict]) -> None:
        """Line through cone center produces expected peak height."""
        dsm_path, dtm_path, meta = synthetic_rasters
        cx, cy = meta["cone_center"]
        r = meta["cone_radius"]

        line = [(cx - r - 2, cy), (cx + r + 2, cy)]
        result = extract_profile(dsm_path, dtm_path, line)

        assert result["num_samples"] > 10
        assert result["length"] == pytest.approx(2 * (r + 2), abs=0.2)
        assert result["max_height"] == pytest.approx(meta["cone_height"], abs=0.5)

    def test_section_area_positive(self, synthetic_rasters: tuple[str, str, dict]) -> None:
        """Section area through cone should be positive."""
        dsm_path, dtm_path, meta = synthetic_rasters
        cx, cy = meta["cone_center"]
        r = meta["cone_radius"]

        line = [(cx - r - 2, cy), (cx + r + 2, cy)]
        result = extract_profile(dsm_path, dtm_path, line)

        assert result["section_area"] > 0
        # Cone cross-section area ≈ r * h (triangle)
        expected_area = r * meta["cone_height"]
        assert result["section_area"] == pytest.approx(expected_area, rel=0.2)

    def test_profile_outside_heap(self, synthetic_rasters: tuple[str, str, dict]) -> None:
        """Line far from cone should show flat profile."""
        dsm_path, dtm_path, meta = synthetic_rasters
        origin_e = meta["origin_e"]
        origin_n = meta["origin_n"]

        line = [(origin_e + 5, origin_n + 5), (origin_e + 95, origin_n + 5)]
        result = extract_profile(dsm_path, dtm_path, line)

        assert result["max_height"] < 0.5
        assert result["section_area"] < 1.0

    def test_outside_raster_returns_nans(self, synthetic_rasters: tuple[str, str, dict]) -> None:
        """Line completely outside raster extent produces all-null profile."""
        dsm_path, dtm_path, _ = synthetic_rasters
        line = [(-10000.0, -10000.0), (-9000.0, -9000.0)]
        result = extract_profile(dsm_path, dtm_path, line)

        assert result["section_area"] == 0.0
        assert all(v is None for v in result["dsm_z"])

    def test_too_few_points_raises(self, synthetic_rasters: tuple[str, str, dict]) -> None:
        """Line with <2 points raises ValueError."""
        dsm_path, dtm_path, _ = synthetic_rasters
        with pytest.raises(ValueError, match="at least 2"):
            extract_profile(dsm_path, dtm_path, [(0, 0)])

    def test_zero_length_raises(self, synthetic_rasters: tuple[str, str, dict]) -> None:
        """Same point twice raises ValueError."""
        dsm_path, dtm_path, _ = synthetic_rasters
        with pytest.raises(ValueError, match="zero length"):
            extract_profile(dsm_path, dtm_path, [(100, 100), (100, 100)])

    def test_sample_spacing_controls_count(self, synthetic_rasters: tuple[str, str, dict]) -> None:
        """Smaller spacing → more samples."""
        dsm_path, dtm_path, meta = synthetic_rasters
        cx, cy = meta["cone_center"]
        line = [(cx - 10, cy), (cx + 10, cy)]

        r1 = extract_profile(dsm_path, dtm_path, line, sample_spacing=1.0)
        r2 = extract_profile(dsm_path, dtm_path, line, sample_spacing=0.1)

        assert r2["num_samples"] > r1["num_samples"] * 5

    def test_dsm_dtm_consistency(self, synthetic_rasters: tuple[str, str, dict]) -> None:
        """All valid points have consistent dsm_z and dtm_z values."""
        dsm_path, dtm_path, meta = synthetic_rasters
        cx, cy = meta["cone_center"]
        line = [(cx - 10, cy), (cx + 10, cy)]
        result = extract_profile(dsm_path, dtm_path, line, sample_spacing=0.5)

        for dsm, dtm in zip(result["dsm_z"], result["dtm_z"]):
            if dsm is not None and dtm is not None:
                # DSM should be >= DTM (we have a heap on flat ground)
                assert dsm >= dtm - 0.01

    def test_json_serializable(self, synthetic_rasters: tuple[str, str, dict]) -> None:
        """Result is fully JSON-serializable (no NaN, no numpy types)."""
        dsm_path, dtm_path, meta = synthetic_rasters
        cx, cy = meta["cone_center"]
        line = [(cx - 10, cy), (cx + 10, cy)]
        result = extract_profile(dsm_path, dtm_path, line)

        serialized = json.dumps(result)
        assert "NaN" not in serialized
        assert "Infinity" not in serialized


class TestCLICrossSection:
    """Test CLI cross-section command."""

    def test_cli_help(self) -> None:
        """CLI shows help for cross-section command."""
        result = subprocess.run(
            ["py", "-3.11", "-m", "heap_analyzer.cli", "cross-section", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "--dsm" in result.stdout
        assert "--dtm" in result.stdout
        assert "--line" in result.stdout

    def test_cli_emits_json_lines(self, synthetic_rasters: tuple[str, str, dict]) -> None:
        """CLI outputs valid JSON Lines with type field."""
        dsm_path, dtm_path, meta = synthetic_rasters
        cx, cy = meta["cone_center"]
        line_str = f"{cx - 10},{cy};{cx + 10},{cy}"

        result = subprocess.run(
            [
                "py", "-3.11", "-m", "heap_analyzer.cli", "cross-section",
                "--dsm", dsm_path,
                "--dtm", dtm_path,
                "--line", line_str,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                parsed = json.loads(line)
                assert "type" in parsed

    def test_cli_result_has_profile(self, synthetic_rasters: tuple[str, str, dict]) -> None:
        """CLI result contains profile data."""
        dsm_path, dtm_path, meta = synthetic_rasters
        cx, cy = meta["cone_center"]
        line_str = f"{cx - 10},{cy};{cx + 10},{cy}"

        result = subprocess.run(
            [
                "py", "-3.11", "-m", "heap_analyzer.cli", "cross-section",
                "--dsm", dsm_path,
                "--dtm", dtm_path,
                "--line", line_str,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        for line in result.stdout.strip().split("\n"):
            parsed = json.loads(line)
            if parsed["type"] == "result":
                assert "distance" in parsed["data"]
                assert "dsm_z" in parsed["data"]
                assert "dtm_z" in parsed["data"]
                assert parsed["data"]["max_height"] > 0
                break
        else:
            pytest.fail("No result message found in CLI output")


class TestNoBarePrint:
    """Verify no print() in production code."""

    def test_no_print_in_cross_section(self) -> None:
        """cross_section.py has no bare print() calls."""
        source_file = Path(__file__).parent.parent / "processing" / "cross_section.py"
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "print":
                    pytest.fail(
                        f"Bare print() at line {node.lineno} in cross_section.py"
                    )
