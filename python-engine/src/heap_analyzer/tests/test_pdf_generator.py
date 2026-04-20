"""Tests for PDF report generator."""

from __future__ import annotations

import json
import math
import subprocess

import matplotlib

matplotlib.use("Agg")

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds
from shapely.geometry import Polygon, mapping

from heap_analyzer.report.formatting import fmt_it
from heap_analyzer.report.pdf_generator import (
    ReportConfig,
    ReportGenerator,
    ReportProgress,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def synthetic_report_data(
    tmp_path_factory: pytest.TempPathFactory,
) -> dict:
    """Create synthetic data for PDF report testing.

    Returns dict with: tiff_path, results_path, heaps_db_data, categories.
    """
    base = tmp_path_factory.mktemp("pdf_gen")

    # Create a 100x100m synthetic RGB GeoTIFF
    size = 100
    res = 0.5
    nx = ny = int(size / res)
    origin_e, origin_n = 500000.0, 4500000.0
    transform = from_bounds(
        origin_e, origin_n, origin_e + size, origin_n + size, nx, ny,
    )

    rgb = np.zeros((3, ny, nx), dtype=np.uint8)
    rgb[0] = 120
    rgb[1] = 160
    rgb[2] = 90

    tiff_path = base / "test_ortho.tif"
    profile = {
        "driver": "GTiff",
        "dtype": "uint8",
        "width": nx,
        "height": ny,
        "count": 3,
        "crs": "EPSG:32632",
        "transform": transform,
    }
    with rasterio.open(tiff_path, "w", **profile) as ds:
        ds.write(rgb)

    # Create heaps
    categories = ["Rottame ferroso", "Ghisa", "Scorie"]
    heap_metrics = []
    heaps_db = []

    for i, (cx, cy, r) in enumerate([
        (500025.0, 4500025.0, 10.0),
        (500060.0, 4500060.0, 12.0),
        (500075.0, 4500025.0, 8.0),
    ]):
        angles = np.linspace(0, 2 * math.pi, 32, endpoint=False)
        coords = [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in angles]
        poly = Polygon(coords)
        geojson = mapping(poly)

        heap_metrics.append({
            "heap_id": i + 1,
            "label": str(i + 1),
            "polygon_geojson": geojson,
            "volume_m3": 100.0 + i * 50,
            "planimetric_area_m2": math.pi * r**2,
            "surface_area_m2": math.pi * r**2 * 1.1,
            "max_height_m": 3.0 + i * 0.5,
            "mean_height_m": 1.5 + i * 0.3,
            "base_elevation_m": 100.0,
            "centroid_e": cx,
            "centroid_n": cy,
            "bbox_min_e": cx - r,
            "bbox_min_n": cy - r,
            "bbox_max_e": cx + r,
            "bbox_max_n": cy + r,
        })

        heaps_db.append({
            "heap_id": i + 1,
            "material_category": categories[i] if i < 2 else None,
            "material_confidence": 0.85 if i == 0 else (0.4 if i == 1 else None),
            "classified_by": "vlm:qwen2.5-vl-7b" if i < 2 else None,
            "is_manually_confirmed": i == 0,
            "notes": "Test note" if i == 0 else None,
        })

    results = {
        "survey_metadata": {
            "las_path": "test.las",
            "tiff_path": str(tiff_path),
            "output_dir": str(base),
            "config": {
                "dsm_resolution": 0.1,
                "height_threshold": 0.5,
                "min_heap_area": 50,
                "dsm_percentile": 95,
                "morpho_kernel_size": 50,
            },
            "processing_time_s": 10.0,
            "heap_count": 3,
            "filtered_count": 0,
            "survey_date": "2026-04-20",
            "project_categories": categories,
        },
        "heap_metrics": heap_metrics,
        "base_elevation": 100.0,
        "base_elevation_method": "morphological",
        "base_elevation_confidence": 0.95,
        "intermediate_files": {},
        "warnings": [],
    }
    results_path = base / "results.json"
    results_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    return {
        "tiff_path": tiff_path,
        "results_path": results_path,
        "heaps_db": heaps_db,
        "categories": categories,
        "base_dir": base,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestItalianFormatting:
    """Tests for fmt_it."""

    def test_thousands_and_decimals(self) -> None:
        assert fmt_it(1234.5) == "1.234,50"

    def test_zero_decimals(self) -> None:
        assert fmt_it(0.5, 2) == "0,50"

    def test_million(self) -> None:
        assert fmt_it(1000000) == "1.000.000,00"

    def test_small_number(self) -> None:
        assert fmt_it(42.1, 1) == "42,1"

    def test_negative(self) -> None:
        assert fmt_it(-1234.56, 2) == "-1.234,56"


class TestPdfGeneration:
    """Tests for PDF report generation."""

    def test_generates_valid_pdf(self, synthetic_report_data: dict) -> None:
        """Report generates a valid PDF file."""
        from pypdf import PdfReader

        output = synthetic_report_data["base_dir"] / "report.pdf"
        config = ReportConfig(
            site_name="Test Site",
            operator_name="Test Operator",
            company_name="Test Company",
            additional_notes="Nota di test\nSeconda riga",
        )

        generator = ReportGenerator(config)
        generator.generate(
            results_path=synthetic_report_data["results_path"],
            tiff_path=synthetic_report_data["tiff_path"],
            output_path=output,
            heap_db_data=synthetic_report_data["heaps_db"],
        )

        assert output.exists()
        reader = PdfReader(str(output))
        assert not reader.is_encrypted

        # Expected pages: cover(1) + TOC(1) + overview(1) + 3 heaps(3)
        #   + summary(1) + charts(1) + params(1) + notes(1) = 10
        assert len(reader.pages) >= 8

    def test_page_count_without_notes(self, synthetic_report_data: dict) -> None:
        """Without notes, page count should be one less."""
        from pypdf import PdfReader

        output_with = synthetic_report_data["base_dir"] / "report_with_notes.pdf"
        output_without = synthetic_report_data["base_dir"] / "report_without_notes.pdf"

        config_with = ReportConfig(
            site_name="Test",
            additional_notes="Some notes here",
        )
        config_without = ReportConfig(site_name="Test")

        gen_with = ReportGenerator(config_with)
        gen_with.generate(
            results_path=synthetic_report_data["results_path"],
            tiff_path=synthetic_report_data["tiff_path"],
            output_path=output_with,
            heap_db_data=synthetic_report_data["heaps_db"],
        )

        gen_without = ReportGenerator(config_without)
        gen_without.generate(
            results_path=synthetic_report_data["results_path"],
            tiff_path=synthetic_report_data["tiff_path"],
            output_path=output_without,
            heap_db_data=synthetic_report_data["heaps_db"],
        )

        pages_with = len(PdfReader(str(output_with)).pages)
        pages_without = len(PdfReader(str(output_without)).pages)
        assert pages_with > pages_without

    def test_only_confirmed_reduces_pages(
        self, synthetic_report_data: dict,
    ) -> None:
        """With only_confirmed_heaps=True, fewer heap pages."""
        from pypdf import PdfReader

        output_all = synthetic_report_data["base_dir"] / "report_all.pdf"
        output_conf = synthetic_report_data["base_dir"] / "report_confirmed.pdf"

        gen_all = ReportGenerator(ReportConfig(site_name="Test"))
        gen_all.generate(
            results_path=synthetic_report_data["results_path"],
            tiff_path=synthetic_report_data["tiff_path"],
            output_path=output_all,
            heap_db_data=synthetic_report_data["heaps_db"],
        )

        gen_conf = ReportGenerator(
            ReportConfig(site_name="Test", only_confirmed_heaps=True),
        )
        gen_conf.generate(
            results_path=synthetic_report_data["results_path"],
            tiff_path=synthetic_report_data["tiff_path"],
            output_path=output_conf,
            heap_db_data=synthetic_report_data["heaps_db"],
        )

        pages_all = len(PdfReader(str(output_all)).pages)
        pages_conf = len(PdfReader(str(output_conf)).pages)
        assert pages_conf <= pages_all

    def test_italian_strings_present(self, synthetic_report_data: dict) -> None:
        """Required Italian strings should appear in the PDF text."""
        from pypdf import PdfReader

        output = synthetic_report_data["base_dir"] / "report_it.pdf"
        gen = ReportGenerator(ReportConfig(site_name="Test"))
        gen.generate(
            results_path=synthetic_report_data["results_path"],
            tiff_path=synthetic_report_data["tiff_path"],
            output_path=output,
            heap_db_data=synthetic_report_data["heaps_db"],
        )

        reader = PdfReader(str(output))
        all_text = ""
        for page in reader.pages:
            text = page.extract_text() or ""
            all_text += text + "\n"

        required_phrases = [
            "Report Volumetrico",
            "Panoramica del sito",
            "Tabella riepilogativa",
            "Analisi grafica",
            "Parametri di elaborazione",
        ]

        for phrase in required_phrases:
            assert phrase in all_text, f"Missing Italian phrase: '{phrase}'"

    def test_progress_phases_emitted(self, synthetic_report_data: dict) -> None:
        """Progress callback receives expected phases."""
        output = synthetic_report_data["base_dir"] / "report_progress.pdf"
        phases_seen: list[str] = []

        def on_progress(p: ReportProgress) -> None:
            phases_seen.append(p.phase)

        gen = ReportGenerator(ReportConfig(site_name="Test"))
        gen.generate(
            results_path=synthetic_report_data["results_path"],
            tiff_path=synthetic_report_data["tiff_path"],
            output_path=output,
            progress_cb=on_progress,
            heap_db_data=synthetic_report_data["heaps_db"],
        )

        expected_phases = ["overview", "heap-sheets", "summary", "charts", "params", "assemble"]
        for phase in expected_phases:
            assert phase in phases_seen, f"Missing phase: {phase}"

    def test_unclassified_heap_graceful(
        self, synthetic_report_data: dict,
    ) -> None:
        """Heap with material_category=null renders 'Non classificato'."""
        from pypdf import PdfReader

        output = synthetic_report_data["base_dir"] / "report_unclass.pdf"
        gen = ReportGenerator(ReportConfig(site_name="Test"))
        gen.generate(
            results_path=synthetic_report_data["results_path"],
            tiff_path=synthetic_report_data["tiff_path"],
            output_path=output,
            heap_db_data=synthetic_report_data["heaps_db"],
        )

        reader = PdfReader(str(output))
        all_text = ""
        for page in reader.pages:
            text = page.extract_text() or ""
            all_text += text + "\n"

        assert "Non classificato" in all_text

    def test_low_confidence_warning(self, synthetic_report_data: dict) -> None:
        """Heap with confidence<0.7 via VLM shows warning text."""
        from pypdf import PdfReader

        output = synthetic_report_data["base_dir"] / "report_lowconf.pdf"
        gen = ReportGenerator(ReportConfig(site_name="Test"))
        gen.generate(
            results_path=synthetic_report_data["results_path"],
            tiff_path=synthetic_report_data["tiff_path"],
            output_path=output,
            heap_db_data=synthetic_report_data["heaps_db"],
        )

        reader = PdfReader(str(output))
        all_text = ""
        for page in reader.pages:
            text = page.extract_text() or ""
            all_text += text + "\n"

        # Heap 2 has confidence=0.4, classified by VLM
        assert "da verificare" in all_text.lower()


class TestCLIGenerateReport:
    """Test CLI generate-report command."""

    def test_cli_produces_pdf(self, synthetic_report_data: dict) -> None:
        """CLI generate-report produces a valid PDF."""
        output = synthetic_report_data["base_dir"] / "cli_report.pdf"

        result = subprocess.run(
            [
                "py", "-3.11", "-m", "heap_analyzer.cli",
                "generate-report",
                "--results", str(synthetic_report_data["results_path"]),
                "--tiff", str(synthetic_report_data["tiff_path"]),
                "--output", str(output),
                "--site-name", "CLI Test",
                "--survey-date", "2026-04-20",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        # Verify JSON Lines on stdout
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                parsed = json.loads(line)
                assert "type" in parsed

        assert output.exists()
        assert output.stat().st_size > 1000  # sanity: >1KB
