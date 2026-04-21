"""Potree 2.0 point cloud conversion via PotreeConverter.

Converts LAS/LAZ files to Potree 2.0 octree format for 3D visualization.
"""

from __future__ import annotations

import json
import shutil
import struct
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel

from heap_analyzer.utils.logging import get_stderr_logger

_log = get_stderr_logger(__name__)

# LAS 1.x public header block offsets for bbox doubles (little-endian).
# Applies to LAS 1.2, 1.3, 1.4 — these fields sit at fixed offsets.
_LAS_BBOX_OFFSET = 179  # Max X
_LAS_BBOX_STRUCT = "<dddddd"  # MaxX, MinX, MaxY, MinY, MaxZ, MinZ

# Tolerance (in CRS units) beyond which the LAS header bbox is considered
# inconsistent with the actual point extents and must be repaired before
# feeding the file to PotreeConverter (which rejects mismatches strictly).
_BBOX_TOLERANCE_M = 1e-4


def _repair_las_bbox_if_needed(las_path: Path) -> bool:
    """Validate and repair the LAS public header bounding box in-place.

    PotreeConverter 2.x aborts with "point outside bounding box" when any
    point falls outside the header's declared min/max. LAS files produced
    by some tools can have header bboxes that are slightly off (rounding
    during scale/offset application), so we re-scan the points and patch
    the header bytes when they disagree with reality.

    Only the 48 bytes of min/max X/Y/Z doubles are modified; point data
    and other header fields are untouched.

    Returns:
        True if the header was repaired, False if it was already valid.
    """
    try:
        import laspy
    except ImportError:  # pragma: no cover
        _log.warning("laspy not available; skipping LAS bbox repair")
        return False

    actual_min = [float("inf")] * 3
    actual_max = [float("-inf")] * 3

    with laspy.open(str(las_path)) as reader:
        header = reader.header
        h_min = (float(header.x_min), float(header.y_min), float(header.z_min))
        h_max = (float(header.x_max), float(header.y_max), float(header.z_max))

        for chunk in reader.chunk_iterator(1_000_000):
            xs, ys, zs = chunk.x, chunk.y, chunk.z
            actual_min[0] = min(actual_min[0], float(xs.min()))
            actual_min[1] = min(actual_min[1], float(ys.min()))
            actual_min[2] = min(actual_min[2], float(zs.min()))
            actual_max[0] = max(actual_max[0], float(xs.max()))
            actual_max[1] = max(actual_max[1], float(ys.max()))
            actual_max[2] = max(actual_max[2], float(zs.max()))

    needs_repair = False
    for i in range(3):
        if (
            abs(actual_min[i] - h_min[i]) > _BBOX_TOLERANCE_M
            or abs(actual_max[i] - h_max[i]) > _BBOX_TOLERANCE_M
        ):
            needs_repair = True
            break

    if not needs_repair:
        return False

    _log.warning(
        "LAS bbox header mismatch in %s: header min=%s max=%s, actual min=%s max=%s — patching header.",
        las_path.name, h_min, h_max, tuple(actual_min), tuple(actual_max),
    )

    packed = struct.pack(
        _LAS_BBOX_STRUCT,
        actual_max[0], actual_min[0],
        actual_max[1], actual_min[1],
        actual_max[2], actual_min[2],
    )
    with open(las_path, "r+b") as f:
        f.seek(_LAS_BBOX_OFFSET)
        f.write(packed)

    return True


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

    # Repair LAS bbox header if inconsistent — PotreeConverter rejects
    # files whose points fall outside the header-declared bounds.
    if progress_callback:
        progress_callback(0, "Verifica header LAS...")
    try:
        if _repair_las_bbox_if_needed(las_file):
            _log.info("LAS bbox header repaired: %s", las_file)
    except Exception as exc:  # noqa: BLE001
        _log.warning("LAS bbox repair failed (continuing anyway): %s", exc)

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

    # potree-core (the npm loader used by the frontend) only handles 8-bit
    # RGB — it decodes the color buffer as Uint8Array. PotreeConverter 2.x
    # emits 16-bit RGB whenever the source LAS has 16-bit RGB (the default
    # for LAS 1.2+, including DJI Terra), so without this post-processing
    # the cloud renders fully white in the 3D viewer. Downcast uint16 ->
    # uint8 by keeping the high byte of each channel, then patch the byte
    # offsets in hierarchy.bin and update metadata.json.
    try:
        if progress_callback:
            progress_callback(99, "Conversione RGB uint16->uint8...")
        _downcast_rgb_uint16_to_uint8(metadata_path.parent)
        with open(metadata_path, encoding="utf-8") as f:
            metadata = json.load(f)
    except Exception as exc:  # noqa: BLE001
        _log.warning("RGB downcast failed (continuing): %s", exc)

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


