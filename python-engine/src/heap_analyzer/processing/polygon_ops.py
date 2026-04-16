"""Polygon editing operations for heap splitting and merging.

Used by F3.S01 interactive editing. All geometry operations use Shapely 2.x.
"""

from __future__ import annotations

from shapely.geometry import LineString, Polygon, mapping, shape
from shapely.ops import split as shp_split
from shapely.ops import unary_union


def split_polygon_by_line(
    polygon_geojson: dict,  # type: ignore[type-arg]
    line_geojson: dict,  # type: ignore[type-arg]
) -> list[dict]:  # type: ignore[type-arg]
    """Split a polygon with a LineString cutter.

    Args:
        polygon_geojson: GeoJSON geometry dict of the polygon to split.
        line_geojson: GeoJSON geometry dict of the cutting LineString.

    Returns:
        List of GeoJSON Polygon geometries (>= 2 parts).

    Raises:
        ValueError: If the line does not properly cut the polygon
            (must cross edge-to-edge producing >= 2 parts).
    """
    poly = shape(polygon_geojson)
    if not poly.is_valid:
        poly = poly.buffer(0)
    line = shape(line_geojson)
    if not isinstance(line, LineString):
        raise ValueError("Splitter must be a LineString")
    if not line.intersects(poly):
        raise ValueError("Cutting line does not intersect the polygon")

    # Shapely 2.x: split returns a GeometryCollection
    result = shp_split(poly, line)
    parts = [g for g in result.geoms if isinstance(g, Polygon) and g.area > 0]
    if len(parts) < 2:
        raise ValueError(
            "Line did not produce >= 2 parts "
            "(must cross the polygon edge-to-edge)"
        )
    return [mapping(p) for p in parts]


def merge_polygons(
    polygons_geojson: list[dict],  # type: ignore[type-arg]
) -> dict:  # type: ignore[type-arg]
    """Merge >= 2 polygons into one via unary_union.

    Args:
        polygons_geojson: List of GeoJSON geometry dicts.

    Returns:
        A single GeoJSON Polygon or MultiPolygon geometry dict.

    Raises:
        ValueError: If fewer than 2 inputs are provided.
    """
    if len(polygons_geojson) < 2:
        raise ValueError("merge_polygons requires >= 2 polygons")
    geoms = [shape(g) for g in polygons_geojson]
    geoms = [g.buffer(0) if not g.is_valid else g for g in geoms]
    merged = unary_union(geoms)
    return mapping(merged)
