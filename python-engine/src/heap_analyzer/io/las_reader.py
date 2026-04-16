"""Chunked LAS/LAZ reader with CRS extraction.

Supports out-of-core processing for files larger than available RAM
via chunk_iterator() from laspy 2.x.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import laspy
import numpy as np
from pydantic import BaseModel

from heap_analyzer.utils.logging import get_stderr_logger

logger = get_stderr_logger(__name__)


class LasReaderError(Exception):
    """Raised for corrupted, empty, or unsupported LAS/LAZ files."""


class LasMetadata(BaseModel):
    """Metadata for a LAS/LAZ file."""

    bounds_min: tuple[float, float, float]
    bounds_max: tuple[float, float, float]
    num_points: int
    crs: str | None
    point_format: int
    point_count: int
    has_classification: bool
    file_size_bytes: int


class LasReader:
    """Chunked reader for LAS/LAZ files. Supports out-of-core processing."""

    def __init__(self, path: Path) -> None:
        """Open a LAS/LAZ file for reading.

        Args:
            path: Path to the LAS/LAZ file.

        Raises:
            FileNotFoundError: If the file does not exist.
            LasReaderError: If the file is corrupted or unsupported.
        """
        if not path.exists():
            raise FileNotFoundError(f"LAS file not found: {path}")

        self._path = path
        self._file_size = path.stat().st_size

        if self._file_size < 227:  # LAS 1.0 minimum header size
            raise LasReaderError(f"File too small to be a valid LAS file: {path}")

        try:
            self._reader = laspy.open(str(path))
        except Exception as exc:
            raise LasReaderError(
                f"Cannot open LAS file '{path}': {exc}"
            ) from exc

        self._header = self._reader.header
        self._metadata: LasMetadata | None = None

    def __enter__(self) -> LasReader:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the file handle."""
        if hasattr(self, "_reader") and self._reader is not None:
            self._reader.close()
            self._reader = None  # intentional close sentinel

    def get_metadata(self) -> LasMetadata:
        """Return file metadata without loading point data.

        Returns:
            LasMetadata with bounds, CRS, point count, etc.
        """
        if self._metadata is not None:
            return self._metadata

        h = self._header
        point_count = h.point_count

        if point_count == 0:
            raise LasReaderError(f"LAS file has zero points: {self._path}")

        has_classification = False
        # Check if classification dimension exists in point format
        dim_names = [d.name for d in h.point_format.dimensions]
        has_classification = "classification" in dim_names

        crs = self._extract_crs()

        self._metadata = LasMetadata(
            bounds_min=(float(h.x_min), float(h.y_min), float(h.z_min)),
            bounds_max=(float(h.x_max), float(h.y_max), float(h.z_max)),
            num_points=point_count,
            crs=crs,
            point_format=h.point_format.id,
            point_count=point_count,
            has_classification=has_classification,
            file_size_bytes=self._file_size,
        )
        return self._metadata

    def get_bounds(self) -> tuple[float, float, float, float]:
        """Return 2D bounds (min_x, min_y, max_x, max_y)."""
        meta = self.get_metadata()
        return (
            meta.bounds_min[0],
            meta.bounds_min[1],
            meta.bounds_max[0],
            meta.bounds_max[1],
        )

    def read_points(
        self, bounds: tuple[float, float, float, float] | None = None
    ) -> np.ndarray:
        """Read all points (or within optional 2D bounds).

        Args:
            bounds: Optional (min_x, min_y, max_x, max_y) spatial filter.

        Returns:
            Structured numpy array with fields: x, y, z, classification.
        """
        las = laspy.read(str(self._path))
        x = np.asarray(las.x, dtype=np.float64)
        y = np.asarray(las.y, dtype=np.float64)
        z = np.asarray(las.z, dtype=np.float64)

        dim_names = [d.name for d in las.point_format.dimensions]
        if "classification" in dim_names:
            classification = np.asarray(las.classification, dtype=np.uint8)
        else:
            classification = np.zeros(len(x), dtype=np.uint8)

        if bounds is not None:
            min_x, min_y, max_x, max_y = bounds
            mask = (x >= min_x) & (x <= max_x) & (y >= min_y) & (y <= max_y)
            x = x[mask]
            y = y[mask]
            z = z[mask]
            classification = classification[mask]

        result = np.empty(
            len(x),
            dtype=[
                ("x", np.float64),
                ("y", np.float64),
                ("z", np.float64),
                ("classification", np.uint8),
            ],
        )
        result["x"] = x
        result["y"] = y
        result["z"] = z
        result["classification"] = classification
        return result

    def iter_chunks(
        self, chunk_size: int = 1_000_000
    ) -> Iterator[np.ndarray]:
        """Yield chunks of points as structured arrays.

        Args:
            chunk_size: Number of points per chunk.

        Yields:
            Structured numpy arrays with fields: x, y, z, classification.
        """
        # Re-open for chunked iteration (reader may have been consumed)
        with laspy.open(str(self._path)) as reader:
            for points in reader.chunk_iterator(chunk_size):
                x = np.asarray(points.x, dtype=np.float64)
                y = np.asarray(points.y, dtype=np.float64)
                z = np.asarray(points.z, dtype=np.float64)

                dim_names = [d.name for d in points.point_format.dimensions]
                if "classification" in dim_names:
                    classification = np.asarray(
                        points.classification, dtype=np.uint8
                    )
                else:
                    classification = np.zeros(len(x), dtype=np.uint8)

                chunk = np.empty(
                    len(x),
                    dtype=[
                        ("x", np.float64),
                        ("y", np.float64),
                        ("z", np.float64),
                        ("classification", np.uint8),
                    ],
                )
                chunk["x"] = x
                chunk["y"] = y
                chunk["z"] = z
                chunk["classification"] = classification
                yield chunk

    def _extract_crs(self) -> str | None:
        """Extract CRS from LAS VLRs.

        Strategy:
        1. Try header.parse_crs() (laspy + pyproj integration)
        2. Return as 'EPSG:XXXXX' string if possible
        3. Return None if no CRS found

        Returns:
            CRS string like 'EPSG:32632' or None.
        """
        try:
            crs = self._header.parse_crs()
            if crs is not None:
                epsg = crs.to_epsg()
                if epsg is not None:
                    return f"EPSG:{epsg}"
                # Fallback: return WKT-derived name if EPSG not available
                return str(crs.to_wkt())
        except (ImportError, Exception) as exc:
            logger.debug("CRS extraction failed: %s", exc)

        return None
