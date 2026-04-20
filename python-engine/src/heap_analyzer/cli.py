"""Command-line interface for Heap Analyzer.

CRITICAL: stdout is ONLY JSON Lines. All debug/log output goes to stderr.
"""

import json
import sys
from pathlib import Path
from typing import Any

import click

from heap_analyzer import __version__
from heap_analyzer.config import ProcessingConfig
from heap_analyzer.utils.logging import emit_error, emit_progress, emit_result, emit_warning


@click.group()
@click.version_option(version=__version__)
@click.option("--verbose", is_flag=True, default=False, help="Enable DEBUG logging")
def main(verbose: bool) -> None:
    """Heap Analyzer — Volumetric analysis of material heaps from LiDAR point clouds."""
    from heap_analyzer.utils.logging import setup_logging
    setup_logging(verbose=verbose)


@main.command()
@click.option("--las", required=True, help="Path to input LAS/LAZ file")
@click.option("--tiff", required=True, help="Path to input GeoTIFF ortophoto")
@click.option("--output", required=True, help="Output directory path")
@click.option("--config", default=None, help="Path to JSON file with ProcessingConfig overrides")
def process(las: str, tiff: str, output: str, config: str | None) -> None:
    """Process a LAS point cloud + GeoTIFF ortophoto to detect and measure heaps.

    All progress is reported as JSON Lines on stdout.
    Logs and debug info go to stderr.
    """
    print(f"[heap-analyzer] process called: las={las} tiff={tiff} output={output}", file=sys.stderr)

    try:
        processing_config = _parse_config(config)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        emit_error("INVALID_CONFIG", f"Errore configurazione: {exc}")
        sys.exit(1)

    try:
        from heap_analyzer.pipeline import ProcessingPipeline

        pipeline = ProcessingPipeline(processing_config)
        las_path = Path(las)
        tiff_path = Path(tiff)
        output_dir = Path(output)

        def on_progress(pct: int, msg: str) -> None:
            emit_progress("processing", float(pct), msg)

        result = pipeline.run(las_path, tiff_path, output_dir, progress_callback=on_progress)

        emit_result({
            "heap_metrics": [m.model_dump() for m in result.heap_metrics],
            "survey_metadata": result.survey_metadata,
            "base_elevation": result.base_elevation,
            "base_elevation_method": result.base_elevation_method,
            "base_elevation_confidence": result.base_elevation_confidence,
            "intermediate_files": result.intermediate_files,
            "warnings": result.warnings,
        })

    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        emit_error("PROCESSING_ERROR", f"Errore durante l'elaborazione: {exc}")
        print(f"[heap-analyzer] ERROR: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


@main.command()
@click.option("--las", required=True, help="Path to LAS/LAZ file")
@click.option("--tiff", required=True, help="Path to GeoTIFF ortophoto")
def validate(las: str, tiff: str) -> None:
    """Validate that a LAS file and GeoTIFF are compatible (matching CRS, overlapping bounds).

    All output is JSON Lines on stdout.
    """
    print(f"[heap-analyzer] validate called: las={las} tiff={tiff}", file=sys.stderr)

    try:
        from heap_analyzer.pipeline import ProcessingPipeline

        pipeline = ProcessingPipeline()
        las_path = Path(las)
        tiff_path = Path(tiff)

        emit_progress("validation", 10.0, "Validazione input...")
        errors = pipeline.validate_inputs(las_path, tiff_path)
        emit_progress("validation", 100.0, "Validazione completata")

        if errors:
            emit_result({"valid": False, "errors": errors})
            sys.exit(1)
        else:
            emit_result({"valid": True, "errors": []})

    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        emit_error("VALIDATION_ERROR", f"Errore validazione: {exc}")
        sys.exit(1)


@main.command("generate-test-data")
@click.option("--output", required=True, help="Output directory for test data")
@click.option(
    "--variant", default="baseline", type=click.Choice(["baseline", "t2"]),
    help="Dataset variant: baseline (original 4 heaps) or t2 (temporal comparison partner)",
)
def generate_test_data(output: str, variant: str) -> None:
    """Generate synthetic test dataset with geometric heaps.

    Produces test.las, test.tif, and ground_truth.json in the output directory.
    Use --variant t2 to generate the temporal comparison partner dataset.
    """
    print(f"[heap-analyzer] generate-test-data: output={output} variant={variant}", file=sys.stderr)  # noqa: E501

    try:
        output_dir = Path(output)
        output_dir.mkdir(parents=True, exist_ok=True)

        emit_progress("setup", 5.0, f"Inizializzazione generatore ({variant})...")

        if variant == "t2":
            from heap_analyzer.test_data_generator import create_test_site_t2
            create_test_site_t2(output_dir)
            files = ["test.las", "test.tif", "ground_truth_t2.json"]
        else:
            from heap_analyzer.test_data_generator import create_test_site
            create_test_site(output_dir)
            files = ["test.las", "test.tif", "ground_truth.json"]

        emit_progress("complete", 100.0, f"Dataset sintetico ({variant}) generato")
        emit_result({
            "output_dir": str(output_dir),
            "variant": variant,
            "files": files,
        })
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        emit_error("GENERATOR_ERROR", f"Errore generazione dati: {exc}")
        sys.exit(1)


@main.command("compare")
@click.option(
    "--results-a", required=True, type=click.Path(exists=True),
    help="Path to results.json from survey A",
)
@click.option(
    "--results-b", required=True, type=click.Path(exists=True),
    help="Path to results.json from survey B",
)
@click.option(
    "--output", default=None, type=click.Path(),
    help="Output path for match.json (optional)",
)
@click.option(
    "--iou-threshold", default=0.3, type=float,
    help="Min IoU to match (default 0.3)",
)
@click.option(
    "--stability-threshold", default=0.05, type=float,
    help="Stability threshold (default 0.05)",
)
def compare_cmd(
    results_a: str,
    results_b: str,
    output: str | None,
    iou_threshold: float,
    stability_threshold: float,
) -> None:
    """Compare heaps between two survey results (spatial matching).

    Reads two results.json files, matches heaps by polygon IoU using
    the Hungarian algorithm, and emits a MatchResult.
    """
    print(f"[heap-analyzer] compare called: A={results_a} B={results_b}", file=sys.stderr)

    try:
        from heap_analyzer.comparison.config import ComparisonConfig
        from heap_analyzer.comparison.matcher import HeapRecord, match_heaps
        from heap_analyzer.processing.volume import HeapMetrics

        emit_progress("compare", 0.0, "Caricamento risultati...")

        # Load results
        data_a = json.loads(Path(results_a).read_text(encoding="utf-8"))
        data_b = json.loads(Path(results_b).read_text(encoding="utf-8"))

        metrics_a = [HeapMetrics(**hm) for hm in data_a["heap_metrics"]]
        metrics_b = [HeapMetrics(**hm) for hm in data_b["heap_metrics"]]

        # Convert to HeapRecords
        heaps_a = [
            HeapRecord(
                heap_id=m.heap_id,
                polygon_geojson=m.polygon_geojson,
                volume_m3=m.volume_m3,
                planimetric_area_m2=m.planimetric_area_m2,
                max_height_m=m.max_height_m,
            )
            for m in metrics_a
        ]
        heaps_b = [
            HeapRecord(
                heap_id=m.heap_id,
                polygon_geojson=m.polygon_geojson,
                volume_m3=m.volume_m3,
                planimetric_area_m2=m.planimetric_area_m2,
                max_height_m=m.max_height_m,
            )
            for m in metrics_b
        ]

        config = ComparisonConfig(
            iou_threshold=iou_threshold,
            stability_threshold=stability_threshold,
        )

        emit_progress("compare", 30.0, "Calcolo IoU e matching...")
        result = match_heaps(heaps_a, heaps_b, config)

        emit_progress("compare", 90.0, "Matching completato")

        result_dict = result.model_dump()

        # Optionally save to file
        if output:
            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(result_dict, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"[heap-analyzer] Match result saved: {output_path}", file=sys.stderr)

        emit_result(result_dict)

    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        emit_error("COMPARE_FAILED", f"Errore durante il confronto: {exc}")
        print(f"[heap-analyzer] ERROR: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


@main.command("create-tiles")
@click.option("--tiff", required=True, help="Path to input GeoTIFF ortophoto")
@click.option("--output", required=True, help="Output directory for tiles")
@click.option("--max-zoom", default=None, type=int, help="Maximum zoom level (auto-computed if omitted)")
def create_tiles(tiff: str, output: str, max_zoom: int | None) -> None:
    """Generate XYZ tile pyramid from a GeoTIFF in source CRS."""
    print(f"[heap-analyzer] create-tiles called: tiff={tiff} output={output}", file=sys.stderr)

    try:
        from heap_analyzer.export.tile_generator import generate_tiles

        def on_progress(pct: int, msg: str) -> None:
            emit_progress("generating_tiles", float(pct), msg)

        result = generate_tiles(
            Path(tiff), Path(output),
            max_zoom=max_zoom,
            progress_callback=on_progress,
        )
        emit_result({
            "tiles_dir": result.tiles_dir,
            "metadata": result.model_dump(),
        })
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        emit_error("TILE_ERROR", f"Errore generazione tile: {exc}")
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


@main.command("export-csv")
@click.option("--results", required=True, help="Path to results.json from pipeline")
@click.option("--output", required=True, help="Output CSV file path")
@click.option("--survey-date", default=None, help="Survey date (YYYY-MM-DD)")
def export_csv(results: str, output: str, survey_date: str | None) -> None:
    """Export heap metrics to CSV.

    CSV format: semicolon separator, UTF-8 with BOM, Italian headers.
    """
    print(f"[heap-analyzer] export-csv called: results={results} output={output}", file=sys.stderr)

    try:
        from heap_analyzer.export.csv_export import export_csv as do_export
        from heap_analyzer.processing.volume import HeapMetrics

        results_path = Path(results)
        if not results_path.exists():
            emit_error("FILE_NOT_FOUND", f"File risultati non trovato: {results}")
            sys.exit(1)

        data = json.loads(results_path.read_text(encoding="utf-8"))

        # Parse heap metrics
        metrics = [HeapMetrics(**hm) for hm in data["heap_metrics"]]

        # Survey metadata
        survey_metadata = data.get("survey_metadata", {})

        # Survey date
        if survey_date:
            survey_metadata["survey_date"] = survey_date
        elif "survey_date" not in survey_metadata:
            import datetime
            today = datetime.date.today().isoformat()
            emit_warning(f"Data rilievo non specificata, uso data odierna: {today}")
            survey_metadata["survey_date"] = today

        emit_progress("export", 50.0, "Esportazione CSV...")
        output_path = do_export(metrics, survey_metadata, Path(output))
        emit_progress("export", 100.0, "Esportazione CSV completata")
        emit_result({"output_path": str(output_path), "heap_count": len(metrics)})

    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        emit_error("EXPORT_ERROR", f"Errore esportazione CSV: {exc}")
        sys.exit(1)


@main.command("generate-report")
@click.option("--results", required=True, type=click.Path(exists=True), help="Path to results.json")
@click.option("--tiff", required=True, type=click.Path(exists=True), help="Path to GeoTIFF")
@click.option("--output", required=True, type=click.Path(), help="Output PDF path")
@click.option("--logo", default=None, type=click.Path(), help="Logo PNG/JPEG path")
@click.option("--company", default=None, help="Company name")
@click.option("--notes", default=None, help="Additional notes text")
@click.option("--only-confirmed", is_flag=True, default=False, help="Only confirmed heaps")
@click.option("--site-name", default=None, help="Site name")
@click.option("--operator", default=None, help="Operator name")
@click.option("--survey-date", default=None, help="Survey date YYYY-MM-DD")
@click.option("--heaps-json", default=None, help="JSON array of heap DB data with classifications")
@click.option("--categories-json", default=None, help="JSON array of project categories")
def generate_report_cmd(
    results: str,
    tiff: str,
    output: str,
    logo: str | None,
    company: str | None,
    notes: str | None,
    only_confirmed: bool,
    site_name: str | None,
    operator: str | None,
    survey_date: str | None,
    heaps_json: str | None,
    categories_json: str | None,
) -> None:
    """Generate a professional PDF report."""
    click.echo(f"[heap-analyzer] generate-report: output={output}", err=True)

    try:
        from heap_analyzer.report.pdf_generator import (
            ReportConfig,
            ReportGenerator,
            ReportProgress,
        )

        # Build config
        config = ReportConfig(
            site_name=site_name or "Sito",
            company_name=company,
            logo_path=logo,
            operator_name=operator,
            additional_notes=notes,
            only_confirmed_heaps=only_confirmed,
        )

        # Inject survey_date into results if provided
        results_path = Path(results)
        data = json.loads(results_path.read_text(encoding="utf-8"))
        if survey_date:
            data.setdefault("survey_metadata", {})["survey_date"] = survey_date
        if categories_json:
            cats = json.loads(categories_json)
            data.setdefault("survey_metadata", {})["project_categories"] = cats

        # Write back modified data to a temp file
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8",
        ) as tmp:
            json.dump(data, tmp, ensure_ascii=False, indent=2)
            temp_results = Path(tmp.name)

        # Parse heap DB data
        heap_db_data: list[dict] | None = None  # type: ignore[type-arg]
        if heaps_json:
            heap_db_data = json.loads(heaps_json)

        def on_progress(p: ReportProgress) -> None:
            emit_progress(p.phase, p.percent, p.message)

        generator = ReportGenerator(config)
        generator.generate(
            results_path=temp_results,
            tiff_path=Path(tiff),
            output_path=Path(output),
            progress_cb=on_progress,
            heap_db_data=heap_db_data,
        )

        # Cleanup temp file
        temp_results.unlink(missing_ok=True)

        emit_result({"output_path": output})

    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        emit_error("REPORT_FAILED", f"Errore generazione report: {exc}")
        click.echo(f"[heap-analyzer] ERROR: {exc}", err=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


@main.command("recompute-heap")
@click.option("--ndsm", required=True, type=click.Path(exists=True), help="Path to nDSM GeoTIFF")
@click.option("--polygon-json", required=True, help="GeoJSON geometry as JSON string")
@click.option("--base-elevation", required=True, type=float, help="Base elevation in meters")
@click.option(
    "--config", "config_arg", default=None,
    help="ProcessingConfig JSON string or file path",
)
def recompute_heap(
    ndsm: str, polygon_json: str,
    base_elevation: float, config_arg: str | None,
) -> None:
    """Recompute metrics for a single heap polygon. Emits JSON Lines."""
    click.echo(f"[heap-analyzer] recompute-heap called: ndsm={ndsm}", err=True)

    try:
        cfg = _parse_config(config_arg)
        geom_dict = json.loads(polygon_json)

        from heap_analyzer.processing.volume import recompute_single_heap

        metrics = recompute_single_heap(ndsm, geom_dict, base_elevation, cfg)
        emit_result(metrics.model_dump())

    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        emit_error("RECOMPUTE_FAILED", str(exc))
        click.echo(f"[heap-analyzer] ERROR: {exc}", err=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


@main.command("split-polygon")
@click.option("--polygon-json", required=True, help="GeoJSON geometry of polygon to split")
@click.option("--line-json", required=True, help="GeoJSON geometry of cutting LineString")
def split_polygon(polygon_json: str, line_json: str) -> None:
    """Split a polygon with a cutting line. Emits JSON Lines."""
    click.echo("[heap-analyzer] split-polygon called", err=True)

    try:
        from heap_analyzer.processing.polygon_ops import split_polygon_by_line

        parts = split_polygon_by_line(
            json.loads(polygon_json), json.loads(line_json)
        )
        emit_result({"parts": parts})

    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        emit_error("SPLIT_FAILED", str(exc))
        click.echo(f"[heap-analyzer] ERROR: {exc}", err=True)
        sys.exit(1)


@main.command("merge-polygons")
@click.option(
    "--polygons-json", required=True,
    help="JSON array of GeoJSON geometries",
)
def merge_polygons_cmd(polygons_json: str) -> None:
    """Merge >= 2 polygons into one. Emits JSON Lines."""
    click.echo("[heap-analyzer] merge-polygons called", err=True)

    try:
        from heap_analyzer.processing.polygon_ops import merge_polygons

        merged = merge_polygons(json.loads(polygons_json))
        emit_result({"merged": merged})

    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        emit_error("MERGE_FAILED", str(exc))
        click.echo(f"[heap-analyzer] ERROR: {exc}", err=True)
        sys.exit(1)


@main.command("recompute-all-heaps")
@click.option("--ndsm", required=True, type=click.Path(exists=True), help="Path to nDSM GeoTIFF")
@click.option("--heaps-json", required=True, help="JSON array of {id, polygon_geojson}")
@click.option("--base-elevation", required=True, type=float, help="New base elevation in meters")
@click.option("--original-base-elevation", default=None, type=float, help="Original base elevation")
@click.option(
    "--config", "config_arg", default=None,
    help="ProcessingConfig JSON string or file path",
)
def recompute_all_heaps_cmd(
    ndsm: str, heaps_json: str,
    base_elevation: float, original_base_elevation: float | None,
    config_arg: str | None,
) -> None:
    """Recompute metrics for all heaps with a new base elevation. Emits JSON Lines."""
    click.echo(f"[heap-analyzer] recompute-all-heaps called: ndsm={ndsm}", err=True)

    try:
        cfg = _parse_config(config_arg)
        heaps = json.loads(heaps_json)

        from heap_analyzer.processing.volume import recompute_all_heaps

        emit_progress("recompute", 0.0, "Ricalcolo volumi...")
        results = recompute_all_heaps(ndsm, heaps, base_elevation, cfg, original_base_elevation)
        emit_progress("recompute", 100.0, "Ricalcolo completato")
        emit_result({"heaps": results, "base_elevation": base_elevation})

    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        emit_error("RECOMPUTE_ALL_FAILED", str(exc))
        click.echo(f"[heap-analyzer] ERROR: {exc}", err=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


@main.command("export-pointcloud")
@click.option("--las", required=True, type=click.Path(exists=True), help="Input LAS/LAZ file")
@click.option("--output", required=True, type=click.Path(), help="Output directory for Potree files")
@click.option("--converter-path", default=None, type=click.Path(), help="Custom PotreeConverter path")
def export_pointcloud_cmd(las: str, output: str, converter_path: str | None) -> None:
    """Convert LAS/LAZ to Potree 2.0 format."""
    click.echo(f"[heap-analyzer] export-pointcloud called: las={las}", err=True)

    try:
        from heap_analyzer.export.pointcloud_export import export_for_potree

        def progress_cb(pct: int, msg: str) -> None:
            emit_progress("potree_conversion", float(pct), msg)

        result = export_for_potree(
            las_path=las,
            output_dir=output,
            potree_converter_path=converter_path,
            progress_callback=progress_cb,
        )

        if result.success:
            emit_result({
                "output_dir": result.output_dir,
                "metadata_path": result.metadata_path,
                "num_points": result.num_points,
                "bounds": result.bounds,
            })
        else:
            emit_error("POTREE_CONVERSION_FAILED", result.error or "Unknown error")
            sys.exit(1)

    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        emit_error("POTREE_CONVERSION_FAILED", str(exc))
        click.echo(f"[heap-analyzer] ERROR: {exc}", err=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


@main.command("sample-ground")
@click.option("--dsm", required=True, type=click.Path(exists=True), help="Path to DSM GeoTIFF")
@click.option("--polygons-json", required=True, help="JSON array of GeoJSON polygon geometries")
def sample_ground_cmd(dsm: str, polygons_json: str) -> None:
    """Sample DSM elevation within user-drawn ground-reference polygons. Emits JSON Lines."""
    click.echo(f"[heap-analyzer] sample-ground called: dsm={dsm}", err=True)

    try:
        from heap_analyzer.processing.ground_sampling import sample_dsm_in_polygons

        polygons = json.loads(polygons_json)
        result = sample_dsm_in_polygons(dsm, polygons)
        emit_result(result)

    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        emit_error("GROUND_SAMPLE_FAILED", str(exc))
        click.echo(f"[heap-analyzer] ERROR: {exc}", err=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


@main.command("render-site-overview")
@click.option("--tiff", required=True, type=click.Path(exists=True), help="Path to GeoTIFF")
@click.option("--results", required=True, type=click.Path(exists=True), help="Path to results.json")
@click.option("--site-name", default="Sito", help="Site name for the title")
@click.option("--survey-date", required=True, help="Survey date YYYY-MM-DD")
@click.option("--output", required=True, type=click.Path(), help="Output PNG path")
@click.option("--dpi", default=150, type=int, help="Output DPI")
@click.option("--max-width", default=2400, type=int, help="Max raster width in pixels")
@click.option("--categories-json", default=None, help="JSON array of project categories")
def render_site_overview_cmd(
    tiff: str,
    results: str,
    site_name: str,
    survey_date: str,
    output: str,
    dpi: int,
    max_width: int,
    categories_json: str | None,
) -> None:
    """Render site overview PNG with heap overlays for the PDF report."""
    click.echo(f"[heap-analyzer] render-site-overview: tiff={tiff}", err=True)

    try:
        import datetime as dt

        from heap_analyzer.processing.volume import HeapMetrics
        from heap_analyzer.report.map_renderer import HeapRenderInfo, MapRenderer

        emit_progress("render_overview", 0.0, "Caricamento dati...")

        data = json.loads(Path(results).read_text(encoding="utf-8"))
        metrics = [HeapMetrics(**hm) for hm in data["heap_metrics"]]

        # Parse categories
        project_categories: list[str] = []
        if categories_json:
            project_categories = json.loads(categories_json)

        # Build HeapRenderInfo list
        heaps = [
            HeapRenderInfo(
                heap_id=m.heap_id,
                label=m.label,
                polygon_geojson=m.polygon_geojson,
                category=None,  # classification comes from DB, not results.json
            )
            for m in metrics
        ]

        parsed_date = dt.date.fromisoformat(survey_date)

        emit_progress("render_overview", 20.0, "Rendering panoramica...")

        renderer = MapRenderer()
        renderer.render_site_overview(
            tiff_path=Path(tiff),
            heaps=heaps,
            project_categories=project_categories,
            site_name=site_name,
            survey_date=parsed_date,
            output_path=Path(output),
            dpi=dpi,
            max_width_px=max_width,
        )

        emit_progress("render_overview", 100.0, "Panoramica completata")
        emit_result({"output_path": output})

    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        emit_error("RENDER_OVERVIEW_FAILED", str(exc))
        click.echo(f"[heap-analyzer] ERROR: {exc}", err=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


@main.command("render-heap-detail")
@click.option("--tiff", required=True, type=click.Path(exists=True), help="Path to GeoTIFF")
@click.option("--results", required=True, type=click.Path(exists=True), help="Path to results.json")
@click.option("--heap-id", required=True, type=int, help="Heap ID to render")
@click.option("--output", required=True, type=click.Path(), help="Output PNG path")
@click.option("--dpi", default=200, type=int, help="Output DPI")
@click.option("--padding", default=25.0, type=float, help="Padding around polygon (%)")
@click.option("--categories-json", default=None, help="JSON array of project categories")
def render_heap_detail_cmd(
    tiff: str,
    results: str,
    heap_id: int,
    output: str,
    dpi: int,
    padding: float,
    categories_json: str | None,
) -> None:
    """Render a heap detail PNG for the PDF report."""
    click.echo(f"[heap-analyzer] render-heap-detail: heap_id={heap_id}", err=True)

    try:
        from heap_analyzer.processing.volume import HeapMetrics
        from heap_analyzer.report.map_renderer import (
            HeapDetailMetrics,
            HeapRenderInfo,
            MapRenderer,
        )

        emit_progress("render_detail", 0.0, "Caricamento dati...")

        data = json.loads(Path(results).read_text(encoding="utf-8"))
        all_metrics = [HeapMetrics(**hm) for hm in data["heap_metrics"]]

        target = None
        for m in all_metrics:
            if m.heap_id == heap_id:
                target = m
                break

        if target is None:
            emit_error("HEAP_NOT_FOUND", f"Cumulo {heap_id} non trovato nei risultati")
            sys.exit(1)

        project_categories: list[str] = []
        if categories_json:
            project_categories = json.loads(categories_json)

        heap_info = HeapRenderInfo(
            heap_id=target.heap_id,
            label=target.label,
            polygon_geojson=target.polygon_geojson,
            category=None,
        )

        detail_metrics = HeapDetailMetrics(
            volume_m3=target.volume_m3,
            max_height_m=target.max_height_m,
            mean_height_m=target.mean_height_m,
            planimetric_area_m2=target.planimetric_area_m2,
        )

        emit_progress("render_detail", 20.0, "Rendering dettaglio cumulo...")

        renderer = MapRenderer()
        renderer.render_heap_detail(
            tiff_path=Path(tiff),
            heap=heap_info,
            heap_metrics=detail_metrics,
            project_categories=project_categories,
            output_path=Path(output),
            dpi=dpi,
            padding_percent=padding,
        )

        emit_progress("render_detail", 100.0, "Dettaglio completato")
        emit_result({"output_path": output, "heap_id": heap_id})

    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        emit_error("RENDER_DETAIL_FAILED", str(exc))
        click.echo(f"[heap-analyzer] ERROR: {exc}", err=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


@main.command("export-geo")
@click.option("--results", required=True, type=click.Path(exists=True), help="Path to results.json")
@click.option(
    "--format", "export_format",
    type=click.Choice(["geojson", "shapefile", "both"]), default="both",
    help="Output format",
)
@click.option("--output-dir", required=True, type=click.Path(), help="Output directory")
@click.option("--basename", default="heaps", help="Output file basename (without extension)")
@click.option("--crs", default=None, help="EPSG CRS override (e.g. 'EPSG:32632')")
@click.option("--heaps-json", default=None, help="JSON array of DB-enriched heap records")
@click.option("--survey-date", default=None, help="Survey date (ISO YYYY-MM-DD)")
def export_geo_cmd(
    results: str,
    export_format: str,
    output_dir: str,
    basename: str,
    crs: str | None,
    heaps_json: str | None,
    survey_date: str | None,
) -> None:
    """Export heaps as GeoJSON / Shapefile for QGIS consumption."""
    click.echo(f"[heap-analyzer] export-geo: format={export_format} output={output_dir}", err=True)

    try:
        from heap_analyzer.export.geo_export import (
            HeapRecord,
            export_geojson,
            export_shapefile,
        )
        from heap_analyzer.processing.volume import HeapMetrics

        results_path = Path(results)
        data = json.loads(results_path.read_text(encoding="utf-8"))

        # Base metrics from pipeline results
        pipeline_metrics = {m["heap_id"]: m for m in data["heap_metrics"]}

        # Resolve CRS (CLI override > results.json > default UTM 32N)
        resolved_crs = crs or data.get("survey_metadata", {}).get("crs") or "EPSG:32632"

        # Build heap records. If --heaps-json was provided, use it as source of truth
        # (DB-enriched). Otherwise fall back to pipeline metrics only.
        records: list[HeapRecord] = []
        if heaps_json:
            db_heaps = json.loads(heaps_json)
            for h in db_heaps:
                heap_id = h.get("id") if "id" in h else h.get("heap_id")
                metrics = pipeline_metrics.get(heap_id, {})

                records.append(
                    HeapRecord(
                        id=int(heap_id),
                        label=h.get("label") or metrics.get("label"),
                        polygon_geojson=(
                            h.get("polygon_geojson") or metrics.get("polygon_geojson") or {}
                        ),
                        volume_m3=float(h.get("volume") or metrics.get("volume_m3") or 0.0),
                        planimetric_area_m2=float(
                            h.get("planimetric_area") or metrics.get("planimetric_area_m2") or 0.0,
                        ),
                        surface_area_m2=float(
                            h.get("surface_area") or metrics.get("surface_area_m2") or 0.0,
                        ),
                        max_height_m=float(
                            h.get("max_height") or metrics.get("max_height_m") or 0.0,
                        ),
                        mean_height_m=float(
                            h.get("mean_height") or metrics.get("mean_height_m") or 0.0,
                        ),
                        base_elevation_m=float(
                            h.get("base_elevation") or metrics.get("base_elevation_m") or 0.0,
                        ),
                        centroid_e=float(h.get("centroid_e") or metrics.get("centroid_e") or 0.0),
                        centroid_n=float(h.get("centroid_n") or metrics.get("centroid_n") or 0.0),
                        material_category=h.get("material_category"),
                        material_confidence=h.get("material_confidence"),
                        is_manually_confirmed=bool(h.get("is_manually_confirmed", False)),
                        is_excluded=bool(h.get("is_excluded", False)),
                        survey_date=h.get("survey_date") or survey_date,
                    )
                )
        else:
            for hm in data["heap_metrics"]:
                m = HeapMetrics(**hm)
                records.append(
                    HeapRecord(
                        id=m.heap_id,
                        label=m.label,
                        polygon_geojson=m.polygon_geojson,
                        volume_m3=m.volume_m3,
                        planimetric_area_m2=m.planimetric_area_m2,
                        surface_area_m2=m.surface_area_m2,
                        max_height_m=m.max_height_m,
                        mean_height_m=m.mean_height_m,
                        base_elevation_m=m.base_elevation_m,
                        centroid_e=m.centroid_e,
                        centroid_n=m.centroid_n,
                        survey_date=survey_date,
                    )
                )

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        paths: list[str] = []

        emit_progress("export_geo", 10.0, "Preparazione export GIS...")

        if export_format in ("geojson", "both"):
            emit_progress("export_geo", 40.0, "Scrittura GeoJSON...")
            p = export_geojson(records, resolved_crs, out_dir / f"{basename}.geojson")
            paths.append(str(p))

        if export_format in ("shapefile", "both"):
            emit_progress("export_geo", 75.0, "Scrittura Shapefile...")
            p = export_shapefile(records, resolved_crs, out_dir / f"{basename}.shp")
            paths.append(str(p))
            for ext in (".shx", ".dbf", ".prj"):
                sib = out_dir / f"{basename}{ext}"
                if sib.exists():
                    paths.append(str(sib))

        emit_progress("export_geo", 100.0, "Export GIS completato")
        emit_result({"paths": paths, "crs": resolved_crs, "count": len(records)})

    except click.UsageError as exc:
        emit_error("NO_HEAPS", str(exc))
        sys.exit(1)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        emit_error("EXPORT_GEO_FAILED", f"Errore export GIS: {exc}")
        click.echo(f"[heap-analyzer] ERROR: {exc}", err=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


@main.command("config-schema")
def config_schema_cmd() -> None:
    """Emit ProcessingConfig field metadata (name, type, default, description)."""
    try:
        fields: list[dict[str, Any]] = []
        for name, info in ProcessingConfig.model_fields.items():
            annotation = info.annotation
            type_name = getattr(annotation, "__name__", str(annotation))
            fields.append({
                "name": name,
                "type": type_name,
                "default": info.default,
                "description": info.description or "",
            })
        emit_result({"fields": fields})
    except Exception as exc:  # noqa: BLE001
        emit_error("SCHEMA_FAILED", str(exc))
        sys.exit(1)


@main.command("scan-dji-terra")
@click.option(
    "--folder", required=True, type=click.Path(), help="DJI Terra root folder path"
)
def scan_dji_terra_cmd(folder: str) -> None:
    """Scan a DJI Terra output folder and emit its asset manifest as JSON Lines."""
    click.echo(f"[heap-analyzer] scan-dji-terra called: folder={folder}", err=True)

    try:
        from heap_analyzer.io.dji_terra_scanner import (
            DJITerraIncompleteError,
            scan_dji_terra_folder,
        )

        manifest = scan_dji_terra_folder(Path(folder))

        # Convert to JSON-serializable dict (paths become strings, date → ISO).
        payload: dict[str, Any] = {
            "orthophoto_path": str(manifest.orthophoto_path),
            "dsm_path": str(manifest.dsm_path),
            "las_path": str(manifest.las_path),
            "crs": manifest.crs,
            "survey_date": manifest.survey_date.isoformat() if manifest.survey_date else None,
            "bbox": list(manifest.bbox) if manifest.bbox else None,
            "has_ground_classification": manifest.has_ground_classification,
            "pipeline_complete": manifest.pipeline_complete,
            "warnings": manifest.warnings,
        }
        emit_result(payload)

    except FileNotFoundError as exc:
        emit_error("FOLDER_NOT_FOUND", str(exc))
        sys.exit(1)
    except DJITerraIncompleteError as exc:
        emit_error("DJI_INCOMPLETE", str(exc))
        sys.exit(1)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        emit_error("DJI_SCAN_FAILED", f"Errore scansione DJI Terra: {exc}")
        click.echo(f"[heap-analyzer] ERROR: {exc}", err=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


@main.command("cross-section")
@click.option("--dsm", required=True, type=click.Path(exists=True), help="Path to DSM GeoTIFF")
@click.option("--dtm", required=True, type=click.Path(exists=True), help="Path to DTM GeoTIFF")
@click.option("--line", "line_str", required=True, help="Line coords as JSON or 'x1,y1;x2,y2'")
@click.option("--spacing", default=None, type=float, help="Sample spacing in meters")
def cross_section_cmd(dsm: str, dtm: str, line_str: str, spacing: float | None) -> None:
    """Extract DSM/DTM profile along a line. Emits JSON Lines."""
    click.echo(f"[heap-analyzer] cross-section called: dsm={dsm}", err=True)

    try:
        from heap_analyzer.processing.cross_section import extract_profile

        # Parse line: JSON GeoJSON LineString or "x1,y1;x2,y2" format
        if line_str.strip().startswith("{") or line_str.strip().startswith("["):
            parsed = json.loads(line_str)
            if isinstance(parsed, dict):
                coords = [(c[0], c[1]) for c in parsed["coordinates"]]
            else:
                coords = [(c[0], c[1]) for c in parsed]
        else:
            coords = []
            for seg in line_str.split(";"):
                x, y = seg.split(",")
                coords.append((float(x.strip()), float(y.strip())))

        emit_progress("cross_section", 0.0, "Estrazione profilo...")
        result = extract_profile(dsm, dtm, coords, spacing)
        emit_progress("cross_section", 100.0, "Profilo completato")
        emit_result(result)

    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        emit_error("CROSS_SECTION_FAILED", str(exc))
        click.echo(f"[heap-analyzer] ERROR: {exc}", err=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)



# ---------------------------------------------------------------------------
# VLM subcommands
# ---------------------------------------------------------------------------

@main.group()
def vlm() -> None:
    """VLM model management commands (GPU, download, load, unload)."""


def _get_models_dir(models_dir: str | None) -> Path:
    """Resolve the models directory from CLI arg or env var."""
    import os
    if models_dir:
        return Path(models_dir)
    env_dir = os.environ.get("HEAP_ANALYZER_MODELS_DIR")
    if env_dir:
        return Path(env_dir)
    return Path.home() / ".cache" / "heap-analyzer" / "models"


@vlm.command("gpu-info")
def vlm_gpu_info() -> None:
    """Report GPU hardware status. Emits JSON Lines."""
    from heap_analyzer.classification.vlm_service import VLMService

    svc = VLMService(models_dir=_get_models_dir(None))
    gpu = svc.check_gpu()
    emit_result(gpu.model_dump())


@vlm.command("list-models")
@click.option("--models-dir", default=None, type=click.Path(), help="Models directory")
def vlm_list_models(models_dir: str | None) -> None:
    """List available VLM models with download status. Emits JSON Lines."""
    from heap_analyzer.classification.vlm_service import VLMService

    svc = VLMService(models_dir=_get_models_dir(models_dir))
    models = svc.list_available_models()
    emit_result({"models": [m.model_dump() for m in models]})


@vlm.command("is-downloaded")
@click.option("--model", "model_name", required=True, help="Model short name")
@click.option("--models-dir", default=None, type=click.Path(), help="Models directory")
def vlm_is_downloaded(model_name: str, models_dir: str | None) -> None:
    """Check if a model is downloaded. Emits JSON Lines."""
    from heap_analyzer.classification.vlm_service import VLMService

    svc = VLMService(models_dir=_get_models_dir(models_dir))
    downloaded = svc.is_downloaded(model_name)
    emit_result({"downloaded": downloaded})


@vlm.command("download")
@click.option("--model", "model_name", required=True, help="Model short name")
@click.option("--models-dir", default=None, type=click.Path(), help="Models directory")
def vlm_download(model_name: str, models_dir: str | None) -> None:
    """Download a VLM model. Emits progress JSON Lines."""
    from heap_analyzer.classification.vlm_service import VLMService

    svc = VLMService(models_dir=_get_models_dir(models_dir))

    from heap_analyzer.classification.vlm_service import DownloadProgress

    def on_progress(p: DownloadProgress) -> None:
        emit_progress("vlm_download", p.percent, p.message)

    try:
        svc.download_model(model_name, progress_cb=on_progress)
        emit_result({"model": model_name, "downloaded": True})
    except Exception as exc:  # noqa: BLE001
        emit_error("VLM_DOWNLOAD_FAILED", str(exc))
        print(f"[heap-analyzer] VLM download error: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


def _parse_config(config_arg: str | None) -> ProcessingConfig:
    """Parse ProcessingConfig from --config argument.

    Args:
        config_arg: Path to JSON file, or None for defaults.

    Returns:
        ProcessingConfig instance.
    """
    if config_arg is None:
        return ProcessingConfig()

    config_path = Path(config_arg)
    if config_path.exists():
        # Read from file
        cfg_text = config_path.read_text(encoding="utf-8")
    else:
        # Try as inline JSON string
        cfg_text = config_arg

    try:
        cfg_dict = json.loads(cfg_text)
    except json.JSONDecodeError as exc:
        emit_error("INVALID_CONFIG", f"Config JSON non valido: {exc}")
        sys.exit(1)

    return ProcessingConfig(**cfg_dict)


if __name__ == "__main__":
    main()
