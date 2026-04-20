"""Smoke test for scripts/benchmark.py on the synthetic dataset.

Marked ``slow`` so CI can skip it via ``-m 'not slow'``.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.slow
def test_benchmark_runs_on_synthetic(tmp_path: Path) -> None:
    """End-to-end: generate synthetic dataset, run benchmark, validate report schema."""
    # 1) Generate the synthetic dataset
    dataset_dir = tmp_path / "dataset"
    gen_proc = subprocess.run(
        [sys.executable, "-m", "heap_analyzer", "generate-test-data", "--output", str(dataset_dir)],
        capture_output=True, text=True, check=False,
    )
    assert gen_proc.returncode == 0, f"generate-test-data failed: {gen_proc.stderr}"
    las = dataset_dir / "test.las"
    tif = dataset_dir / "test.tif"
    assert las.exists() and tif.exists()

    # 2) Run the benchmark script
    out_dir = tmp_path / "bench-out"
    script_path = (
        Path(__file__).resolve().parent.parent / "scripts" / "benchmark.py"
    )
    assert script_path.exists(), f"benchmark.py missing at {script_path}"

    bench_proc = subprocess.run(
        [sys.executable, str(script_path), "--las", str(las), "--tiff", str(tif),
         "--output", str(out_dir), "--label", "synthetic-smoke"],
        capture_output=True, text=True, check=False,
    )
    assert bench_proc.returncode == 0, f"benchmark failed: {bench_proc.stderr}"

    # 3) Validate report JSON
    reports = list(out_dir.glob("benchmark-*.json"))
    assert len(reports) == 1, f"Expected 1 report, got {reports}"
    report = json.loads(reports[0].read_text(encoding="utf-8"))

    assert "meta" in report
    assert "timestamp" in report["meta"]
    assert "label" in report["meta"]
    assert "stages" in report
    assert isinstance(report["stages"], list)
    assert "total_duration_s" in report
    assert isinstance(report["total_duration_s"], (int, float))
    assert "peak_ram_mb" in report
    assert "heap_count" in report
    assert report["heap_count"] >= 0
