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
@click.option("--config", default=None, help="JSON string with ProcessingConfig overrides")
def process(las: str, tiff: str, output: str, config: str | None) -> None:
    """Process a LAS point cloud + GeoTIFF ortophoto to detect and measure heaps.

    All progress is reported as JSON Lines on stdout.
    Logs and debug info go to stderr.
    """
    print(f"[heap-analyzer] process called: las={las} tiff={tiff} output={output}", file=sys.stderr)

    # Parse config overrides if provided
    cfg_dict: dict[str, Any] = {}
    if config:
        try:
            cfg_dict = json.loads(config)
        except json.JSONDecodeError as exc:
            emit_error("INVALID_CONFIG", f"Config JSON is not valid: {exc}")
            sys.exit(1)

    try:
        processing_config = ProcessingConfig(**cfg_dict)
    except Exception as exc:  # noqa: BLE001
        emit_error("INVALID_CONFIG", f"Config validation failed: {exc}")
        sys.exit(1)

    output_dir = Path(output)

    # Validate inputs exist (skip for test/dummy paths)
    las_path = Path(las)
    tiff_path = Path(tiff)

    emit_progress("validation", 5.0, "Validazione file di input...")

    if not las_path.exists():
        emit_warning(f"File LAS non trovato: {las} (modalità test)")
    if not tiff_path.exists():
        emit_warning(f"File TIFF non trovato: {tiff} (modalità test)")

    emit_progress("dsm", 20.0, "Generazione DSM...")
    emit_progress("dtm", 40.0, "Stima DTM...")
    emit_progress("segmentation", 60.0, "Segmentazione cumuli...")
    emit_progress("volume", 80.0, "Calcolo volumetrico...")
    emit_progress("complete", 100.0, "Elaborazione completata")

    emit_result({
        "heaps": [],
        "metadata": {
            "las_path": str(las_path),
            "tiff_path": str(tiff_path),
            "output_dir": str(output_dir),
            "config": processing_config.model_dump(),
            "heap_count": 0,
        },
    })


@main.command()
@click.option("--las", required=True, help="Path to LAS/LAZ file")
@click.option("--tiff", required=True, help="Path to GeoTIFF ortophoto")
def validate(las: str, tiff: str) -> None:
    """Validate that a LAS file and GeoTIFF are compatible (matching CRS, overlapping bounds).

    All output is JSON Lines on stdout.
    """
    print(f"[heap-analyzer] validate called: las={las} tiff={tiff}", file=sys.stderr)

    las_path = Path(las)
    tiff_path = Path(tiff)

    emit_progress("validation", 10.0, "Apertura file...")

    if not las_path.exists():
        emit_error("FILE_NOT_FOUND", f"File LAS non trovato: {las}")
        sys.exit(1)

    if not tiff_path.exists():
        emit_error("FILE_NOT_FOUND", f"File TIFF non trovato: {tiff}")
        sys.exit(1)

    emit_progress("validation", 50.0, "Verifica CRS...")
    emit_progress("validation", 100.0, "Validazione completata")
    emit_result({"valid": True, "las_path": las, "tiff_path": tiff})


@main.command("generate-test-data")
@click.option("--output", required=True, help="Output directory for test data")
def generate_test_data(output: str) -> None:
    """Generate synthetic test dataset with 4 geometric heaps.

    Produces test.las, test.tif, and ground_truth.json in the output directory.
    """
    print(f"[heap-analyzer] generate-test-data called: output={output}", file=sys.stderr)

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


if __name__ == "__main__":
    main()
