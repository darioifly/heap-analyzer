"""Tests for GIS export (GeoJSON + Shapefile)."""

from __future__ import annotations

from pathlib import Path

import click
import pytest

from heap_analyzer.export.geo_export import (
    HeapRecord,
    export_geojson,
    export_shapefile,
)


def _make_record(
    heap_id: int,
    x: float,
    y: float,
    size: float = 5.0,
    **overrides: object,
) -> HeapRecord:
    """Build a HeapRecord with a square polygon of side `size` anchored at (x, y)."""
    polygon = {
        "type": "Polygon",
        "coordinates": [
            [
                [x, y],
                [x + size, y],
                [x + size, y + size],
                [x, y + size],
                [x, y],
            ]
        ],
    }
    fields: dict[str, object] = {
        "id": heap_id,
        "label": f"H{heap_id}",
        "polygon_geojson": polygon,
        "volume_m3": 100.0 * heap_id,
        "planimetric_area_m2": size * size,
        "surface_area_m2": size * size * 1.1,
        "max_height_m": 3.0,
        "mean_height_m": 1.5,
        "base_elevation_m": 100.0,
        "centroid_e": x + size / 2,
        "centroid_n": y + size / 2,
        "material_category": "ghisa",
        "material_confidence": 0.9,
        "is_manually_confirmed": True,
        "is_excluded": False,
        "survey_date": "2026-04-20",
    }
    fields.update(overrides)
    return HeapRecord(**fields)  # type: ignore[arg-type]


def test_geojson_valid_structure(tmp_path: Path) -> None:
    """GeoJSON round-trips with correct feature count, CRS, and attribute keys."""
    gpd = pytest.importorskip("geopandas")

    records = [
        _make_record(1, 500000.0, 4900000.0),
        _make_record(2, 500100.0, 4900000.0),
        _make_record(3, 500200.0, 4900000.0),
    ]

    out = tmp_path / "out.geojson"
    export_geojson(records, "EPSG:32632", out)

    assert out.exists()
    gdf = gpd.read_file(out)

    assert len(gdf) == 3
    assert str(gdf.crs).upper().endswith("32632")

    expected_cols = {
        "id", "label", "volume_m3", "planimetric_area_m2", "surface_area_m2",
        "max_height_m", "mean_height_m", "base_elevation_m",
        "centroid_e", "centroid_n",
        "material_category", "material_confidence",
        "is_manually_confirmed", "survey_date",
    }
    assert expected_cols.issubset(set(gdf.columns))


def test_shapefile_column_names_max_10_chars(tmp_path: Path) -> None:
    """Every non-geometry column in the written .dbf is <=10 chars."""
    pytest.importorskip("geopandas")
    pytest.importorskip("pyogrio")

    records = [_make_record(1, 500000.0, 4900000.0)]
    out = tmp_path / "heaps.shp"
    export_shapefile(records, "EPSG:32632", out)

    import geopandas as gpd
    gdf = gpd.read_file(out)
    for col in gdf.columns:
        if col == "geometry":
            continue
        assert len(col) <= 10, f"Shapefile column '{col}' exceeds 10 chars"


def test_shapefile_prj_contains_crs(tmp_path: Path) -> None:
    """The sibling .prj file exists and references the UTM projection."""
    pytest.importorskip("geopandas")

    records = [_make_record(1, 500000.0, 4900000.0)]
    out = tmp_path / "heaps.shp"
    export_shapefile(records, "EPSG:32632", out)

    prj = out.with_suffix(".prj")
    assert prj.exists(), ".prj file must be written alongside .shp"
    wkt = prj.read_text(encoding="utf-8")
    assert "UTM" in wkt or "Transverse_Mercator" in wkt


def test_excluded_heaps_skipped(tmp_path: Path) -> None:
    """A heap marked is_excluded=True must not appear in the output."""
    pytest.importorskip("geopandas")

    records = [
        _make_record(1, 500000.0, 4900000.0, is_excluded=False),
        _make_record(2, 500100.0, 4900000.0, is_excluded=True),
        _make_record(3, 500200.0, 4900000.0, is_excluded=False),
    ]

    out = tmp_path / "out.geojson"
    export_geojson(records, "EPSG:32632", out)

    import geopandas as gpd
    gdf = gpd.read_file(out)
    assert len(gdf) == 2
    assert set(gdf["id"].tolist()) == {1, 3}


def test_empty_raises(tmp_path: Path) -> None:
    """Empty (or all-excluded) input raises click.UsageError with Italian message."""
    pytest.importorskip("geopandas")

    with pytest.raises(click.UsageError, match="Nessun cumulo"):
        export_geojson([], "EPSG:32632", tmp_path / "empty.geojson")

    all_excluded = [_make_record(1, 0.0, 0.0, is_excluded=True)]
    with pytest.raises(click.UsageError, match="Nessun cumulo"):
        export_shapefile(all_excluded, "EPSG:32632", tmp_path / "empty.shp")


def test_polygon_geometry_preserved(tmp_path: Path) -> None:
    """Round-trip polygon coordinates match input within 1e-6 m tolerance."""
    pytest.importorskip("geopandas")

    records = [_make_record(1, 500000.0, 4900000.0, size=7.5)]
    out = tmp_path / "out.geojson"
    export_geojson(records, "EPSG:32632", out)

    import geopandas as gpd
    gdf = gpd.read_file(out)
    geom = gdf.geometry.iloc[0]
    orig_coords = records[0].polygon_geojson["coordinates"][0]
    out_coords = list(geom.exterior.coords)

    assert len(orig_coords) == len(out_coords)
    for a, b in zip(orig_coords, out_coords, strict=False):
        assert abs(a[0] - b[0]) < 1e-6
        assert abs(a[1] - b[1]) < 1e-6
