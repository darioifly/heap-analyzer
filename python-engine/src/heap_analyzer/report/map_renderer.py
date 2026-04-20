"""Map rendering for PDF reports: site overview and heap detail images.

Uses matplotlib to render GeoTIFF rasters with polygon overlays,
numbered labels, legends, scale bars, and north arrows.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import matplotlib
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.patches import Polygon as MplPolygon
from pydantic import BaseModel
from shapely import wkt
from shapely.geometry import shape as shapely_shape

from heap_analyzer.report.palette import (
    UNCLASSIFIED_COLOR,
    category_color,
)
from heap_analyzer.utils.logging import get_stderr_logger

matplotlib.use("Agg")

logger = get_stderr_logger(__name__)


class HeapRenderInfo(BaseModel):
    """Minimal heap info needed for rendering."""

    heap_id: int
    label: str | None = None
    polygon_wkt: str | None = None
    polygon_geojson: dict | None = None  # type: ignore[type-arg]
    category: str | None = None


class HeapDetailMetrics(BaseModel):
    """Metrics displayed on heap detail image."""

    volume_m3: float
    max_height_m: float
    mean_height_m: float
    planimetric_area_m2: float


def _hex_to_rgba(hex_color: str, alpha: float = 1.0) -> tuple[float, float, float, float]:
    """Convert hex color string to RGBA tuple (0-1 range)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255
    return (r, g, b, alpha)


def _pick_nice_length(extent_width: float, target_fraction: float = 0.15) -> float:
    """Pick a nice round scale bar length (~target_fraction of extent width)."""
    raw = extent_width * target_fraction
    nice_values = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000]
    return min(nice_values, key=lambda v: abs(v - raw))


def _read_rgb(
    tiff_path: Path,
    max_width_px: int = 2400,
) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    """Read a GeoTIFF as an RGB array, downsampling if too large.

    Args:
        tiff_path: Path to GeoTIFF.
        max_width_px: Maximum output width in pixels.

    Returns:
        Tuple of (rgb array HxWx3 uint8, extent [left, right, bottom, top]).
    """
    with rasterio.open(tiff_path) as ds:
        bounds = ds.bounds
        extent = (bounds.left, bounds.right, bounds.bottom, bounds.top)

        # Determine output shape
        if ds.width > max_width_px:
            scale = max_width_px / ds.width
            out_width = max_width_px
            out_height = max(1, int(ds.height * scale))
        else:
            out_width = ds.width
            out_height = ds.height

        out_shape = (out_height, out_width)

        if ds.count >= 3:
            # RGB bands
            r = ds.read(1, out_shape=out_shape)
            g = ds.read(2, out_shape=out_shape)
            b = ds.read(3, out_shape=out_shape)
            rgb = np.stack([r, g, b], axis=-1)
        elif ds.count == 1:
            # Grayscale fallback
            gray = ds.read(1, out_shape=out_shape)
            rgb = np.stack([gray, gray, gray], axis=-1)
        else:
            # 2 bands — use first as grayscale
            gray = ds.read(1, out_shape=out_shape)
            rgb = np.stack([gray, gray, gray], axis=-1)

        # Normalize to uint8 if needed
        if rgb.dtype != np.uint8:
            if rgb.max() > 0:
                rgb = (rgb / rgb.max() * 255).astype(np.uint8)
            else:
                rgb = rgb.astype(np.uint8)

    return rgb, extent


def _get_polygon_coords(heap: HeapRenderInfo) -> list[tuple[float, float]] | None:
    """Extract polygon exterior coordinates from WKT or GeoJSON."""
    try:
        if heap.polygon_wkt:
            geom = wkt.loads(heap.polygon_wkt)
        elif heap.polygon_geojson:
            geom = shapely_shape(heap.polygon_geojson)
        else:
            return None

        if geom.geom_type == "MultiPolygon":
            # Use the largest polygon
            geom = max(geom.geoms, key=lambda g: g.area)

        return list(geom.exterior.coords)
    except Exception:  # noqa: BLE001
        logger.warning("Failed to parse polygon for heap %d", heap.heap_id)
        return None


