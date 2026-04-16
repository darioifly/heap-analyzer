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
def generate_test_data(output: str) -> None:
    """Generate synthetic test dataset with 4 geometric heaps.

    Produces test.las, test.tif, and ground_truth.json in the output directory.
    """
    print(f"[heap-analyzer] generate-test-data called: output={output}", file=sys.stderr)

    try:
        from heap_analyzer.test_data_generator import create_test_site

        output_dir = Path(output)
        output_dir.mkdir(parents=True, exist_ok=True)

        emit_progress("setup", 5.0, "Inizializzazione generatore...")
        create_test_site(output_dir)
        emit_progress("complete", 100.0, "Dataset sintetico generato")
        emit_result({
            "output_dir": str(output_dir),
            "files": ["test.las", "test.tif", "ground_truth.json"],
        })
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        emit_error("GENERATOR_ERROR", f"Errore generazione dati: {exc}")
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
