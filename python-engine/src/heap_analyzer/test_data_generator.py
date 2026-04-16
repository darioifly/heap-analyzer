"""Synthetic test dataset generator.

Creates a LAS point cloud, GeoTIFF ortophoto, and ground_truth.json for a
simulated 200m × 200m site with 4 geometric heaps of known analytical volumes.

CRS: EPSG:32632 (UTM Zone 32N)
Origin: E=500000, N=5000000
Terrain: flat at 100.0 m elevation

Heaps (analytically exact volumes):
  1. Cone:           center=(50,50),  r=15m, h=5m  → V=πr²h/3 ≈ 1178.097 m³
  2. Hemisphere:     center=(150,50), r=12m         → V=2πr³/3 ≈ 3619.115 m³
  3. Pyramid:        center=(50,150), base 20×20m, h=6m → V=b²h/3 = 800.0 m³
  4. Truncated cone: center=(150,150), r_b=18m, r_t=8m, h=4m → V≈2345.699 m³
"""

from __future__ import annotations

import json
import math
import sys
from collections.abc import Callable
from pathlib import Path

import numpy as np

from heap_analyzer.utils.logging import emit_progress, get_stderr_logger

logger = get_stderr_logger(__name__)

# ---------------------------------------------------------------------------
# Analytical volume constants
# ---------------------------------------------------------------------------

CONE_R = 15.0
CONE_H = 5.0
CONE_VOL = math.pi * CONE_R**2 * CONE_H / 3  # ≈ 1178.097

HEMI_R = 12.0
HEMI_VOL = 2 * math.pi * HEMI_R**3 / 3  # ≈ 3619.115

PYRAMID_BASE = 20.0
PYRAMID_H = 6.0
PYRAMID_VOL = PYRAMID_BASE**2 * PYRAMID_H / 3  # = 800.0

TCONE_RB = 18.0
TCONE_RT = 8.0
TCONE_H = 4.0
TCONE_VOL = math.pi * TCONE_H * (TCONE_RB**2 + TCONE_RB * TCONE_RT + TCONE_RT**2) / 3  # ≈ 2345.699

# Site parameters
ORIGIN_E = 500000.0
ORIGIN_N = 5000000.0
SITE_SIZE = 200.0  # metres
TERRAIN_ELEV = 100.0  # m a.s.l.
CRS_WKT = 'EPSG:32632'

# Point densities
TERRAIN_DENSITY = 50   # pts / m²
HEAP_DENSITY = 200     # pts / m²


# ---------------------------------------------------------------------------
# Height functions for each heap shape
# ---------------------------------------------------------------------------

def _cone_height(
    x: np.ndarray, y: np.ndarray, cx: float, cy: float, r: float, h: float
) -> np.ndarray:
    """Height of a cone above terrain (0 outside radius)."""
    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    above = np.maximum(0.0, h * (1.0 - dist / r))
    return above


def _hemisphere_height(x: np.ndarray, y: np.ndarray, cx: float, cy: float, r: float) -> np.ndarray:
    """Height of a hemisphere above terrain (0 outside radius)."""
    dist2 = (x - cx) ** 2 + (y - cy) ** 2
    inside = dist2 < r**2
    h = np.zeros_like(x, dtype=float)
    h[inside] = np.sqrt(r**2 - dist2[inside])
    return h


def _pyramid_height(
    x: np.ndarray, y: np.ndarray, cx: float, cy: float, base: float, h: float
) -> np.ndarray:
    """Height of a square-base pyramid above terrain."""
    half = base / 2.0
    dx = np.abs(x - cx)
    dy = np.abs(y - cy)
    factor = np.maximum(0.0, 1.0 - np.maximum(dx, dy) / half)
    return h * factor


