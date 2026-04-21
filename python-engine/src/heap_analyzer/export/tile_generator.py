"""Generate XYZ tile pyramids from GeoTIFF in source CRS (NO Mercator reprojection).

Output structure:
    output_dir/
        metadata.json
        {z}/{x}/{y}.png
"""

from __future__ import annotations

import json
import math
import sys
from collections.abc import Callable
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import Window
from PIL import Image
from pydantic import BaseModel


class TileMetadata(BaseModel):
    """Metadata for the generated tile pyramid."""

    tiles_dir: str
    min_zoom: int
    max_zoom: int
    tile_size: int
    crs: str
    bounds: tuple[float, float, float, float]  # min_x, min_y, max_x, max_y
    origin: tuple[float, float]  # top-left (min_x, max_y)
    resolutions: list[float]  # meters/pixel per zoom level


def generate_tiles(
    tiff_path: Path,
    output_dir: Path,
    tile_size: int = 256,
    min_zoom: int = 0,
    max_zoom: int | None = None,
    progress_callback: Callable[[int, str], None] | None = None,
) -> TileMetadata:
    """Generate XYZ pyramid tiles in source raster's CRS.

    Args:
        tiff_path: Path to input GeoTIFF.
        output_dir: Directory for tile output.
        tile_size: Pixel size of each tile (default 256).
        min_zoom: Minimum zoom level (default 0).
        max_zoom: Maximum zoom level (auto-computed if None).
        progress_callback: Optional callback(percent, message).

    Returns:
        TileMetadata with pyramid information.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    with rasterio.open(str(tiff_path)) as src:
        crs = str(src.crs)
        bounds = (src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top)
        width = src.width
        height = src.height
        band_count = min(src.count, 3)  # Use first 3 bands for RGB

        extent_w = bounds[2] - bounds[0]
        extent_h = bounds[3] - bounds[1]
        max_extent = max(extent_w, extent_h)

        # Auto-compute max_zoom: at max_zoom, tile pixels roughly match source resolution
        if max_zoom is None:
            max_dim = max(width, height)
            max_zoom = max(0, math.ceil(math.log2(max_dim / tile_size)))

        # Compute resolutions per zoom level
        # Zoom 0: one tile covers the entire extent
        resolutions: list[float] = []
        for z in range(max_zoom + 1):
            res = max_extent / (tile_size * (2 ** z))
            resolutions.append(res)

        origin = (bounds[0], bounds[3])  # top-left corner

        total_tiles = sum((2 ** z) ** 2 for z in range(min_zoom, max_zoom + 1))
        tiles_done = 0

        for z in range(min_zoom, max_zoom + 1):
            n_tiles = 2 ** z
            # Tiles are SQUARE in geographic space so that res × tile_size
            # maps back to the declared resolution. For non-square rasters the
            # tiles outside the actual extent are simply transparent. Using
            # separate tile_extent_x / tile_extent_y (as before) would stretch
            # the ortho, misaligning any overlay — e.g. a 321×239 m Acciaieria
            # ortho showed polygons shifted ~10 m north because the y-axis was
            # compressed by 239/321 = 0.74.
            tile_extent = max_extent / n_tiles

            zoom_dir = output_dir / str(z)
            zoom_dir.mkdir(exist_ok=True)

            for tx in range(n_tiles):
                col_dir = zoom_dir / str(tx)
                col_dir.mkdir(exist_ok=True)

                for ty in range(n_tiles):
                    # Geographic bounds of this tile (square, tile_extent × tile_extent).
                    tile_min_x = bounds[0] + tx * tile_extent
                    tile_max_x = tile_min_x + tile_extent
                    tile_max_y = bounds[3] - ty * tile_extent
                    tile_min_y = tile_max_y - tile_extent

                    # Full tile pixel range in SOURCE pixels (may extend past raster).
                    full_col_off_f, full_row_off_f = ~src.transform * (
                        tile_min_x, tile_max_y
                    )
                    full_col_end_f, full_row_end_f = ~src.transform * (
                        tile_max_x, tile_min_y
                    )
                    full_col_span = full_col_end_f - full_col_off_f
                    full_row_span = full_row_end_f - full_row_off_f

                    # Read window = intersection with raster bounds.
                    read_col_off = max(0, int(round(full_col_off_f)))
                    read_row_off = max(0, int(round(full_row_off_f)))
                    read_col_end = min(width, int(round(full_col_end_f)))
                    read_row_end = min(height, int(round(full_row_end_f)))
                    win_width = read_col_end - read_col_off
                    win_height = read_row_end - read_row_off

                    if win_width <= 0 or win_height <= 0:
                        # Tile falls entirely outside the raster — transparent.
                        img = Image.new("RGBA", (tile_size, tile_size), (0, 0, 0, 0))
                    else:
                        # Where the intersection lands in the OUTPUT 256×256 tile.
                        # Proportional to the full tile span so the raster's pixels
                        # map 1:1 to their geographic position inside the tile —
                        # anything not covered stays transparent. (The previous
                        # implementation stretched the intersection to fill 256×256,
                        # which misaligned polygon overlays at every zoom level
                        # whenever the raster was non-square.)
                        out_col_off = int(
                            round(
                                (read_col_off - full_col_off_f) / full_col_span * tile_size
                            )
                        )
                        out_row_off = int(
                            round(
                                (read_row_off - full_row_off_f) / full_row_span * tile_size
                            )
                        )
                        out_col_end = int(
                            round(
                                (read_col_end - full_col_off_f) / full_col_span * tile_size
                            )
                        )
                        out_row_end = int(
                            round(
                                (read_row_end - full_row_off_f) / full_row_span * tile_size
                            )
                        )
                        # Clamp to the 256×256 canvas — rounding can push endpoints
                        # one pixel past tile_size when the read window aligns
                        # exactly with the raster edge.
                        out_col_off = max(0, min(tile_size, out_col_off))
                        out_row_off = max(0, min(tile_size, out_row_off))
                        out_col_end = max(out_col_off, min(tile_size, out_col_end))
                        out_row_end = max(out_row_off, min(tile_size, out_row_end))
                        out_w = max(1, out_col_end - out_col_off)
                        out_h = max(1, out_row_end - out_row_off)

                        window = Window(read_col_off, read_row_off, win_width, win_height)
                        data = src.read(
                            list(range(1, band_count + 1)),
                            window=window,
                            out_shape=(band_count, out_h, out_w),
                            resampling=Resampling.bilinear,
                        )

                        if data.dtype != np.uint8:
                            dmin = np.nanmin(data)
                            dmax = np.nanmax(data)
                            if dmax > dmin:
                                data = ((data - dmin) / (dmax - dmin) * 255).astype(
                                    np.uint8
                                )
                            else:
                                data = np.zeros_like(data, dtype=np.uint8)

                        if band_count == 1:
                            patch = np.stack([data[0], data[0], data[0]], axis=-1)
                        elif band_count == 3:
                            patch = np.moveaxis(data, 0, -1)
                        else:
                            patch = np.moveaxis(data[:3], 0, -1)

                        # Paste the proportionally-sized patch onto a transparent
                        # RGBA 256×256 canvas at the correct offset.
                        canvas = np.zeros((tile_size, tile_size, 4), dtype=np.uint8)
                        canvas[
                            out_row_off : out_row_off + out_h,
                            out_col_off : out_col_off + out_w,
                            :3,
                        ] = patch
                        canvas[
                            out_row_off : out_row_off + out_h,
                            out_col_off : out_col_off + out_w,
                            3,
                        ] = 255
                        img = Image.fromarray(canvas, "RGBA")

                    tile_path = col_dir / f"{ty}.png"
                    img.save(str(tile_path), "PNG")

                    tiles_done += 1

            if progress_callback:
                pct = int(tiles_done / total_tiles * 100)
                progress_callback(pct, f"Zoom {z}/{max_zoom} completato")

    # Write metadata
    metadata = TileMetadata(
        tiles_dir=str(output_dir),
        min_zoom=min_zoom,
        max_zoom=max_zoom,
        tile_size=tile_size,
        crs=crs,
        bounds=bounds,
        origin=origin,
        resolutions=resolutions,
    )

    metadata_path = output_dir / "metadata.json"
    metadata_path.write_text(metadata.model_dump_json(indent=2), encoding="utf-8")

    return metadata
