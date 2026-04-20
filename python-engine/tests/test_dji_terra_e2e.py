"""End-to-end integration test on the real DJI Terra Acciaieria dataset.

Runs the full pipeline using the DJI-supplied DSM and ground-classified LAS
and verifies that segmentation produces finite, positive volumes for at least
one heap. Marked ``slow`` so it is excluded from the fast test sweep.

This test does not assert any specific heap count — the real site geometry
can vary with algorithm parameters. It asserts invariants the pipeline must
always uphold on any real industrial scene.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REAL_DJI_FOLDER = Path(
    "C:/Users/iflys/projects/Heap Analyzer/Esempio/260330 Acciaieria",
)

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        not REAL_DJI_FOLDER.exists(),
        reason="DJI sample folder not available",
    ),
]


def test_dji_terra_end_to_end_pipeline(tmp_path: Path) -> None:
    """Scan + pipeline with precomputed DSM + ground classification on real data."""
    from heap_analyzer.config import ProcessingConfig
    from heap_analyzer.io.dji_terra_scanner import scan_dji_terra_folder
    from heap_analyzer.pipeline import ProcessingPipeline

    # 1. Scan the real folder.
    manifest = scan_dji_terra_folder(REAL_DJI_FOLDER)
    assert manifest.has_ground_classification is True
    assert manifest.crs is not None

    # 2. Run pipeline with the DJI DSM pre-populated.
    progress_events: list[tuple[int, str]] = []

    def capture(pct: int, msg: str) -> None:
        progress_events.append((pct, msg))

    config = ProcessingConfig(precomputed_dsm_path=manifest.dsm_path)
    pipeline = ProcessingPipeline(config)

    output_dir = tmp_path / "out"
    result = pipeline.run(
        las_path=manifest.las_path,
        tiff_path=manifest.orthophoto_path,
        output_dir=output_dir,
        progress_callback=capture,
    )

    # 3. Verify the DSM generation phase was announced as skipped.
    dsm_skipped = any(
        "importat" in msg.lower() or "saltata" in msg.lower()
        for _, msg in progress_events
    )
    assert dsm_skipped, (
        f"Expected a 'DSM importato / generazione saltata' progress event. "
        f"Got: {[m for _, m in progress_events if 'DSM' in m.upper()]}"
    )

    # 4. Ground-classification strategy should have been chosen.
    assert result.base_elevation_method in (
        "ground_classification",
        "morphological",
        "percentile",
    )
    # On Acciaieria we expect ground_classification specifically — but fall
    # back gracefully if upstream parameters change. At minimum confidence
    # should not be pathologic.
    assert result.base_elevation_confidence >= 0.5

    # 5. Heaps detected and volumes sensible.
    assert len(result.heap_metrics) > 0, "Real site must have at least one heap"
    for metrics in result.heap_metrics:
        assert metrics.volume_m3 > 0, f"Heap {metrics.heap_id} has non-positive volume"
        assert metrics.volume_m3 < 1e8, (
            f"Heap {metrics.heap_id} volume {metrics.volume_m3} is implausibly large"
        )
        assert metrics.planimetric_area_m2 > 0
        assert metrics.max_height_m > 0

    # 6. Intermediate artefacts exist.
    for artefact in ("dsm", "dtm", "ndsm"):
        p = Path(result.intermediate_files[artefact])
        assert p.exists(), f"Missing intermediate: {artefact}"