def _draw_scale_bar(
    ax: plt.Axes,
    extent: tuple[float, float, float, float],
    position: str = "bottom-right",
) -> None:
    """Draw a manual scale bar on the axes.

    Args:
        ax: Matplotlib axes.
        extent: (left, right, bottom, top) in CRS units (meters).
        position: Where to place the bar.
    """
    left, right, bottom, top = extent
    extent_width = right - left
    extent_height = top - bottom

    bar_length = _pick_nice_length(extent_width)

    # Position: bottom-right with some padding
    pad_x = extent_width * 0.03
    pad_y = extent_height * 0.04
    bar_y = bottom + pad_y
    bar_x_end = right - pad_x
    bar_x_start = bar_x_end - bar_length

    # Draw bar
    bar_height = extent_height * 0.006
    ax.plot(
        [bar_x_start, bar_x_end], [bar_y, bar_y],
        color="black", linewidth=2.5, solid_capstyle="butt",
    )
    # End ticks
    for x in [bar_x_start, bar_x_end]:
        ax.plot(
            [x, x], [bar_y - bar_height, bar_y + bar_height],
            color="black", linewidth=2,
        )
    # Label
    label = f"{int(bar_length)} m" if bar_length >= 1 else f"{bar_length:.1f} m"
    ax.text(
        (bar_x_start + bar_x_end) / 2, bar_y + bar_height * 3,
        label, ha="center", va="bottom", fontsize=8, fontweight="bold",
        color="black",
        path_effects=[pe.withStroke(linewidth=2.5, foreground="white")],
    )


def _draw_north_arrow(
    ax: plt.Axes,
    extent: tuple[float, float, float, float],
) -> None:
    """Draw a north arrow in the top-right corner.

    Args:
        ax: Matplotlib axes.
        extent: (left, right, bottom, top) in CRS units.
    """
    left, right, bottom, top = extent
    extent_width = right - left
    extent_height = top - bottom

    # Position: top-right
    arrow_x = right - extent_width * 0.04
    arrow_base_y = top - extent_height * 0.12
    arrow_tip_y = top - extent_height * 0.04

    ax.annotate(
        "", xy=(arrow_x, arrow_tip_y), xytext=(arrow_x, arrow_base_y),
        arrowprops=dict(arrowstyle="-|>", color="black", lw=2),
    )
    ax.text(
        arrow_x, arrow_base_y - extent_height * 0.02,
        "N", ha="center", va="top", fontsize=10, fontweight="bold",
        color="black",
        path_effects=[pe.withStroke(linewidth=2.5, foreground="white")],
    )


