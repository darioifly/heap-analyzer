"""Tests for LAS/LAZ chunked reader."""

import json
import tracemalloc
from pathlib import Path

import numpy as np
import pytest

from heap_analyzer.io.las_reader import LasMetadata, LasReader, LasReaderError

TEST_DATA_DIR = Path(__file__).resolve().parents[4] / "test-data"
LAS_PATH = TEST_DATA_DIR / "test.las"
GT_PATH = TEST_DATA_DIR / "ground_truth.json"


def _load_ground_truth() -> dict:
    return json.loads(GT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ground_truth() -> dict:
    return _load_ground_truth()


class TestLasMetadata:
    """Verify metadata extraction from synthetic LAS."""

    def test_metadata_synthetic(self, ground_truth: dict) -> None:
        gt_bounds = ground_truth["bounds"]
        with LasReader(LAS_PATH) as reader:
            meta = reader.get_metadata()
            assert isinstance(meta, LasMetadata)
            assert abs(meta.bounds_min[0] - gt_bounds["min_e"]) < 1.0
            assert abs(meta.bounds_min[1] - gt_bounds["min_n"]) < 1.0
            assert abs(meta.bounds_max[0] - gt_bounds["max_e"]) < 1.0
            assert abs(meta.bounds_max[1] - gt_bounds["max_n"]) < 1.0
            assert meta.num_points > 2_000_000
            assert meta.crs == "EPSG:32632"

    def test_get_bounds_2d(self, ground_truth: dict) -> None:
        gt_bounds = ground_truth["bounds"]
        with LasReader(LAS_PATH) as reader:
            b = reader.get_bounds()
            assert len(b) == 4
            assert abs(b[0] - gt_bounds["min_e"]) < 1.0
            assert abs(b[1] - gt_bounds["min_n"]) < 1.0
            assert abs(b[2] - gt_bounds["max_e"]) < 1.0
            assert abs(b[3] - gt_bounds["max_n"]) < 1.0


class TestReadPoints:
    """Verify point reading."""

    def test_read_all_points(self) -> None:
        with LasReader(LAS_PATH) as reader:
            meta = reader.get_metadata()
            points = reader.read_points()
            assert len(points) == meta.num_points
            assert "x" in points.dtype.names
            assert "y" in points.dtype.names
            assert "z" in points.dtype.names

    def test_read_with_bounds(self) -> None:
        sub_bounds = (500040.0, 5000040.0, 500060.0, 5000060.0)
        with LasReader(LAS_PATH) as reader:
            points = reader.read_points(bounds=sub_bounds)
            assert len(points) > 0
            assert np.all(points["x"] >= sub_bounds[0])
            assert np.all(points["x"] <= sub_bounds[2])
            assert np.all(points["y"] >= sub_bounds[1])
            assert np.all(points["y"] <= sub_bounds[3])


class TestChunkedReading:
    """Verify chunked iteration."""

    def test_iter_chunks(self) -> None:
        with LasReader(LAS_PATH) as reader:
            meta = reader.get_metadata()
            total = 0
            chunk_count = 0
            for chunk in reader.iter_chunks(chunk_size=500_000):
                total += len(chunk)
                chunk_count += 1
                assert "x" in chunk.dtype.names
            assert total == meta.num_points
            assert chunk_count >= 2  # Should be multiple chunks

    def test_chunked_memory(self) -> None:
        tracemalloc.start()
        with LasReader(LAS_PATH) as reader:
            for chunk in reader.iter_chunks(chunk_size=100_000):
                _ = chunk["z"].mean()
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peak_mb = peak / (1024 * 1024)
        assert peak_mb < 100, f"Peak memory {peak_mb:.1f} MB exceeds 100 MB"


class TestErrorHandling:
    """Verify error conditions."""

    def test_corrupted_file(self, tmp_path: Path) -> None:
        garbage = tmp_path / "garbage.las"
        garbage.write_bytes(b"x" * 100)
        with pytest.raises(LasReaderError):
            LasReader(garbage)

    def test_missing_file(self) -> None:
        with pytest.raises(FileNotFoundError):
            LasReader(Path("/nonexistent/file.las"))

    def test_context_manager(self) -> None:
        with LasReader(LAS_PATH) as reader:
            _ = reader.get_metadata()
        # After exiting, reader should be closed
        assert reader._reader is None