def _truncated_cone_height(
    x: np.ndarray, y: np.ndarray, cx: float, cy: float, rb: float, rt: float, h: float
) -> np.ndarray:
    """Height of a truncated cone (frustum) above terrain."""
    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    # At dist=0: height = h. At dist=rb: height = 0.
    # Radius at height z: r(z) = rt + (rb - rt) * (1 - z/h)
    # Invert: z(dist) when rb > rt. Linear profile assuming r decreases linearly.
    slope = h / (rb - rt) if rb > rt else 0.0
    z = np.maximum(0.0, h - slope * np.maximum(0.0, dist - rt))
    z[dist >= rb] = 0.0
    return z


# ---------------------------------------------------------------------------
# Terrain point cloud + heap points
# ---------------------------------------------------------------------------

def _generate_terrain_points(
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate flat terrain points (50 pts/m²) for the full 200×200 m site.

    Returns (x, y, z, color_label) arrays.
    """
    n = int(SITE_SIZE * SITE_SIZE * TERRAIN_DENSITY)
    x = ORIGIN_E + rng.uniform(0, SITE_SIZE, n)
    y = ORIGIN_N + rng.uniform(0, SITE_SIZE, n)
    z = np.full(n, TERRAIN_ELEV)
    color = np.zeros(n, dtype=np.int8)  # 0 = terrain
    return x, y, z, color


def _generate_heap_points(
    heap_id: int,
    cx_local: float,
    cy_local: float,
    radius: float,
    height_fn: Callable[[np.ndarray, np.ndarray], np.ndarray],
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate heap point cloud within a circular bounding region.

    Args:
        heap_id: Integer label (1-4).
        cx_local: Heap centre in local coords (0-200 m).
        cy_local: Heap centre in local coords.
        radius: Bounding radius for point generation.
        height_fn: Callable(x_arr, y_arr) → z_above_terrain array.
        rng: numpy random generator.

    Returns:
        (x, y, z, color_label) with UTM coordinates.
    """
    area = math.pi * radius**2
    n = int(area * HEAP_DENSITY * 2)  # oversample, then filter inside heap

    x_local = cx_local + rng.uniform(-radius, radius, n)
    y_local = cy_local + rng.uniform(-radius, radius, n)

    h_above = height_fn(x_local, y_local)
    inside = h_above > 0.0
    x_local = x_local[inside]
    y_local = y_local[inside]
    h_above = h_above[inside]

    x_utm = ORIGIN_E + x_local
    y_utm = ORIGIN_N + y_local
    z = TERRAIN_ELEV + h_above
    color = np.full(len(x_utm), heap_id, dtype=np.int8)
    return x_utm, y_utm, z, color


# ---------------------------------------------------------------------------
# RGB colour map  (RGB per heap_id; 0=terrain)
# ---------------------------------------------------------------------------

COLORS_RGB = {
    0: (139, 90, 43),   # terrain: brown
    1: (220, 50, 50),   # cone: red
    2: (50, 100, 220),  # hemisphere: blue
    3: (50, 200, 50),   # pyramid: green
    4: (220, 200, 50),  # truncated cone: yellow
}


# ---------------------------------------------------------------------------
# GeoTIFF ortophoto generation
# ---------------------------------------------------------------------------

def _generate_geotiff(
    all_x: np.ndarray,
    all_y: np.ndarray,
    all_color: np.ndarray,
    output_path: Path,
    resolution: float = 0.10,
) -> None:
    """Create a synthetic RGB GeoTIFF ortophoto.

    Each pixel is coloured by the dominant heap_id at that cell.
    """
    import rasterio
    from rasterio.transform import from_bounds

    width = int(SITE_SIZE / resolution)
    height = int(SITE_SIZE / resolution)

    # Build RGB image: default terrain colour
    r_band = np.full((height, width), COLORS_RGB[0][0], dtype=np.uint8)
    g_band = np.full((height, width), COLORS_RGB[0][1], dtype=np.uint8)
    b_band = np.full((height, width), COLORS_RGB[0][2], dtype=np.uint8)

    # Assign heap colours (heaps painted last → appear on top)
    for heap_id in [1, 2, 3, 4]:
        mask = all_color == heap_id
        if not np.any(mask):
            continue
        # Convert UTM coords to pixel indices
        col_idx = ((all_x[mask] - ORIGIN_E) / resolution).astype(int)
        row_idx = (height - 1 - ((all_y[mask] - ORIGIN_N) / resolution).astype(int))
        valid = (col_idx >= 0) & (col_idx < width) & (row_idx >= 0) & (row_idx < height)
        col_idx = col_idx[valid]
        row_idx = row_idx[valid]
        cr, cg, cb = COLORS_RGB[heap_id]
        r_band[row_idx, col_idx] = cr
        g_band[row_idx, col_idx] = cg
        b_band[row_idx, col_idx] = cb

    transform = from_bounds(
        west=ORIGIN_E,
        south=ORIGIN_N,
        east=ORIGIN_E + SITE_SIZE,
        north=ORIGIN_N + SITE_SIZE,
        width=width,
        height=height,
    )

    with rasterio.open(
        output_path,
        'w',
        driver='GTiff',
        height=height,
        width=width,
        count=3,
        dtype=np.uint8,
        crs=CRS_WKT,
        transform=transform,
    ) as dst:
        dst.write(r_band, 1)
        dst.write(g_band, 2)
        dst.write(b_band, 3)

    logger.debug("GeoTIFF written: %s (%dx%d)", output_path, width, height)


# ---------------------------------------------------------------------------
# LAS file generation
# ---------------------------------------------------------------------------

def _generate_las(
    all_x: np.ndarray,
    all_y: np.ndarray,
    all_z: np.ndarray,
    all_color: np.ndarray,
    output_path: Path,
) -> None:
    """Write a LAS 1.4 point cloud with CRS=EPSG:32632 and RGB colours."""
    import laspy

    # Build colour arrays
    r_vals = np.array([COLORS_RGB[int(c)][0] * 256 for c in all_color], dtype=np.uint16)
    g_vals = np.array([COLORS_RGB[int(c)][1] * 256 for c in all_color], dtype=np.uint16)
    b_vals = np.array([COLORS_RGB[int(c)][2] * 256 for c in all_color], dtype=np.uint16)

    header = laspy.LasHeader(point_format=2, version='1.4')
    header.offsets = np.array([all_x.min(), all_y.min(), all_z.min()])
    header.scales = np.array([0.001, 0.001, 0.001])

    las = laspy.LasData(header=header)
    las.x = all_x
    las.y = all_y
    las.z = all_z
    las.red = r_vals
    las.green = g_vals
    las.blue = b_vals

    las.write(str(output_path))
    logger.debug("LAS written: %s (%d points)", output_path, len(all_x))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_test_site(output_dir: Path) -> dict[str, object]:
    """Generate a complete synthetic test dataset.

    Args:
        output_dir: Directory where test.las, test.tif, ground_truth.json are written.

    Returns:
        Ground truth dictionary (also saved as ground_truth.json).
    """
    rng = np.random.default_rng(42)
    output_dir.mkdir(parents=True, exist_ok=True)

    emit_progress("generator", 10.0, "Generazione punti terreno...")

    # --- Terrain ---
    tx, ty, tz, tc = _generate_terrain_points(rng)

    emit_progress("generator", 25.0, "Generazione cumulo 1 (cono)...")

    # --- Heap 1: Cone ---
    h1x, h1y, h1z, h1c = _generate_heap_points(
        1, 50.0, 50.0, CONE_R + 2,
        lambda x, y: _cone_height(x, y, 50.0, 50.0, CONE_R, CONE_H),
        rng,
    )

    emit_progress("generator", 40.0, "Generazione cumulo 2 (semisfera)...")

    # --- Heap 2: Hemisphere ---
    h2x, h2y, h2z, h2c = _generate_heap_points(
        2, 150.0, 50.0, HEMI_R + 2,
        lambda x, y: _hemisphere_height(x, y, 150.0, 50.0, HEMI_R),
        rng,
    )

    emit_progress("generator", 55.0, "Generazione cumulo 3 (piramide)...")

    # --- Heap 3: Pyramid ---
    h3x, h3y, h3z, h3c = _generate_heap_points(
        3, 50.0, 150.0, PYRAMID_BASE,
        lambda x, y: _pyramid_height(x, y, 50.0, 150.0, PYRAMID_BASE, PYRAMID_H),
        rng,
    )

    emit_progress("generator", 70.0, "Generazione cumulo 4 (tronco di cono)...")

    # --- Heap 4: Truncated cone ---
    h4x, h4y, h4z, h4c = _generate_heap_points(
        4, 150.0, 150.0, TCONE_RB + 2,
        lambda x, y: _truncated_cone_height(x, y, 150.0, 150.0, TCONE_RB, TCONE_RT, TCONE_H),
        rng,
    )

    # --- Merge all points ---
    all_x = np.concatenate([tx, h1x, h2x, h3x, h4x])
    all_y = np.concatenate([ty, h1y, h2y, h3y, h4y])
    all_z = np.concatenate([tz, h1z, h2z, h3z, h4z])
    all_color = np.concatenate([tc, h1c, h2c, h3c, h4c])

    emit_progress("generator", 80.0, "Scrittura file LAS...")
    las_path = output_dir / "test.las"
    _generate_las(all_x, all_y, all_z, all_color, las_path)

    emit_progress("generator", 90.0, "Scrittura GeoTIFF ortofoto...")
    tif_path = output_dir / "test.tif"
    _generate_geotiff(all_x, all_y, all_color, tif_path)

    ground_truth: dict[str, object] = {
        "terrain_elevation": TERRAIN_ELEV,
        "crs": CRS_WKT,
        "bounds": {
            "min_e": ORIGIN_E,
            "min_n": ORIGIN_N,
            "max_e": ORIGIN_E + SITE_SIZE,
            "max_n": ORIGIN_N + SITE_SIZE,
        },
        "heaps": [
            {
                "id": 1,
                "type": "cone",
                "center_e": ORIGIN_E + 50.0,
                "center_n": ORIGIN_N + 50.0,
                "volume_m3": round(CONE_VOL, 3),
                "max_height": CONE_H,
                "radius": CONE_R,
            },
            {
                "id": 2,
                "type": "hemisphere",
                "center_e": ORIGIN_E + 150.0,
                "center_n": ORIGIN_N + 50.0,
                "volume_m3": round(HEMI_VOL, 3),
                "max_height": HEMI_R,
                "radius": HEMI_R,
            },
            {
                "id": 3,
                "type": "pyramid",
                "center_e": ORIGIN_E + 50.0,
                "center_n": ORIGIN_N + 150.0,
                "volume_m3": round(PYRAMID_VOL, 3),
                "max_height": PYRAMID_H,
                "base_size": PYRAMID_BASE,
            },
            {
                "id": 4,
                "type": "truncated_cone",
                "center_e": ORIGIN_E + 150.0,
                "center_n": ORIGIN_N + 150.0,
                "volume_m3": round(TCONE_VOL, 3),
                "max_height": TCONE_H,
                "r_bottom": TCONE_RB,
                "r_top": TCONE_RT,
            },
        ],
    }

    gt_path = output_dir / "ground_truth.json"
    gt_path.write_text(json.dumps(ground_truth, indent=2), encoding="utf-8")
    logger.debug("ground_truth.json written: %s", gt_path)

    emit_progress("generator", 100.0, "Dataset sintetico completato")

    total_points = len(all_x)
    logger.info(
        "Dataset generato: %d punti, %d heap, CRS=%s",
        total_points,
        len(ground_truth["heaps"]),  # type: ignore[arg-type]
        CRS_WKT,
    )
    print(f"Totale punti: {total_points}", file=sys.stderr)

    return ground_truth
