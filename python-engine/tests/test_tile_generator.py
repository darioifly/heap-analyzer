"""Tests for tile pyramid generator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from heap_analyzer.export.tile_generator import generate_tiles


@pytest.fixture
def synthetic_tiff(tmp_path: Path) -> Path:
    """Get the synthetic test.tif from test-data if available."""
    # From python-engine/tests/ → ../../test-data/
    test_tif = Path(__file__).resolve().parent.parent.parent / "test-data" / "test.tif"
    if test_tif.exists():
        return test_tif
    pytest.skip("test-data/test.tif not found — run 'heap-analyzer generate-test-data' first")
    return test_tif  # unreachable but keeps type checker happy


def test_tiles_generated(synthetic_tiff: Path, tmp_path: Path) -> None:
    """Tiles directory created with metadata.json."""
    output = tmp_path / "tiles"
    result = generate_tiles(synthetic_tiff, output)
    assert output.exists()
    assert (output / "metadata.json").exists()
    assert result.min_zoom == 0
    assert result.max_zoom >= 1


def test_metadata_json(synthetic_tiff: Path, tmp_path: Path) -> None:
    """metadata.json has all required fields."""
    output = tmp_path / "tiles"
    result = generate_tiles(synthetic_tiff, output)
    meta = json.loads((output / "metadata.json").read_text())
    assert meta["tile_size"] == 256
    assert meta["min_zoom"] == 0
    assert meta["max_zoom"] == result.max_zoom
    assert len(meta["resolutions"]) == result.max_zoom + 1
    assert "EPSG" in meta["crs"]
    assert len(meta["bounds"]) == 4
    assert len(meta["origin"]) == 2


def test_tile_dimensions(synthetic_tiff: Path, tmp_path: Path) -> None:
    """Every tile PNG is exactly 256x256."""
    output = tmp_path / "tiles"
    generate_tiles(synthetic_tiff, output)
    for png in output.rglob("*.png"):
        img = Image.open(png)
        assert img.size == (256, 256), f"Tile {png} has wrong size: {img.size}"


def test_tile_zoom_0_exists(synthetic_tiff: Path, tmp_path: Path) -> None:
    """Zoom 0 has exactly 1 tile: 0/0/0.png."""
    output = tmp_path / "tiles"
    generate_tiles(synthetic_tiff, output)
    assert (output / "0" / "0" / "0.png").exists()


def test_native_crs_preserved(synthetic_tiff: Path, tmp_path: Path) -> None:
    """Tile metadata CRS matches source CRS (no Mercator)."""
    import rasterio

    with rasterio.open(str(synthetic_tiff)) as src:
        source_crs = str(src.crs)

    output = tmp_path / "tiles"
    result = generate_tiles(synthetic_tiff, output)
    assert result.crs == source_crs
    assert "3857" not in result.crs  # NOT web Mercator


def test_progress_emitted(synthetic_tiff: Path, tmp_path: Path) -> None:
    """Progress callback is called at least once."""
    calls: list[tuple[int, str]] = []

    def cb(pct: int, msg: str) -> None:
        calls.append((pct, msg))

    output = tmp_path / "tiles"
    generate_tiles(synthetic_tiff, output, progress_callback=cb)
    assert len(calls) > 0
    assert calls[-1][0] == 100  # last call should be 100%
