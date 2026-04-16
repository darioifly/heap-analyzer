"""Tests for CSV export — verifies SPEC.md [EXPORT] compliance."""

import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from heap_analyzer.config import ProcessingConfig
from heap_analyzer.export.csv_export import CSV_HEADERS, export_csv
from heap_analyzer.pipeline import ProcessingPipeline
from heap_analyzer.processing.volume import HeapMetrics

# ---------------------------------------------------------------------------
# Test data paths
# ---------------------------------------------------------------------------

TEST_DATA_DIR = Path(__file__).resolve().parents[4] / "test-data"
OUTPUT_DIR = TEST_DATA_DIR / "output"


@pytest.fixture(scope="module")
def pipeline_result():
    """Run pipeline and return result."""
    config = ProcessingConfig()
    pipeline = ProcessingPipeline(config)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return pipeline.run(
        las_path=TEST_DATA_DIR / "test.las",
        tiff_path=TEST_DATA_DIR / "test.tif",
        output_dir=OUTPUT_DIR,
    )


@pytest.fixture(scope="module")
def csv_path(pipeline_result) -> Path:
    """Export CSV and return path."""
    path = OUTPUT_DIR / "heaps.csv"
    export_csv(
        pipeline_result.heap_metrics,
        {"survey_date": "2026-04-16"},
        path,
    )
    return path


# ---------------------------------------------------------------------------
# CSV format tests
# ---------------------------------------------------------------------------


class TestCsvFormat:
    def test_csv_file_created(self, csv_path: Path) -> None:
        """File exists after export."""
        assert csv_path.exists()

    def test_csv_has_bom(self, csv_path: Path) -> None:
        """First 3 bytes are UTF-8 BOM (EF BB BF)."""
        raw = csv_path.read_bytes()
        assert raw[:3] == b"\xef\xbb\xbf", (
            f"Missing UTF-8 BOM, first 3 bytes: {raw[:3].hex()}"
        )

    def test_csv_separator(self, csv_path: Path) -> None:
        """Lines contain ; not ,."""
        content = csv_path.read_text(encoding="utf-8-sig")
        lines = content.strip().splitlines()
        for line in lines:
            assert ";" in line, f"No semicolon in line: {line!r}"

    def test_csv_decimal_point(self, csv_path: Path) -> None:
        """Numeric values use . not , for decimals."""
        content = csv_path.read_text(encoding="utf-8-sig")
        lines = content.strip().splitlines()
        # Skip header, check data rows
        for line in lines[1:]:
            fields = line.split(";")
            for field in fields[1:13]:  # numeric fields
                if field:
                    assert "," not in field, (
                        f"Comma in numeric field: {field!r} (should use dot)"
                    )

    def test_csv_column_count(self, csv_path: Path) -> None:
        """Each row has 15 fields."""
        with open(csv_path, encoding="utf-8-sig") as f:
            reader = csv.reader(f, delimiter=";")
            for i, row in enumerate(reader):
                assert len(row) == 15, (
                    f"Row {i}: {len(row)} fields, expected 15"
                )

    def test_csv_header(self, csv_path: Path) -> None:
        """Header line matches exact Italian column names from SPEC."""
        with open(csv_path, encoding="utf-8-sig") as f:
            reader = csv.reader(f, delimiter=";")
            header = next(reader)
            assert header == CSV_HEADERS, (
                f"Header mismatch:\n  got:      {header}\n  expected: {CSV_HEADERS}"
            )

    def test_csv_data_rows(self, csv_path: Path, pipeline_result) -> None:
        """N data rows for N input metrics."""
        with open(csv_path, encoding="utf-8-sig") as f:
            reader = csv.reader(f, delimiter=";")
            rows = list(reader)
        data_rows = rows[1:]  # skip header
        assert len(data_rows) == len(pipeline_result.heap_metrics)

    def test_csv_excel_compatible(self, csv_path: Path) -> None:
        """Read back with csv.reader(delimiter=;) — row count and content match."""
        with open(csv_path, encoding="utf-8-sig") as f:
            reader = csv.reader(f, delimiter=";")
            rows = list(reader)
        assert len(rows) >= 2  # header + at least 1 data row
        # Verify first data row has numeric values
        first_data = rows[1]
        # Volume field should be parseable as float
        float(first_data[1])  # Volume_m3


class TestCsvCategories:
    def test_csv_empty_categories(self, pipeline_result, tmp_path: Path) -> None:
        """Heaps without category have empty Categoria_materiale field."""
        path = tmp_path / "no_cats.csv"
        export_csv(
            pipeline_result.heap_metrics,
            {"survey_date": "2026-04-16"},
            path,
        )
        with open(path, encoding="utf-8-sig") as f:
            reader = csv.reader(f, delimiter=";")
            next(reader)  # skip header
            for row in reader:
                assert row[13] == "", f"Expected empty category, got: {row[13]}"

    def test_csv_with_categories(self, pipeline_result, tmp_path: Path) -> None:
        """Heaps with category in dict show category name."""
        cats = {m.heap_id: "Rottame ferroso" for m in pipeline_result.heap_metrics}
        path = tmp_path / "with_cats.csv"
        export_csv(
            pipeline_result.heap_metrics,
            {"survey_date": "2026-04-16"},
            path,
            material_categories=cats,
        )
        with open(path, encoding="utf-8-sig") as f:
            reader = csv.reader(f, delimiter=";")
            next(reader)  # skip header
            for row in reader:
                assert row[13] == "Rottame ferroso", (
                    f"Expected category, got: {row[13]}"
                )


class TestCsvCli:
    def test_cli_export_csv(self, pipeline_result) -> None:
        """CLI export-csv command exits 0 and creates valid file."""
        results_path = OUTPUT_DIR / "results.json"
        assert results_path.exists(), "results.json not found"

        csv_out = OUTPUT_DIR / "cli_heaps.csv"

        _SCRIPT = shutil.which("heap-analyzer")
        cli_base = [_SCRIPT] if _SCRIPT else [sys.executable, "-m", "heap_analyzer.cli"]

        result = subprocess.run(
            [*cli_base, "export-csv",
             "--results", str(results_path),
             "--output", str(csv_out),
             "--survey-date", "2026-04-16"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
            timeout=60,
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert csv_out.exists()

        # Verify it's valid CSV
        with open(csv_out, encoding="utf-8-sig") as f:
            reader = csv.reader(f, delimiter=";")
            rows = list(reader)
        assert len(rows) >= 2  # header + data