class MapRenderer:
    """Renders map images for the PDF report."""

    def __init__(self, palette: list[str] | None = None) -> None:
        """Initialize renderer.

        Args:
            palette: Optional custom palette. Defaults to CATEGORY_PALETTE.
        """
        from heap_analyzer.report.palette import CATEGORY_PALETTE
        self._palette = list(palette) if palette else list(CATEGORY_PALETTE)

    def render_site_overview(
        self,
        tiff_path: Path,
        heaps: list[HeapRenderInfo],
        project_categories: list[str],
        site_name: str,
        survey_date: date,
        output_path: Path,
        dpi: int = 150,
        max_width_px: int = 2400,
    ) -> Path:
        """Render the site overview image with all heaps colored by category.

        Args:
            tiff_path: Path to GeoTIFF (ortophoto or DSM).
            heaps: List of heaps to overlay.
            project_categories: Ordered category list for coloring.
            site_name: Site name for the title.
            survey_date: Survey date for the title.
            output_path: Output PNG path.
            dpi: Output resolution.
            max_width_px: Max width for raster reading.

        Returns:
            Output path.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        rgb, extent = _read_rgb(tiff_path, max_width_px)
        left, right, bottom, top = extent

        # Figure size: match aspect ratio
        aspect = (top - bottom) / (right - left) if (right - left) > 0 else 1
        fig_width = 16
        fig_height = fig_width * aspect + 1.2  # extra for title
        fig, ax = plt.subplots(1, 1, figsize=(fig_width, fig_height))

        # Show raster
        ax.imshow(rgb, extent=[left, right, bottom, top], origin="upper", aspect="equal")

        # Track categories seen for legend
        seen_categories: dict[str | None, str] = {}

        for heap in heaps:
            coords = _get_polygon_coords(heap)
            if not coords:
                continue

            color_hex = category_color(heap.category, project_categories)

            # Draw filled polygon
            poly = MplPolygon(
                coords,
                closed=True,
                fill=True,
                facecolor=_hex_to_rgba(color_hex, 0.35),
                edgecolor=_hex_to_rgba(color_hex, 1.0),
                linewidth=2.0,
                zorder=5,
            )
            ax.add_patch(poly)

            # Label at centroid
            if heap.polygon_wkt:
                geom = wkt.loads(heap.polygon_wkt)
            elif heap.polygon_geojson:
                geom = shapely_shape(heap.polygon_geojson)
            else:
                continue

            centroid = geom.centroid
            display_label = heap.label or str(heap.heap_id)
            ax.annotate(
                display_label,
                xy=(centroid.x, centroid.y),
                ha="center", va="center",
                fontsize=9, fontweight="bold",
                color="white",
                path_effects=[pe.withStroke(linewidth=2.5, foreground="black")],
                zorder=10,
            )

            # Track for legend
            cat_key = heap.category
            if cat_key not in seen_categories:
                seen_categories[cat_key] = color_hex

        # Legend
        legend_handles = []
        for cat_name in project_categories:
            if cat_name in seen_categories:
                color = seen_categories[cat_name]
                legend_handles.append(
                    mpatches.Patch(
                        facecolor=_hex_to_rgba(color, 0.5),
                        edgecolor=_hex_to_rgba(color, 1.0),
                        label=cat_name,
                    )
                )
        # Add unclassified if any
        if None in seen_categories:
            legend_handles.append(
                mpatches.Patch(
                    facecolor=_hex_to_rgba(UNCLASSIFIED_COLOR, 0.5),
                    edgecolor=_hex_to_rgba(UNCLASSIFIED_COLOR, 1.0),
                    label="Non classificato",
                )
            )

        if legend_handles:
            ax.legend(
                handles=legend_handles,
                loc="lower left",
                fontsize=9,
                framealpha=0.85,
                edgecolor="gray",
            )

        # Scale bar
        _draw_scale_bar(ax, extent)

        # North arrow
        _draw_north_arrow(ax, extent)

        # Title
        date_str = survey_date.strftime("%d/%m/%Y")
        ax.set_title(
            f"{site_name} \u2014 Rilievo del {date_str}",
            fontsize=14, fontweight="bold",
            pad=12,
        )

        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.tick_params(labelsize=7)

        plt.tight_layout()
        fig.savefig(
            str(output_path), dpi=dpi,
            bbox_inches="tight", facecolor="white",
        )
        plt.close(fig)

        logger.debug("Site overview saved: %s", output_path)
        return output_path

    def render_heap_detail(
        self,
        tiff_path: Path,
        heap: HeapRenderInfo,
        heap_metrics: HeapDetailMetrics,
        project_categories: list[str],
        output_path: Path,
        dpi: int = 200,
        padding_percent: float = 25.0,
    ) -> Path:
        """Render a detail image for a single heap.

        Args:
            tiff_path: Path to GeoTIFF.
            heap: Heap to render.
            heap_metrics: Metrics for annotation overlay.
            project_categories: For category coloring.
            output_path: Output PNG path.
            dpi: Output resolution.
            padding_percent: Extra padding around the polygon bounds.

        Returns:
            Output path.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        coords = _get_polygon_coords(heap)
        if not coords:
            logger.warning("No polygon for heap %d, skipping detail render", heap.heap_id)
            return output_path

        # Compute crop bounds from polygon
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        poly_left, poly_right = min(xs), max(xs)
        poly_bottom, poly_top = min(ys), max(ys)

        pad_x = (poly_right - poly_left) * padding_percent / 100
        pad_y = (poly_top - poly_bottom) * padding_percent / 100

        crop_left = poly_left - pad_x
        crop_right = poly_right + pad_x
        crop_bottom = poly_bottom - pad_y
        crop_top = poly_top + pad_y

        # Read windowed raster
        with rasterio.open(tiff_path) as ds:
            # Convert crop bounds to pixel coordinates
            row_start, col_start = ds.index(crop_left, crop_top)
            row_end, col_end = ds.index(crop_right, crop_bottom)

            # Clamp to raster bounds
            row_start = max(0, min(row_start, ds.height - 1))
            row_end = max(0, min(row_end, ds.height - 1))
            col_start = max(0, min(col_start, ds.width - 1))
            col_end = max(0, min(col_end, ds.width - 1))

            if row_start > row_end:
                row_start, row_end = row_end, row_start
            if col_start > col_end:
                col_start, col_end = col_end, col_start

            window = rasterio.windows.Window(
                col_start, row_start,
                col_end - col_start + 1,
                row_end - row_start + 1,
            )

            # Compute the actual extent of the window
            win_transform = ds.window_transform(window)
            win_left = win_transform.c
            win_top = win_transform.f
            win_right = win_left + window.width * abs(win_transform.a)
            win_bottom = win_top + window.height * win_transform.e  # e is negative

            extent = (win_left, win_right, win_bottom, win_top)

            if ds.count >= 3:
                r = ds.read(1, window=window)
                g = ds.read(2, window=window)
                b = ds.read(3, window=window)
                rgb = np.stack([r, g, b], axis=-1)
            else:
                gray = ds.read(1, window=window)
                rgb = np.stack([gray, gray, gray], axis=-1)

            if rgb.dtype != np.uint8:
                if rgb.max() > 0:
                    rgb = (rgb / rgb.max() * 255).astype(np.uint8)
                else:
                    rgb = rgb.astype(np.uint8)

        # Figure
        width_m = extent[1] - extent[0]
        height_m = extent[3] - extent[2]
        aspect = height_m / width_m if width_m > 0 else 1
        fig_width = 8
        fig_height = fig_width * aspect
        fig, ax = plt.subplots(1, 1, figsize=(fig_width, fig_height))

        ext = [extent[0], extent[1], extent[2], extent[3]]
        ax.imshow(rgb, extent=ext, origin="upper", aspect="equal")

        # Overlay polygon
        color_hex = category_color(heap.category, project_categories)
        poly = MplPolygon(
            coords,
            closed=True,
            fill=True,
            facecolor=_hex_to_rgba(color_hex, 0.25),
            edgecolor=_hex_to_rgba(color_hex, 1.0),
            linewidth=2.5,
            zorder=5,
        )
        ax.add_patch(poly)

        # Annotations in top-left corner
        display_label = heap.label or str(heap.heap_id)
        annotation_lines = [
            f"Cumulo #{display_label}",
            f"V: {heap_metrics.volume_m3:.1f} m\u00b3",
            f"h max: {heap_metrics.max_height_m:.2f} m",
            f"Cat: {heap.category or 'N/C'}",
        ]
        annotation_text = "\n".join(annotation_lines)

        ax.text(
            extent[0] + width_m * 0.02,
            extent[3] - height_m * 0.02,
            annotation_text,
            fontsize=9, fontweight="bold",
            color="white", va="top",
            path_effects=[pe.withStroke(linewidth=2.5, foreground="black")],
            zorder=10,
        )

        # Small scale bar
        _draw_scale_bar(ax, extent)

        # Small north arrow
        _draw_north_arrow(ax, extent)

        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.tick_params(labelsize=6)

        plt.tight_layout()
        fig.savefig(
            str(output_path), dpi=dpi,
            bbox_inches="tight", facecolor="white",
        )
        plt.close(fig)

        logger.debug("Heap detail saved: %s", output_path)
        return output_path