def _downcast_rgb_uint16_to_uint8(potree_dir: Path) -> None:
    """Rewrite octree.bin + hierarchy.bin + metadata.json so the rgb
    attribute becomes uint8 (3 bytes/point) instead of uint16 (6 bytes).

    potree-core's loader unconditionally decodes the color buffer as
    Uint8Array, so a 16-bit RGB attribute lands in the wrong bytes and
    every point renders saturated white. Keeping just the high byte of
    each channel preserves the real color with negligible quality loss
    (LAS typically stores 8-bit RGB shifted left by 8, so the low byte
    is zero anyway).

    The Potree 2.0 binary layout packs attributes contiguously per point.
    When we shrink the rgb attribute, every point's stride changes, so
    the byte offsets recorded in hierarchy.bin (for octree nodes) need
    to be scaled by new_point_size / old_point_size.

    Args:
        potree_dir: Directory containing metadata.json, octree.bin,
            hierarchy.bin.
    """
    import numpy as np

    meta_path = potree_dir / "metadata.json"
    with open(meta_path, encoding="utf-8") as f:
        metadata = json.load(f)

    attrs = metadata.get("attributes") or []
    rgb_idx = next((i for i, a in enumerate(attrs) if a.get("name") == "rgb"), None)
    if rgb_idx is None:
        _log.debug("No rgb attribute found — skipping RGB downcast")
        return
    rgb_attr = attrs[rgb_idx]
    if int(rgb_attr.get("elementSize", 2)) == 1:
        _log.debug("RGB already 8-bit — skipping downcast")
        return

    old_size = sum(int(a.get("size", 0)) for a in attrs)
    rgb_off = sum(int(a.get("size", 0)) for a in attrs[:rgb_idx])
    rgb_old_bytes = int(rgb_attr.get("size", 6))  # expected 6
    rgb_new_bytes = 3
    new_size = old_size - rgb_old_bytes + rgb_new_bytes
    _log.info(
        "Downcasting rgb: point size %d -> %d bytes (rgb offset %d)",
        old_size, new_size, rgb_off,
    )

    # --- Rewrite octree.bin ---
    oct_path = potree_dir / "octree.bin"
    raw_bytes = oct_path.read_bytes()
    n_points = len(raw_bytes) // old_size
    if n_points * old_size != len(raw_bytes):
        _log.warning(
            "octree.bin size %d is not a multiple of point size %d — aborting",
            len(raw_bytes), old_size,
        )
        return
    raw = np.frombuffer(raw_bytes, dtype=np.uint8).reshape(n_points, old_size)

    new = np.empty((n_points, new_size), dtype=np.uint8)
    # Bytes before rgb
    if rgb_off > 0:
        new[:, :rgb_off] = raw[:, :rgb_off]
    # Keep the HIGH byte of each uint16 channel (little-endian: byte 1/3/5).
    new[:, rgb_off + 0] = raw[:, rgb_off + 1]
    new[:, rgb_off + 1] = raw[:, rgb_off + 3]
    new[:, rgb_off + 2] = raw[:, rgb_off + 5]
    # Bytes after rgb (rgb is last in our layout, so this is a no-op)
    rest_old = rgb_off + rgb_old_bytes
    rest_new = rgb_off + rgb_new_bytes
    if old_size > rest_old:
        new[:, rest_new:] = raw[:, rest_old:]

    oct_path.write_bytes(new.tobytes())

    # --- Rewrite hierarchy.bin byte offsets ---
    # Potree 2.0 hierarchy entry = type(u1) + childMask(u1) + numPoints(u4) +
    # byteOffset(i8) + byteSize(i8) = 22 bytes. type=0 means a proxy entry
    # whose byteOffset points into hierarchy.bin itself (don't scale those);
    # type=1/2 are octree nodes (scale byteOffset and byteSize).
    hier_path = potree_dir / "hierarchy.bin"
    if hier_path.exists():
        hier_bytes = hier_path.read_bytes()
        entry_dtype = np.dtype(
            [
                ("type", "u1"),
                ("childMask", "u1"),
                ("numPoints", "u4"),
                ("byteOffset", "i8"),
                ("byteSize", "i8"),
            ]
        )
        if len(hier_bytes) % entry_dtype.itemsize == 0:
            entries = np.frombuffer(hier_bytes, dtype=entry_dtype).copy()
            is_octree_node = entries["type"] != 0
            scale_num = np.int64(new_size)
            scale_den = np.int64(old_size)
            entries["byteOffset"][is_octree_node] = (
                entries["byteOffset"][is_octree_node] * scale_num // scale_den
            )
            entries["byteSize"][is_octree_node] = (
                entries["byteSize"][is_octree_node] * scale_num // scale_den
            )
            hier_path.write_bytes(entries.tobytes())
        else:
            _log.warning(
                "hierarchy.bin size %d not a multiple of entry size %d — skipping rescale",
                len(hier_bytes), entry_dtype.itemsize,
            )

    # --- Update metadata.json ---
    rgb_attr["size"] = 3
    rgb_attr["elementSize"] = 1
    rgb_attr["type"] = "uint8"
    # Values had a max around 65280 (255 << 8); high byte is the real 0-255 value.
    rgb_attr["min"] = [max(0, int(v) >> 8) for v in rgb_attr.get("min", [0, 0, 0])]
    rgb_attr["max"] = [min(255, int(v) >> 8) for v in rgb_attr.get("max", [255, 255, 255])]

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    _log.info(
        "RGB downcast complete: rewrote %d points in octree.bin", n_points,
    )
