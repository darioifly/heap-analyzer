"""Pipeline benchmark — measures per-stage wall-clock and peak RAM.

Runs the full ProcessingPipeline against a LAS+TIFF pair and writes a JSON
report to the chosen output directory.

Not a test — this script is run by hand (or by F7.S04 CI later) to establish
and track performance baselines. SPEC targets:

  * Pipeline end-to-end (2 ha, 8M points): < 15 min
  * Peak RAM: < 16 GB
  * UI never blocks (main thread stalls < 50 ms)
  * 3D viewer ≥ 30 FPS sustained (measured separately in the browser)

Output never touches stdout as JSON Lines — this script does not speak the
IPC protocol. Progress goes to stderr.
"""

from __future__ import annotations

import datetime as dt
import json
import platform
import sys
import threading
import time
from pathlib import Path

import click


def _peak_ram_sampler(stop_event: threading.Event, peak_holder: list[float]) -> None:
    """Background thread: samples current-process RSS every 250 ms and
    updates ``peak_holder[0]`` (MB). Exits when ``stop_event`` is set.

    Runs best-effort — psutil import failure just leaves the holder at 0.
    """
    try:
        import psutil
    except ImportError:
        return
    proc = psutil.Process()
    while not stop_event.is_set():
        try:
            rss_mb = proc.memory_info().rss / (1024 * 1024)
            if rss_mb > peak_holder[0]:
                peak_holder[0] = rss_mb
        except Exception:  # noqa: BLE001
            pass
        stop_event.wait(0.25)


@click.command()
@click.option("--las", required=True, type=click.Path(exists=True), help="Input LAS/LAZ path")
@click.option("--tiff", required=True, type=click.Path(exists=True), help="Input GeoTIFF path")
@click.option("--output", required=True, type=click.Path(), help="Output directory for pipeline + report")
@click.option("--label", default=None, help="Short label for the dataset (shown in report)")
def main(las: str, tiff: str, output: str, label: str | None) -> None:
    """Run the processing pipeline and record per-stage metrics."""
    # Lazy import to keep script startup cheap
    from heap_analyzer.config import ProcessingConfig
    from heap_analyzer.pipeline import ProcessingPipeline

    las_path = Path(las)
    tiff_path = Path(tiff)
    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)

    click.echo(f"[benchmark] dataset: {las_path.name} + {tiff_path.name}", err=True)

    # RAM sampler
    peak_holder = [0.0]
    stop_event = threading.Event()
    sampler = threading.Thread(
        target=_peak_ram_sampler, args=(stop_event, peak_holder), daemon=True
    )
    sampler.start()

    # Per-stage durations: the pipeline reports progress in % per phase.
    # We track wall-clock between progress boundaries to derive stage durations.
    stage_starts: dict[str, float] = {}
    stage_durations: dict[str, float] = {}

    # Map progress percent bands -> phase names (see ProcessingPipeline.run)
    percent_phase_map = [
        (0, "dsm"),
        (25, "dtm"),
        (35, "ndsm"),
        (50, "segmentation"),
        (75, "volume"),
        (90, "tiles"),
        (98, "heatmap"),
    ]
    last_phase: str | None = None

    def progress_cb(pct: int, _msg: str) -> None:
        nonlocal last_phase
        now = time.time()
        # Resolve current phase by the highest threshold <= pct
        current = "dsm"
        for threshold, name in percent_phase_map:
            if pct >= threshold:
                current = name
        if current != last_phase:
            if last_phase is not None and last_phase in stage_starts:
                stage_durations[last_phase] = now - stage_starts[last_phase]
            stage_starts[current] = now
            last_phase = current

    cfg = ProcessingConfig()
    pipeline = ProcessingPipeline(cfg)

    t0 = time.time()
    try:
        result = pipeline.run(las_path, tiff_path, output_dir, progress_callback=progress_cb)
        total = time.time() - t0
        if last_phase is not None and last_phase in stage_starts:
            stage_durations[last_phase] = time.time() - stage_starts[last_phase]
    finally:
        stop_event.set()
        sampler.join(timeout=1.0)

    # Build report
    report = {
        "meta": {
            "timestamp": dt.datetime.now(dt.UTC).isoformat(),
            "label": label or las_path.stem,
            "dataset_las": str(las_path),
            "dataset_tiff": str(tiff_path),
            "cpu": platform.processor() or platform.machine(),
            "python": platform.python_version(),
            "os": f"{platform.system()} {platform.release()}",
        },
        "stages": [
            {"name": name, "duration_s": round(dur, 2)}
            for name, dur in stage_durations.items()
        ],
        "total_duration_s": round(total, 2),
        "peak_ram_mb": round(peak_holder[0], 1),
        "heap_count": len(result.heap_metrics),
        "warnings": result.warnings,
    }

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    report_path = output_dir / f"benchmark-{stamp}.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    click.echo(
        f"[benchmark] complete: total={report['total_duration_s']}s peak_ram={report['peak_ram_mb']}MB "
        f"heaps={report['heap_count']}",
        err=True,
    )
    click.echo(f"[benchmark] report saved: {report_path}", err=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        click.echo(f"[benchmark] FAILED: {exc}", err=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
