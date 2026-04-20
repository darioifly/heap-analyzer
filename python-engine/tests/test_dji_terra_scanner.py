"""Tests for the DJI Terra folder scanner."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from heap_analyzer.io.dji_terra_scanner import (
    DJITerraIncompleteError,
    DJITerraManifest,
    scan_dji_terra_folder,
)

REAL_DJI_FOLDER = Path("C:/Users/iflys/projects/Heap Analyzer/Esempio/260330 Acciaieria")


def _touch_empty(path: Path) -> None:
    """Create an empty file plus any missing parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


def _make_minimal_dji_structure(root: Path, *, include_primary_dsm: bool = True) -> None:
    """Fabricate the minimum DJI-shaped tree for scanner happy-path probing.

    Files are empty placeholders — scanner tolerates read errors via warnings,
    which is what we want for structural tests.
    """
    if include_primary_dsm:
        _touch_empty(root / "map" / "dsm.tif")
    _touch_empty(root / "map" / "result.tif")
    _touch_empty(root / "models" / "pc" / "0" / "terra_las" / "cloud_merged.las")


# ---------------------------------------------------------------------------
# Real-dataset integration test (skipped if the sample isn't present)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not REAL_DJI_FOLDER.exists(),
    reason="DJI sample folder Esempio/260330 Acciaieria not available",
)
def test_scan_real_acciaieria_folder() -> None:
    """Real DJI Terra dataset scans cleanly and exposes all expected assets."""
    manifest = scan_dji_terra_folder(REAL_DJI_FOLDER)

    assert isinstance(manifest, DJITerraManifest)
    assert manifest.dsm_path.name == "dsm.tif"
    assert manifest.dsm_path.parent.name == "map"
    assert manifest.orthophoto_path.name == "result.tif"
    assert manifest.las_path.name == "cloud_merged.las"

    # This specific dataset has ASPRS ground classification populated.
    assert manifest.has_ground_classification is True

    # CRS must resolve from .prj sidecar; this site is UTM 33N (EPSG:32633).
    assert manifest.crs is not None
    assert re.match(r"^EPSG:32\d{3}$", manifest.crs), f"Unexpected CRS: {manifest.crs}"

    # BBox should be a 4-tuple with max > min.
    assert manifest.bbox is not None
    min_e, min_n, max_e, max_n = manifest.bbox
    assert max_e > min_e
    assert max_n > min_n

    # Pipeline sentinel is present in the sample folder.
    assert manifest.pipeline_complete is True


# ---------------------------------------------------------------------------
# Synthetic negative tests (structural)
# ---------------------------------------------------------------------------


def test_missing_folder_raises_filenotfound(tmp_path: Path) -> None:
    """A non-existent folder raises FileNotFoundError with Italian message."""
    missing = tmp_path / "does-not-exist"
    with pytest.raises(FileNotFoundError, match="non trovata"):
        scan_dji_terra_folder(missing)


def test_path_is_a_file_raises_filenotfound(tmp_path: Path) -> None:
    """A regular file (not a directory) raises FileNotFoundError."""
    f = tmp_path / "not-a-folder"
    f.write_text("", encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="non è una cartella"):
        scan_dji_terra_folder(f)


def test_empty_folder_raises_incomplete(tmp_path: Path) -> None:
    """Empty folder — missing DSM triggers DJITerraIncompleteError first."""
    root = tmp_path / "empty"
    root.mkdir()
    with pytest.raises(DJITerraIncompleteError, match="DSM non trovato"):
        scan_dji_terra_folder(root)


def test_missing_both_dsm_sources_raises_incomplete(tmp_path: Path) -> None:
    """If both primary and fallback DSM are absent, error is raised."""
    root = tmp_path / "no-dsm"
    _touch_empty(root / "map" / "result.tif")
    _touch_empty(root / "models" / "pc" / "0" / "terra_las" / "cloud_merged.las")
    # Note: no map/dsm.tif and no terra_dem/dem.tif.
    with pytest.raises(DJITerraIncompleteError, match="DSM non trovato"):
        scan_dji_terra_folder(root)


def test_missing_orthophoto_raises_incomplete(tmp_path: Path) -> None:
    """Missing map/result.tif triggers incomplete error."""
    root = tmp_path / "no-ortho"
    _touch_empty(root / "map" / "dsm.tif")
    _touch_empty(root / "models" / "pc" / "0" / "terra_las" / "cloud_merged.las")
    with pytest.raises(DJITerraIncompleteError, match="Ortofoto non trovata"):
        scan_dji_terra_folder(root)


def test_missing_las_raises_incomplete(tmp_path: Path) -> None:
    """Missing cloud_merged.las triggers incomplete error."""
    root = tmp_path / "no-las"
    _touch_empty(root / "map" / "dsm.tif")
    _touch_empty(root / "map" / "result.tif")
    with pytest.raises(DJITerraIncompleteError, match="Nuvola di punti non trovata"):
        scan_dji_terra_folder(root)


def test_fallback_dsm_when_primary_missing(tmp_path: Path) -> None:
    """terra_dem/dem.tif is used when map/dsm.tif is absent, with warning."""
    root = tmp_path / "fallback"
    _touch_empty(root / "map" / "result.tif")
    _touch_empty(root / "models" / "pc" / "0" / "terra_las" / "cloud_merged.las")
    _touch_empty(root / "models" / "pc" / "0" / "terra_dem" / "dem.tif")

    manifest = scan_dji_terra_folder(root)

    assert manifest.dsm_path.name == "dem.tif"
    assert manifest.dsm_path.parent.name == "terra_dem"
    assert any("fallback" in w.lower() for w in manifest.warnings)


def test_pipeline_sentinel_missing_adds_warning(tmp_path: Path) -> None:
    """Absence of map/2dPipeline_done produces a warning but doesn't fail."""
    root = tmp_path / "no-sentinel"
    _make_minimal_dji_structure(root)

    manifest = scan_dji_terra_folder(root)

    assert manifest.pipeline_complete is False
    assert any("2dPipeline_done" in w for w in manifest.warnings)


def test_pipeline_sentinel_present_no_warning(tmp_path: Path) -> None:
    """With sentinel file present, pipeline_complete=True and no related warning."""
    root = tmp_path / "sentinel"
    _make_minimal_dji_structure(root)
    _touch_empty(root / "map" / "2dPipeline_done")

    manifest = scan_dji_terra_folder(root)

    assert manifest.pipeline_complete is True
    assert not any("2dPipeline_done" in w for w in manifest.warnings)


def test_empty_placeholders_produce_warnings_not_exception(tmp_path: Path) -> None:
    """Empty TIFF/LAS files produce warnings (read failure) but manifest is built."""
    root = tmp_path / "unreadable"
    _make_minimal_dji_structure(root)
    _touch_empty(root / "map" / "2dPipeline_done")

    manifest = scan_dji_terra_folder(root)

    # The scanner tolerates read failures — no CRS, no bbox, no ground class.
    assert manifest.has_ground_classification is False
    assert manifest.bbox is None
    # CRS may be None or, on some platforms, parseable from an empty prj — accept both.
    # The invariant is that read failures become warnings.
    assert len(manifest.warnings) > 0
