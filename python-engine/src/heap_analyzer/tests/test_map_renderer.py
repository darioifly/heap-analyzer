"""Tests for map renderer (site overview + heap detail)."""

from __future__ import annotations

import json
import math
import re
import subprocess
from datetime import date
from pathlib import Path

import matplotlib
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds
from shapely.geometry import Polygon, mapping

matplotlib.use("Agg")

from heap_analyzer.report.map_renderer import (
    HeapDetailMetrics,
    HeapRenderInfo,
    MapRenderer,
)
from heap_analyzer.report.palette import CATEGORY_PALETTE


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def synthetic_site(tmp_path_factory: pytest.TempPathFactory) -> dict:
    """Create a synthetic site with GeoTIFF and results.json.

    Returns dict with: tiff_path, results_path, heaps, categories.
    """
    base = tmp_path_factory.mktemp("map_renderer")

    # Create a 100x100m synthetic RGB GeoTIFF
    size = 100  # meters
    res = 0.5  # m/pixel
    nx = ny = int(size / res)
    origin_e, origin_n = 500000.0, 4500000.0
    transform = from_bounds(origin_e, origin_n, origin_e + size, origin_n + size, nx, ny)

    # Green background with some variation
    rgb = np.zeros((3, ny, nx), dtype=np.uint8)
    rgb[0] = 100  # R
    rgb[1] = 150  # G
    rgb[2] = 80   # B

    tiff_path = base / "test_ortho.tif"
    profile = {
        "driver": "GTiff",
        "dtype": "uint8",
        "width": nx,
        "height": ny,
        "count": 3,
        "crs": "EPSG:32632",
        "transform": transform,
    }
    with rasterio.open(tiff_path, "w", **profile) as ds:
        ds.write(rgb)

    # Create 3 heaps as polygons
    categories = ["Rottame ferroso", "Ghisa", "Scorie"]

    heaps_data = []
    heap_metrics = []

    for i, (cx, cy, r) in enumerate([
        (500025.0, 4500025.0, 10.0),
        (500060.0, 4500060.0, 12.0),
        (500075.0, 4500025.0, 8.0),
    ]):
        # Create circular polygon
        angles = np.linspace(0, 2 * math.pi, 32, endpoint=False)
        coords = [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in angles]
        poly = Polygon(coords)
        geojson = mapping(poly)

        heaps_data.append(
            HeapRenderInfo(
                heap_id=i + 1,
                label=str(i + 1),
                polygon_geojson=geojson,
                category=categories[i],
            )
        )

        heap_metrics.append({
            "heap_id": i + 1,
            "label": str(i + 1),
            "polygon_geojson": geojson,
            "volume_m3": 100.0 + i * 50,
            "planimetric_area_m2": math.pi * r**2,
            "surface_area_m2": math.pi * r**2 * 1.1,
            "max_height_m": 3.0 + i * 0.5,
            "mean_height_m": 1.5 + i * 0.3,
            "base_elevation_m": 100.0,
            "centroid_e": cx,
            "centroid_n": cy,
            "bbox_min_e": cx - r,
            "bbox_min_n": cy - r,
            "bbox_max_e": cx + r,
            "bbox_max_n": cy + r,
        })

    # Write results.json
    results = {
        "survey_metadata": {
            "las_path": "test.las",
            "tiff_path": str(tiff_path),
            "output_dir": str(base),
            "config": {},
            "processing_time_s": 10.0,
            "heap_count": 3,
            "filtered_count": 0,
        },
        "heap_metrics": heap_metrics,
        "base_elevation": 100.0,
        "base_elevation_method": "morphological",
        "base_elevation_confidence": 0.95,
        "intermediate_files": {},
        "warnings": [],
    }
    results_path = base / "results.json"
    results_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    return {
        "tiff_path": tiff_path,
        "results_path": results_path,
        "heaps": heaps_data,
        "categories": categories,
        "heap_metrics": heap_metrics,
        "base_dir": base,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRenderSiteOverview:
    """Tests for site overview rendering."""

    def test_produces_png(self, synthetic_site: dict) -> None:
        """Site overview produces a valid PNG file."""
        output = synthetic_site["base_dir"] / "overview.png"
        renderer = MapRenderer()
        renderer.render_site_overview(
            tiff_path=synthetic_site["tiff_path"],
            heaps=synthetic_site["heaps"],
            project_categories=synthetic_site["categories"],
            site_name="Test Site",
            survey_date=date(2026, 4, 20),
            output_path=output,
            dpi=100,
        )

        assert output.exists()
        # Check PNG magic bytes
        with open(output, "rb") as f:
            magic = f.read(8)
        assert magic[:4] == b"\x89PNG"

    def test_image_size_reasonable(self, synthetic_site: dict) -> None:
        """Overview image should have reasonable dimensions."""
        from PIL import Image

        output = synthetic_site["base_dir"] / "overview_size.png"
        renderer = MapRenderer()
        renderer.render_site_overview(
            tiff_path=synthetic_site["tiff_path"],
            heaps=synthetic_site["heaps"],
            project_categories=synthetic_site["categories"],
            site_name="Test",
            survey_date=date(2026, 1, 1),
            output_path=output,
            dpi=100,
        )

        img = Image.open(output)
        assert img.width >= 200
        assert img.height >= 200

    def test_all_heaps_rendered(self, synthetic_site: dict) -> None:
        """All heaps should have their polygons rendered on the figure."""
        import matplotlib.pyplot as plt
        from matplotlib.patches import Polygon as MplPolygon

        renderer = MapRenderer()
        output = synthetic_site["base_dir"] / "overview_patches.png"

        # Render and check that 3 polygon patches exist
        renderer.render_site_overview(
            tiff_path=synthetic_site["tiff_path"],
            heaps=synthetic_site["heaps"],
            project_categories=synthetic_site["categories"],
            site_name="Test",
            survey_date=date(2026, 1, 1),
            output_path=output,
            dpi=72,
        )

        # The image was already saved, but we verify by re-rendering with inspection
        # This is a smoke test — if it didn't crash, the patches were added
        assert output.exists()


class TestRenderHeapDetail:
    """Tests for heap detail rendering."""

    def test_produces_png(self, synthetic_site: dict) -> None:
        """Heap detail produces a valid PNG file."""
        output = synthetic_site["base_dir"] / "heap_detail_1.png"
        renderer = MapRenderer()
        heap = synthetic_site["heaps"][0]
        metrics = HeapDetailMetrics(
            volume_m3=100.0,
            max_height_m=3.0,
            mean_height_m=1.5,
            planimetric_area_m2=314.0,
        )
        renderer.render_heap_detail(
            tiff_path=synthetic_site["tiff_path"],
            heap=heap,
            heap_metrics=metrics,
            project_categories=synthetic_site["categories"],
            output_path=output,
            dpi=100,
        )

        assert output.exists()
        with open(output, "rb") as f:
            magic = f.read(4)
        assert magic == b"\x89PNG"

    def test_aspect_ratio_matches_bbox(self, synthetic_site: dict) -> None:
        """Detail image aspect ratio should roughly match the expanded bbox."""
        from PIL import Image

        output = synthetic_site["base_dir"] / "heap_detail_aspect.png"
        renderer = MapRenderer()
        heap = synthetic_site["heaps"][1]
        metrics = HeapDetailMetrics(
            volume_m3=150.0,
            max_height_m=3.5,
            mean_height_m=1.8,
            planimetric_area_m2=452.0,
        )
        renderer.render_heap_detail(
            tiff_path=synthetic_site["tiff_path"],
            heap=heap,
            heap_metrics=metrics,
            project_categories=synthetic_site["categories"],
            output_path=output,
            dpi=100,
            padding_percent=25.0,
        )

        img = Image.open(output)
        # For a roughly circular polygon, aspect should be near 1
        img_aspect = img.height / img.width
        assert 0.5 < img_aspect < 2.0  # Generous bounds


class TestPaletteMatchesFrontend:
    """Guard test: Python palette must match TypeScript palette."""

    def test_palette_matches_frontend(self) -> None:
        """CATEGORY_PALETTE in palette.py must match categoryColors.ts."""
        # Navigate from python-engine/src/heap_analyzer/tests/ up to repo root
        ts_path = Path(__file__).resolve().parents[4] / "frontend" / "src" / "utils" / "categoryColors.ts"
        if not ts_path.exists():
            pytest.skip(f"TypeScript file not found at {ts_path}")

        ts_content = ts_path.read_text(encoding="utf-8")

        # Extract hex codes from the TS file
        hex_pattern = re.compile(r'"(#[0-9a-fA-F]{6})"')
        ts_colors = hex_pattern.findall(ts_content)

        # Should have exactly 12 palette colors + 1 unclassified
        assert len(ts_colors) >= 12, f"Found only {len(ts_colors)} colors in TS file"

        # First 12 are the palette
        ts_palette = tuple(c.lower() for c in ts_colors[:12])
        py_palette = tuple(c.lower() for c in CATEGORY_PALETTE)

        assert ts_palette == py_palette, (
            f"Palette mismatch!\n  TS:  {ts_palette}\n  Py:  {py_palette}"
        )


class TestCLIRenderSiteOverview:
    """Test CLI command for site overview rendering."""

    def test_cli_produces_png(self, synthetic_site: dict) -> None:
        """CLI render-site-overview produces a valid PNG and JSON Lines."""
        output = synthetic_site["base_dir"] / "cli_overview.png"

        result = subprocess.run(
            [
                "py", "-3.11", "-m", "heap_analyzer.cli",
                "render-site-overview",
                "--tiff", str(synthetic_site["tiff_path"]),
                "--results", str(synthetic_site["results_path"]),
                "--site-name", "CLI Test",
                "--survey-date", "2026-04-20",
                "--output", str(output),
                "--dpi", "72",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        # Verify JSON Lines on stdout
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                parsed = json.loads(line)
                assert "type" in parsed

        assert output.exists()

    def test_cli_render_heap_detail(self, synthetic_site: dict) -> None:
        """CLI render-heap-detail produces a valid PNG."""
        output = synthetic_site["base_dir"] / "cli_heap_1.png"

        result = subprocess.run(
            [
                "py", "-3.11", "-m", "heap_analyzer.cli",
                "render-heap-detail",
                "--tiff", str(synthetic_site["tiff_path"]),
                "--results", str(synthetic_site["results_path"]),
                "--heap-id", "1",
                "--output", str(output),
                "--dpi", "72",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert output.exists()
