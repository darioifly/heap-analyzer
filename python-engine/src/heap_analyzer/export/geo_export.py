"""GIS export: GeoJSON + Shapefile via GeoPandas/Fiona.

Writes vector files ready for QGIS/ArcGIS with all heap metrics as attributes.
Attributes use SPEC [SCHEMA] heaps-table column names; Shapefile variants are
truncated to <=10 characters.

CRS is taken from the project (read from the caller) and attached without
reprojection — the file is for GIS consumers, not the web, so project CRS
(typically UTM 32N/33N) is correct.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any  # noqa: F401 — Any used in HeapRecord typing below

import click
from pydantic import BaseModel

from heap_analyzer.utils.logging import get_stderr_logger

if TYPE_CHECKING:
    import geopandas as gpd

logger = get_stderr_logger(__name__)


class HeapRecord(BaseModel):
    """Input record for GIS export — merges pipeline metrics with DB-only fields."""

    id: int
    label: str | None = None
    polygon_geojson: dict[str, Any]

    volume_m3: float
    planimetric_area_m2: float
    surface_area_m2: float
    max_height_m: float
    mean_height_m: float
    base_elevation_m: float
    centroid_e: float
    centroid_n: float

    material_category: str | None = None
    material_confidence: float | None = None
    is_manually_confirmed: bool = False
    is_excluded: bool = False
    survey_date: str | None = None


# Full-name -> Shapefile-name (<=10 chars)
_SHP_COLUMN_MAP: dict[str, str] = {
    "id": "id",
    "label": "label",
    "volume_m3": "vol_m3",
    "planimetric_area_m2": "area_pl_m2",
    "surface_area_m2": "area_sf_m2",
    "max_height_m": "h_max_m",
    "mean_height_m": "h_mean_m",
    "base_elevation_m": "base_m",
    "centroid_e": "centr_e",
    "centroid_n": "centr_n",
    "material_category": "mat_cat",
    "material_confidence": "mat_conf",
    "is_manually_confirmed": "confirmed",
    "survey_date": "surv_date",
}


def _build_gdf(heaps: list[HeapRecord], crs: str) -> gpd.GeoDataFrame:
    """Build a GeoDataFrame from HeapRecord list.

    Args:
        heaps: Heap records. Excluded heaps are dropped here.
        crs: Project CRS (e.g. 'EPSG:32632').

    Raises:
        click.UsageError: if no non-excluded heaps.

    Returns:
        geopandas.GeoDataFrame with polygons + metric attributes, CRS set.
    """
    import geopandas as gpd
    from shapely.geometry import shape as shapely_shape

    kept = [h for h in heaps if not h.is_excluded]
    if not kept:
        raise click.UsageError("Nessun cumulo da esportare")

    rows: list[dict[str, Any]] = []
    geoms = []
    for h in kept:
        geoms.append(shapely_shape(h.polygon_geojson))
        rows.append(
            {
                "id": h.id,
                "label": h.label or "",
                "volume_m3": round(h.volume_m3, 3),
                "planimetric_area_m2": round(h.planimetric_area_m2, 3),
                "surface_area_m2": round(h.surface_area_m2, 3),
                "max_height_m": round(h.max_height_m, 3),
                "mean_height_m": round(h.mean_height_m, 3),
                "base_elevation_m": round(h.base_elevation_m, 3),
                "centroid_e": round(h.centroid_e, 3),
                "centroid_n": round(h.centroid_n, 3),
                "material_category": h.material_category or "",
                "material_confidence": (
                    round(h.material_confidence, 3)
                    if h.material_confidence is not None
                    else None
                ),
                "is_manually_confirmed": 1 if h.is_manually_confirmed else 0,
                "survey_date": h.survey_date or "",
            }
        )

    gdf = gpd.GeoDataFrame(rows, geometry=geoms)
    gdf.set_crs(crs, inplace=True, allow_override=True)
    return gdf


def export_geojson(heaps: list[HeapRecord], crs: str, output_path: Path) -> Path:
    """Write heaps as a GeoJSON FeatureCollection.

    Attributes use full (snake_case) names. CRS is preserved in file properties
    but GeoJSON per RFC 7946 does not carry CRS per-feature — the consumer must
    know the project CRS (documented in accompanying metadata).

    Args:
        heaps: Heap records. Excluded heaps are skipped.
        crs: Project CRS (e.g. 'EPSG:32632').
        output_path: Target file path (will be overwritten).

    Returns:
        Resolved output path.

    Raises:
        click.UsageError: if no non-excluded heaps.
    """
    gdf = _build_gdf(heaps, crs)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    gdf.to_file(str(output_path), driver="GeoJSON")
    logger.debug("GeoJSON written: %s (%d features)", output_path, len(gdf))
    return output_path


def export_shapefile(heaps: list[HeapRecord], crs: str, output_path: Path) -> Path:
    """Write heaps as an ESRI Shapefile bundle (.shp/.shx/.dbf/.prj).

    Column names are truncated to the <=10 character Shapefile limit using
    ``_SHP_COLUMN_MAP``. The .prj file is written by Fiona with the project WKT.

    Args:
        heaps: Heap records. Excluded heaps are skipped.
        crs: Project CRS (e.g. 'EPSG:32632').
        output_path: Target .shp path (sibling .shx/.dbf/.prj generated).

    Returns:
        Resolved output path (the .shp file).

    Raises:
        click.UsageError: if no non-excluded heaps.
    """
    gdf = _build_gdf(heaps, crs)
    gdf = gdf.rename(columns=_SHP_COLUMN_MAP)

    # Sanity-check: all non-geometry columns must be <= 10 chars
    for col in gdf.columns:
        if col == "geometry":
            continue
        if len(col) > 10:
            raise RuntimeError(
                f"Internal error: shapefile column '{col}' exceeds 10 chars",
            )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    gdf.to_file(str(output_path), driver="ESRI Shapefile", encoding="utf-8")
    logger.debug("Shapefile written: %s (%d features)", output_path, len(gdf))
    return output_path
