"""End-to-end processing pipeline: LAS+TIFF -> heaps with volumes.

Orchestrates the 5 phases:
  Phase 1 (0-25%):  Generate DSM from LAS
  Phase 2 (25-35%): Estimate DTM
  Phase 3 (35-50%): Compute nDSM + segment heaps
  Phase 4 (50-75%): Segment heaps with multi-criteria filters
  Phase 5 (75-100%): Compute full heap metrics
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from heap_analyzer.config import ProcessingConfig
from heap_analyzer.io.las_reader import LasReader
from heap_analyzer.io.tiff_reader import TiffReader
from heap_analyzer.processing.dsm import generate_dsm
from heap_analyzer.processing.dtm import DtmResult, estimate_dtm
from heap_analyzer.processing.segmentation import (
    SegmentationResult,
    compute_ndsm,
    segment_heaps,
)
from heap_analyzer.processing.volume import HeapMetrics, compute_heap_metrics
from heap_analyzer.utils.logging import get_stderr_logger

logger = get_stderr_logger(__name__)


class PipelineResult(BaseModel):
    """Complete pipeline output."""

    survey_metadata: dict[str, Any]
    heap_metrics: list[HeapMetrics]
    base_elevation: float
    base_elevation_method: str
    base_elevation_confidence: float
    intermediate_files: dict[str, str]
    warnings: list[str]


class ProcessingPipeline:
    """End-to-end pipeline: LAS+TIFF -> heaps with volumes."""

    def __init__(self, config: ProcessingConfig | None = None) -> None:
        """Initialize pipeline with optional config overrides.

        Args:
            config: Processing configuration. Uses defaults if None.
        """
        self.config = config or ProcessingConfig()
        logger.debug("Pipeline initialized with config: %s", self.config.model_dump())

    def validate_inputs(self, las_path: Path, tiff_path: Path) -> list[str]:
        """Return list of validation errors (empty if OK).

        Checks: files exist, LAS readable, TIFF readable, CRS compatible,
        bounds overlap.

        Args:
            las_path: Path to the LAS/LAZ file.
            tiff_path: Path to the GeoTIFF.

        Returns:
            List of error strings. Empty list = all OK.
        """
        errors: list[str] = []

        if not las_path.exists():
            errors.append(f"File LAS non trovato: {las_path}")
        if not tiff_path.exists():
            errors.append(f"File TIFF non trovato: {tiff_path}")

        if errors:
            return errors

        # Check LAS readable
        las_crs: str | None = None
        las_bounds: tuple[float, ...] | None = None
        try:
            with LasReader(las_path) as reader:
                meta = reader.get_metadata()
                las_crs = meta.crs
                las_bounds = (*meta.bounds_min[:2], *meta.bounds_max[:2])
                if not las_crs:
                    errors.append("File LAS senza CRS definito")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Errore lettura LAS: {exc}")

        # Check TIFF readable
        tiff_crs: str | None = None
        tiff_bounds: tuple[float, ...] | None = None
        try:
            tiff_reader = TiffReader(tiff_path)
            tiff_meta = tiff_reader.get_metadata()
            tiff_crs = tiff_meta.crs
            tiff_bounds = (
                tiff_meta.bounds[0],
                tiff_meta.bounds[1],
                tiff_meta.bounds[2],
                tiff_meta.bounds[3],
            )
            if not tiff_crs:
                errors.append("File TIFF senza CRS definito")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Errore lettura TIFF: {exc}")

        # Check CRS compatibility
        if las_crs and tiff_crs:
            tiff_reader_obj = TiffReader(tiff_path)
            if not tiff_reader_obj.check_crs_compatibility(las_crs):
                errors.append(
                    f"CRS non compatibili: LAS={las_crs}, TIFF={tiff_crs}"
                )

        # Check bounds overlap
        if las_bounds and tiff_bounds:
            if (
                las_bounds[2] < tiff_bounds[0]
                or las_bounds[0] > tiff_bounds[2]
                or las_bounds[3] < tiff_bounds[1]
                or las_bounds[1] > tiff_bounds[3]
            ):
                errors.append(
                    "LAS e TIFF non si sovrappongono spazialmente"
                )

        return errors

    def run(
        self,
        las_path: Path,
        tiff_path: Path,
        output_dir: Path,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> PipelineResult:
        """Run the full processing pipeline.

        Args:
            las_path: Path to input LAS/LAZ file.
            tiff_path: Path to input GeoTIFF ortophoto.
            output_dir: Directory for all outputs.
            progress_callback: Optional callback(percent, message).

        Returns:
            PipelineResult with metrics and metadata.
        """
        t0 = time.time()
        output_dir.mkdir(parents=True, exist_ok=True)
        warnings: list[str] = []

        def _progress(pct: int, msg: str) -> None:
            if progress_callback is not None:
                progress_callback(pct, msg)

        # --- Phase 1: Generate or import DSM (0-25%) ---
        dsm_path = output_dir / "dsm.tif"

        precomputed = self.config.precomputed_dsm_path
        if precomputed is not None and Path(precomputed).exists():
            # Skip DSM generation — reuse an externally-produced DSM (e.g. from
            # DJI Terra). Copy into the output layout so downstream phases find
            # it exactly where they expect.
            import shutil

            _progress(0, "Fase 1: Importazione DSM esterno...")
            shutil.copy2(Path(precomputed), dsm_path)
            logger.info("DSM imported from %s (generation skipped)", precomputed)
            _progress(
                25,
                "DSM importato (generazione saltata)",
            )
        else:
            _progress(0, "Fase 1: Generazione DSM...")

            def dsm_progress(pct: int, msg: str) -> None:
                # Scale 0-100 to 0-25
                _progress(int(pct * 0.25), f"DSM: {msg}")

            generate_dsm(las_path, dsm_path, self.config, progress_callback=dsm_progress)

        # --- Phase 2: Estimate DTM (25-35%) ---
        _progress(25, "Fase 2: Stima DTM...")
        dtm_path = output_dir / "dtm.tif"

        def dtm_progress(pct: int, msg: str) -> None:
            _progress(25 + int(pct * 0.10), f"DTM: {msg}")

        dtm_result: DtmResult = estimate_dtm(
            dsm_path, dtm_path, self.config,
            las_path=las_path,
            manual_base_elevation=self.config.manual_base_elevation,
            progress_callback=dtm_progress,
        )

        # --- Phase 3: Compute nDSM (35-50%) ---
        _progress(35, "Fase 3: Calcolo nDSM...")
        ndsm_path = output_dir / "ndsm.tif"
        compute_ndsm(dsm_path, dtm_path, ndsm_path)

        # --- Phase 4: Segment heaps (50-75%) ---
        _progress(50, "Fase 4: Segmentazione cumuli...")

        def seg_progress(pct: int, msg: str) -> None:
            _progress(50 + int(pct * 0.25), f"Segmentazione: {msg}")

        seg_result: SegmentationResult = segment_heaps(
            ndsm_path, self.config, progress_callback=seg_progress,
        )

        accepted = [h for h in seg_result.heaps if not h.is_filtered]
        filtered = [h for h in seg_result.heaps if h.is_filtered]

        if filtered:
            for h in filtered:
                warnings.append(
                    f"Cumulo {h.heap_id} filtrato: {h.filter_reason}"
                )

        # --- Phase 5: Compute metrics (75-100%) ---
        _progress(75, "Fase 5: Calcolo metriche volumetriche...")

        def vol_progress(pct: int, msg: str) -> None:
            _progress(75 + int(pct * 0.15), f"Volume: {msg}")

        metrics: list[HeapMetrics] = compute_heap_metrics(
            ndsm_path,
            seg_result.label_map_path,
            accepted,
            dtm_result.estimated_base_elevation,
            self.config,
            progress_callback=vol_progress,
        )

        # --- Phase 6: Generate tiles (90-100%) ---
        _progress(90, "Fase 6: Generazione tile ortofoto...")
        tiles_dir = output_dir / "tiles"

        try:
            from heap_analyzer.export.tile_generator import generate_tiles

            def tile_progress(pct: int, msg: str) -> None:
                _progress(90 + int(pct * 0.08), f"Tile: {msg}")

            tile_result = generate_tiles(
                tiff_path, tiles_dir, progress_callback=tile_progress,
            )
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Generazione tile fallita: {exc}")
            tile_result = None

        # Generate nDSM heatmap
        ndsm_heatmap_path = output_dir / "ndsm_heatmap.png"
        try:
            from heap_analyzer.export.heatmap_generator import generate_ndsm_heatmap

            _progress(98, "Generazione mappa altezze...")
            generate_ndsm_heatmap(
                ndsm_path, ndsm_heatmap_path,
                height_threshold=self.config.height_threshold,
            )
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Generazione heatmap fallita: {exc}")
            ndsm_heatmap_path = None

        elapsed = time.time() - t0

        # --- Build result ---
        _progress(100, "Elaborazione completata")

        intermediate_files = {
            "dsm": str(dsm_path),
            "dtm": str(dtm_path),
            "ndsm": str(ndsm_path),
            "label_map": str(seg_result.label_map_path),
        }
        if tile_result is not None:
            intermediate_files["tiles"] = str(tiles_dir)
            intermediate_files["tiles_metadata"] = str(tiles_dir / "metadata.json")
        if ndsm_heatmap_path is not None:
            intermediate_files["ndsm_heatmap"] = str(ndsm_heatmap_path)

        survey_metadata: dict[str, Any] = {
            "las_path": str(las_path),
            "tiff_path": str(tiff_path),
            "output_dir": str(output_dir),
            # mode='json' serialises Path / datetime to str so the dict round-
            # trips through json.dumps in the IPC bridge without a TypeError.
            "config": self.config.model_dump(mode="json"),
            "processing_time_s": round(elapsed, 1),
            "heap_count": len(metrics),
            "filtered_count": len(filtered),
        }

        # Read CRS from DSM
        try:
            import rasterio

            with rasterio.open(str(dsm_path)) as ds:
                survey_metadata["crs"] = str(ds.crs)
                survey_metadata["bounds"] = {
                    "min_e": ds.bounds.left,
                    "min_n": ds.bounds.bottom,
                    "max_e": ds.bounds.right,
                    "max_n": ds.bounds.top,
                }
        except Exception:  # noqa: BLE001
            pass

        result = PipelineResult(
            survey_metadata=survey_metadata,
            heap_metrics=metrics,
            base_elevation=dtm_result.estimated_base_elevation,
            base_elevation_method=dtm_result.method.value,
            base_elevation_confidence=dtm_result.confidence,
            intermediate_files=intermediate_files,
            warnings=warnings,
        )

        # Save results.json
        results_path = output_dir / "results.json"
        results_path.write_text(
            result.model_dump_json(indent=2), encoding="utf-8",
        )

        logger.debug(
            "Pipeline complete: %d heaps, %.1f s, results at %s",
            len(metrics), elapsed, results_path,
        )

        return result
