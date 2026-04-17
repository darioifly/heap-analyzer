"""Potree 2.0 point cloud conversion via PotreeConverter.

Converts LAS/LAZ files to Potree 2.0 octree format for 3D visualization.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

from pydantic import BaseModel

from heap_analyzer.utils.logging import get_stderr_logger

_log = get_stderr_logger(__name__)


class PotreeExportResult(BaseModel):
    """Result of Potree conversion."""

    output_dir: str
    metadata_path: str
    num_points: int
    bounds: dict[str, list[float]]
    success: bool
    error: str | None = None


def find_potree_converter(custom_path: str | None = None) -> Path | None:
    """Find PotreeConverter binary.

    Search order:
    1. custom_path argument (if provided)
    2. tools/PotreeConverter/ directory tree (recursive .exe search)
    3. System PATH

    Args:
        custom_path: Optional explicit path to PotreeConverter binary.

    Returns:
        Path to PotreeConverter binary, or None if not found.
    """
    # 1. Custom path
    if custom_path:
        p = Path(custom_path)
        if p.exists() and p.is_file():
            return p

    # 2. Project tools/ directory — walk up from this file to find project root
    current = Path(__file__).resolve()
    for parent in current.parents:
        tools_dir = parent / "tools" / "PotreeConverter"
        if tools_dir.exists():
            # Recursive search for PotreeConverter.exe (may be in subdirectory)
            for exe in tools_dir.rglob("PotreeConverter*.exe"):
                return exe
        # Stop at project root markers
        if (parent / "CLAUDE.md").exists() or (parent / "package.json").exists():
            break

    # 3. System PATH
    which_result = shutil.which("PotreeConverter")
    if which_result:
        return Path(which_result)

    return None


def export_for_potree(
    las_path: str,
    output_dir: str,
    potree_converter_path: str | None = None,
    progress_callback: Callable[[int, str], None] | None = None,
) -> PotreeExportResult:
    """Convert LAS/LAZ to Potree 2.0 format.

    Args:
        las_path: Path to input LAS/LAZ file.
        output_dir: Directory for Potree output files.
        potree_converter_path: Optional custom path to PotreeConverter binary.
        progress_callback: Optional callback(percent, message) for progress updates.

    Returns:
        PotreeExportResult with conversion details.
    """
    las_file = Path(las_path)
    out_dir = Path(output_dir)

    _empty_result = PotreeExportResult(
        output_dir=str(out_dir),
        metadata_path="",
        num_points=0,
        bounds={},
        success=False,
    )

    # Validate input
    if not las_file.exists():
        return _empty_result.model_copy(
            update={"error": f"LAS file not found: {las_file}"}
        )

    # Find PotreeConverter
    converter = find_potree_converter(potree_converter_path)
    if converter is None:
        return _empty_result.model_copy(
            update={
                "error": "PotreeConverter not found. "
                "Install it in tools/PotreeConverter/ or add to PATH."
            }
        )

    _log.info("Using PotreeConverter at: %s", converter)

    # Create output directory
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build command
    cmd = [str(converter), str(las_file), "-o", str(out_dir)]

    if progress_callback:
        progress_callback(0, "Avvio conversione Potree...")

    try:
        # Windows: CREATE_NO_WINDOW to avoid console flash
        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NO_WINDOW

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creation_flags,
        )

        # Parse progress from stdout
        stdout_lines: list[str] = []
        if process.stdout is not None:
            for line in process.stdout:
                line = line.strip()
                if line:
                    stdout_lines.append(line)
                    _log.debug("PotreeConverter: %s", line)
                    # PotreeConverter outputs progress like "xyz% ..."
                    if "%" in line:
                        try:
                            pct_str = line.split("%")[0].strip().split()[-1]
                            pct = int(float(pct_str))
                            if progress_callback:
                                progress_callback(min(pct, 99), f"Conversione: {pct}%")
                        except (ValueError, IndexError):
                            pass

        stderr_output = process.stderr.read() if process.stderr else ""
        return_code = process.wait()

        if return_code != 0:
            return _empty_result.model_copy(
                update={
                    "error": f"PotreeConverter failed (exit {return_code}): "
                    f"{stderr_output[:500]}"
                }
            )

    except FileNotFoundError:
        return _empty_result.model_copy(
            update={"error": f"PotreeConverter binary not executable: {converter}"}
        )
    except OSError as e:
        return _empty_result.model_copy(
            update={"error": f"OS error running PotreeConverter: {e}"}
        )

    # Read metadata.json
    metadata_path = out_dir / "metadata.json"
    if not metadata_path.exists():
        # Some PotreeConverter versions put output in a subdirectory
        for candidate in out_dir.rglob("metadata.json"):
            metadata_path = candidate
            break
        else:
            return _empty_result.model_copy(
                update={
                    "error": "PotreeConverter ran but metadata.json not found in output."
                }
            )

    with open(metadata_path, encoding="utf-8") as f:
        metadata = json.load(f)

    # Extract info from metadata
    num_points = metadata.get("points", 0)
    bb = metadata.get("boundingBox", {})
    bounds = {
        "min": [bb.get("lx", 0), bb.get("ly", 0), bb.get("lz", 0)],
        "max": [bb.get("ux", 0), bb.get("uy", 0), bb.get("uz", 0)],
    }

    if progress_callback:
        progress_callback(100, "Conversione completata")

    return PotreeExportResult(
        output_dir=str(metadata_path.parent),
        metadata_path=str(metadata_path),
        num_points=num_points,
        bounds=bounds,
        success=True,
    )
