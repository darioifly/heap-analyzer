"""Tests for GeoTIFF tiled reader."""

import tempfile
import tracemalloc
from pathlib import Path

import numpy as np
import pytest
import rasterio

from heap_analyzer.io.tiff_reader import TiffMetadata, TiffReader, TiffReaderError

TEST_DATA_DIR = Path(__file__).resolve().parents[4] / "test-data"
TIF_PATH = TEST_DATA_DIR / "test.tif"


class TestTiffMetadata:
    """Verify metadata extraction from synthetic GeoTIFF."""

    def test_metadata_synthetic(self) -> None:
        with TiffReader(TIF_PATH) as reader:
            meta = reader.get_metadata()
            assert isinstance(meta, TiffMetadata)
            assert meta.width == 2000
            assert meta.height == 2000
            assert meta.crs == "EPSG:32632"
            assert meta.band_count == 3

    def test_resolution(self) -> None:
        with TiffReader(TIF_PATH) as reader:
            meta = reader.get_metadata()
            assert abs(meta.resolution[0] - 0.10) < 0.01
            assert abs(meta.resolution[1] - 0.10) < 0.01


class TestReadTile:
    """Verify windowed reading."""

    def test_read_tile(self) -> None:
        from rasterio.windows import Window

        with TiffReader(TIF_PATH) as reader:
            data = reader.read_tile(Window(0, 0, 256, 256))
            assert data.shape == (3, 256, 256)

    def test_iter_tiles(self) -> None:
        with TiffReader(TIF_PATH) as reader:
            tiles = list(reader.iter_tiles(tile_size=512))
            # 2000 / 512 = ceil to 4 tiles per axis = 16 tiles
            assert len(tiles) == 16
            # Verify full coverage: sum of tile pixels == full raster pixels
            total_pixels = sum(w.width * w.height for w, _ in tiles)
            assert total_pixels == 2000 * 2000

    def test_read_region_by_bounds(self) -> None:
        # Read a 50m x 50m region
        bounds = (500050.0, 5000050.0, 500100.0, 5000100.0)
        with TiffReader(TIF_PATH) as reader:
            data = reader.read_region(bounds)
            assert data.shape[0] == 3  # 3 bands
            # At 0.10 m/px, 50m = 500 pixels
            assert abs(data.shape[1] - 500) <= 1
            assert abs(data.shape[2] - 500) <= 1


class TestCrsCompatibility:
    """Verify CRS comparison."""

    def test_crs_compatibility_match(self) -> None:
        with TiffReader(TIF_PATH) as reader:
            assert reader.check_crs_compatibility("EPSG:32632") is True

    def test_crs_compatibility_mismatch(self) -> None:
        with TiffReader(TIF_PATH) as reader:
            assert reader.check_crs_compatibility("EPSG:4326") is False

    def test_crs_compatibility_none(self) -> None:
        with TiffReader(TIF_PATH) as reader:
            assert reader.check_crs_compatibility(None) is False


class TestErrorHandling:
    """Verify error conditions."""

    def test_invalid_file(self, tmp_path: Path) -> None:
        garbage = tmp_path / "garbage.tif"
        garbage.write_bytes(b"x" * 100)
        with pytest.raises(TiffReaderError):
            TiffReader(garbage)

    def test_missing_file(self) -> None:
        with pytest.raises(FileNotFoundError):
            TiffReader(Path("/nonexistent/file.tif"))

    def test_chunked_memory(self) -> None:
        tracemalloc.start()
        with TiffReader(TIF_PATH) as reader:
            for _, data in reader.iter_tiles(tile_size=512):
                _ = data.mean()
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peak_mb = peak / (1024 * 1024)
        assert peak_mb < 100, f"Peak memory {peak_mb:.1f} MB exceeds 100 MB"
