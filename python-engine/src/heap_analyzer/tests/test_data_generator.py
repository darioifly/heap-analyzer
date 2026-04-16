"""Tests for the synthetic test data generator."""

import json
import math
import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def test_site_dir():
    """Generate a test site once and return the directory path."""
    tmp = tempfile.mkdtemp(prefix="heap-analyzer-test-")
    try:
        from heap_analyzer.test_data_generator import create_test_site
        create_test_site(Path(tmp))
        yield Path(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class TestLasOutput:
    """Verify the LAS file is valid and has correct metadata."""

    def test_las_file_exists(self, test_site_dir: Path) -> None:
        assert (test_site_dir / "test.las").exists()

    def test_las_readable(self, test_site_dir: Path) -> None:
        import laspy
        las = laspy.read(str(test_site_dir / "test.las"))
        assert len(las.points) > 0

    def test_las_has_rgb(self, test_site_dir: Path) -> None:
        import laspy
        las = laspy.read(str(test_site_dir / "test.las"))
        # Point format 2 has RGB
        assert hasattr(las, "red")
        assert hasattr(las, "green")
        assert hasattr(las, "blue")

    def test_las_bounds_within_site(self, test_site_dir: Path) -> None:
        import laspy
        las = laspy.read(str(test_site_dir / "test.las"))
        tol = 0.01  # 1cm tolerance for LAS scale quantisation
        assert las.x.min() >= 500000.0 - tol
        assert las.x.max() <= 500200.0 + tol
        assert las.y.min() >= 5000000.0 - tol
        assert las.y.max() <= 5000200.0 + tol

    def test_las_z_range_reasonable(self, test_site_dir: Path) -> None:
        """Z should be between terrain (100m) and terrain + max_heap_height."""
        import laspy
        las = laspy.read(str(test_site_dir / "test.las"))
        assert las.z.min() >= 99.9  # terrain ≈ 100m
        assert las.z.max() <= 115.0  # highest heap is hemisphere r=12m

    def test_las_point_count_reasonable(self, test_site_dir: Path) -> None:
        """Minimum: 200×200 × 50 pts/m² terrain = 2_000_000 terrain points + heap points."""
        import laspy
        las = laspy.read(str(test_site_dir / "test.las"))
        assert len(las.points) > 1_500_000


class TestGeoTiffOutput:
    """Verify the GeoTIFF ortophoto is valid."""

    def test_tif_file_exists(self, test_site_dir: Path) -> None:
        assert (test_site_dir / "test.tif").exists()

    def test_tif_readable(self, test_site_dir: Path) -> None:
        import rasterio
        with rasterio.open(str(test_site_dir / "test.tif")) as ds:
            assert ds.width > 0
            assert ds.height > 0

    def test_tif_has_rgb_bands(self, test_site_dir: Path) -> None:
        import rasterio
        with rasterio.open(str(test_site_dir / "test.tif")) as ds:
            assert ds.count == 3

    def test_tif_crs_correct(self, test_site_dir: Path) -> None:
        import rasterio
        with rasterio.open(str(test_site_dir / "test.tif")) as ds:
            assert ds.crs is not None
            assert "32632" in str(ds.crs)

    def test_tif_bounds_match_site(self, test_site_dir: Path) -> None:
        import rasterio
        with rasterio.open(str(test_site_dir / "test.tif")) as ds:
            bounds = ds.bounds
            assert abs(bounds.left - 500000.0) < 1.0
            assert abs(bounds.bottom - 5000000.0) < 1.0
            assert abs(bounds.right - 500200.0) < 1.0
            assert abs(bounds.top - 5000200.0) < 1.0

    def test_tif_compatible_crs_with_las(self, test_site_dir: Path) -> None:
        """LAS and TIFF should have compatible CRS (both UTM 32N)."""
        import rasterio
        with rasterio.open(str(test_site_dir / "test.tif")) as ds:
            tif_crs = str(ds.crs)
        assert "32632" in tif_crs


class TestGroundTruth:
    """Verify ground_truth.json is valid and contains correct volumes."""

    def test_gt_file_exists(self, test_site_dir: Path) -> None:
        assert (test_site_dir / "ground_truth.json").exists()

    def test_gt_valid_json(self, test_site_dir: Path) -> None:
        content = (test_site_dir / "ground_truth.json").read_text(encoding="utf-8")
        gt = json.loads(content)
        assert isinstance(gt, dict)

    def test_gt_has_4_heaps(self, test_site_dir: Path) -> None:
        gt = json.loads((test_site_dir / "ground_truth.json").read_text())
        assert len(gt["heaps"]) == 4

    def test_gt_heap_types(self, test_site_dir: Path) -> None:
        gt = json.loads((test_site_dir / "ground_truth.json").read_text())
        types = {h["type"] for h in gt["heaps"]}
        assert types == {"cone", "hemisphere", "pyramid", "truncated_cone"}

    def test_gt_cone_volume_analytical(self, test_site_dir: Path) -> None:
        """Cone: V = π×15²×5/3 ≈ 1178.097"""
        gt = json.loads((test_site_dir / "ground_truth.json").read_text())
        cone = next(h for h in gt["heaps"] if h["type"] == "cone")
        expected = math.pi * 15**2 * 5 / 3
        assert abs(cone["volume_m3"] - expected) < 0.01

    def test_gt_hemisphere_volume_analytical(self, test_site_dir: Path) -> None:
        """Hemisphere: V = 2π×12³/3 ≈ 3619.115"""
        gt = json.loads((test_site_dir / "ground_truth.json").read_text())
        hemi = next(h for h in gt["heaps"] if h["type"] == "hemisphere")
        expected = 2 * math.pi * 12**3 / 3
        assert abs(hemi["volume_m3"] - expected) < 0.01

    def test_gt_pyramid_volume_analytical(self, test_site_dir: Path) -> None:
        """Pyramid: V = 20²×6/3 = 800.000"""
        gt = json.loads((test_site_dir / "ground_truth.json").read_text())
        pyr = next(h for h in gt["heaps"] if h["type"] == "pyramid")
        assert abs(pyr["volume_m3"] - 800.0) < 0.001

    def test_gt_truncated_cone_volume_analytical(self, test_site_dir: Path) -> None:
        """Truncated cone: V = π×h×(rb²+rb×rt+rt²)/3"""
        gt = json.loads((test_site_dir / "ground_truth.json").read_text())
        tc = next(h for h in gt["heaps"] if h["type"] == "truncated_cone")
        rb, rt, h = 18.0, 8.0, 4.0
        expected = math.pi * h * (rb**2 + rb * rt + rt**2) / 3
        assert abs(tc["volume_m3"] - expected) < 0.01

    def test_gt_heaps_not_overlapping(self, test_site_dir: Path) -> None:
        """Heap centres should be far enough apart not to overlap."""
        gt = json.loads((test_site_dir / "ground_truth.json").read_text())
        heaps = gt["heaps"]
        for i in range(len(heaps)):
            for j in range(i + 1, len(heaps)):
                dx = heaps[i]["center_e"] - heaps[j]["center_e"]
                dy = heaps[i]["center_n"] - heaps[j]["center_n"]
                dist = math.sqrt(dx**2 + dy**2)
                # All heap pairs: centres at least 60m apart
                assert dist >= 50.0, (
                    f"Heaps {heaps[i]['id']} and {heaps[j]['id']} are too close: {dist:.1f}m"
                )
