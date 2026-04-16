"""Tiled GeoTIFF reader with CRS comparison.

Supports out-of-core processing for rasters larger than available RAM
via windowed reading from rasterio.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import numpy as np
import rasterio
from pydantic import BaseModel
from rasterio.windows import Window

from heap_analyzer.utils.logging import get_stderr_logger

logger = get_stderr_logger(__name__)


class TiffReaderError(Exception):
    """Raised for invalid or unsupported GeoTIFF files."""


class TiffMetadata(BaseModel):
    """Metadata for a GeoTIFF file."""

    bounds: tuple[float, float, float, float]  # min_x, min_y, max_x, max_y
    width: int
    height: int
    crs: str | None  # "EPSG:XXXXX" or None
    resolution: tuple[float, float]  # (x_res, y_res) in CRS units
    band_count: int
    dtype: str  # e.g. "uint8", "float32"
    file_size_bytes: int


class TiffReader:
    """Tiled reader for GeoTIFF. Supports out-of-core for files > RAM."""

    def __init__(self, path: Path) -> None:
        """Open a GeoTIFF file for reading.

        Args:
            path: Path to the GeoTIFF file.

        Raises:
            FileNotFoundError: If the file does not exist.
            TiffReaderError: If the file is not a valid raster.
        """
        if not path.exists():
            raise FileNotFoundError(f"TIFF file not found: {path}")

        self._path = path
        self._file_size = path.stat().st_size

        try:
            self._dataset = rasterio.open(str(path))
        except Exception as exc:
            raise TiffReaderError(
                f"Cannot open TIFF file '{path}': {exc}"
            ) from exc

        self._metadata: TiffMetadata | None = None

    def __enter__(self) -> TiffReader:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the dataset."""
        if hasattr(self, "_dataset") and self._dataset is not None:
            self._dataset.close()
            self._dataset = None  # intentional close sentinel

    def get_metadata(self) -> TiffMetadata:
        """Return file metadata.

        Returns:
            TiffMetadata with bounds, CRS, resolution, dimensions.
        """
        if self._metadata is not None:
            return self._metadata

        ds = self._dataset
        b = ds.bounds
        transform = ds.transform

        crs_str: str | None = None
        if ds.crs is not None:
            epsg = ds.crs.to_epsg()
            crs_str = f"EPSG:{epsg}" if epsg is not None else ds.crs.to_wkt()

        self._metadata = TiffMetadata(
            bounds=(float(b.left), float(b.bottom), float(b.right), float(b.top)),
            width=ds.width,
            height=ds.height,
            crs=crs_str,
            resolution=(abs(float(transform.a)), abs(float(transform.e))),
            band_count=ds.count,
            dtype=str(ds.dtypes[0]),
            file_size_bytes=self._file_size,
        )
        return self._metadata

    def read_tile(self, window: Window) -> np.ndarray:
        """Read a single window.

        Args:
            window: Rasterio Window specifying the region to read.

        Returns:
            Array of shape (bands, height, width).
        """
        result: np.ndarray = self._dataset.read(window=window)
        return result

    def iter_tiles(
        self, tile_size: int = 1024
    ) -> Iterator[tuple[Window, np.ndarray]]:
        """Iterate over tiles of size tile_size x tile_size.

        Args:
            tile_size: Tile dimension in pixels.

        Yields:
            (Window, array) tuples covering the full raster.
        """
        ds = self._dataset
        for row_off in range(0, ds.height, tile_size):
            height = min(tile_size, ds.height - row_off)
            for col_off in range(0, ds.width, tile_size):
                width = min(tile_size, ds.width - col_off)
                window = Window(col_off, row_off, width, height)
                data = ds.read(window=window)
                yield window, data

    def read_region(
        self, bounds: tuple[float, float, float, float]
    ) -> np.ndarray:
        """Read by geographic bounds.

        Args:
            bounds: (min_x, min_y, max_x, max_y) in CRS units.

        Returns:
            Array of shape (bands, height, width).
        """
        from rasterio.windows import from_bounds

        window = from_bounds(
            bounds[0], bounds[1], bounds[2], bounds[3],
            transform=self._dataset.transform,
        )
        # Clamp to dataset dimensions
        window = window.intersection(
            Window(0, 0, self._dataset.width, self._dataset.height)
        )
        result: np.ndarray = self._dataset.read(window=window)
        return result

    def check_crs_compatibility(self, other_crs: str | None) -> bool:
        """Check if this raster's CRS matches another CRS string.

        Args:
            other_crs: CRS string like 'EPSG:32632' or None.

        Returns:
            True if both CRS are set and equal.
        """
        my_crs = self.get_metadata().crs
        if my_crs is None or other_crs is None:
            return False
        return my_crs == other_crs
