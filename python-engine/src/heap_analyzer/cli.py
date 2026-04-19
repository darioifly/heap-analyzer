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
def main() -> None:
    """Heap Analyzer — Volumetric analysis of material heaps from LiDAR point clouds."""


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
