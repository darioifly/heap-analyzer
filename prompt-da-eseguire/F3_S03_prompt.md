# F3.S03 — Point Cloud → Potree Conversion (PotreeConverter Integration)

## 🎯 CONTEXT

You are Claude Code working on the **Heap Analyzer** project (Electron + React + Python). Desktop Windows app for volumetric heap analysis from LAS point clouds + GeoTIFF orthophotos. Steel plant use case.

**Completed**: F0–F2 (setup, pipeline, UI 2D), **F3.S01** (polygon editing + volume recalc + undo/redo), **F3.S02** (base elevation override + ground selection).

**Current task**: **F3.S03 — Point Cloud → Potree Conversion**. This is task 3 of 5 in F3. This task is **backend-only** (Python + Electron IPC + Express static serving). The Potree 3D viewer (F3.S04) will consume the output of this task.

---

## 📚 AUTHORITATIVE REFERENCES (READ FIRST)

1. `docs/SPEC.md` — section [UI] Vista 3D (Potree), section [LIBS] (PotreeConverter 2.x).
2. `docs/DEV-PLAN.md` — locate F3.S03.
3. `CLAUDE.md` — persistent instructions.
4. `docs/reports/F3.S01-report.md` and `docs/reports/F3.S02-report.md` — understand current state.

**Key SPEC facts**:
- Potree manages: octree LOD, frustum culling, streaming nodes.
- Output format: Potree 2.0 (`metadata.json` + `hierarchy.bin` + octree `.bin` nodes).
- PotreeConverter = external binary. **DO NOT reimplement octree.**

---

## 🔒 CRITICAL RULES (NON-NEGOTIABLE)

### Runtime
- ❌ **DO NOT** run `npm run dev`, `npm run start`, or any dev server — already running in hot-reload.
- ✅ **DO** run tests: `npm run test`, `cd python-engine && pytest`, `npm run typecheck`, `npm run lint`.

### IPC protocol
- Python stdout = **JSON Lines only** with `"type"` field.
- **ZERO `print()` on stdout.**

### Git
- **Single branch `main`. NO feature branches.**
- After each step with green tests:
  ```bash
  git add -A && git commit -m "F3.S03: <description>" && git push origin main
  ```

### MCP plugins
- **Context7 MANDATORY** before: `laspy` (point format, color extraction), PotreeConverter CLI flags.
- **Sequential Thinking RECOMMENDED** for: fallback strategy design.
- **Memory**: save task summary at the end.

### Windows environment
- Working dir: `C:\Users\iflys\projects\Heap Analyzer` (space in path).
- Python 3.11, Node.js, Git all configured.
- GitHub: `darioifly/heap-analyzer`, branch `main`.

---

## 🧠 DESIGN DECISIONS

### D1: PotreeConverter availability — detect at runtime with graceful fallback

The user is **unsure** if PotreeConverter is installed. The implementation MUST:

1. **Detect** PotreeConverter at runtime by searching:
   a. `PATH` environment variable (run `where PotreeConverter` or `where PotreeConverter2` on Windows).
   b. Project-local path: `<project_root>/tools/PotreeConverter/PotreeConverter.exe`.
   c. Common install locations: `C:\PotreeConverter\PotreeConverter.exe`, `C:\Program Files\PotreeConverter\PotreeConverter.exe`.
   d. User-configurable path stored in settings (for future F7.S02 — for now, read from env var `POTREE_CONVERTER_PATH` if set).

2. **If found**: use it directly (preferred path — best performance and output quality).

3. **If NOT found**: implement a **pure-Python fallback** using `laspy` + custom octree-free conversion to Potree 2.0 format. This fallback:
   - Reads the LAS file (chunked for large files).
   - Writes a simplified Potree 2.0 structure: `metadata.json` + a single flat `octree.bin` containing all points (no hierarchical LOD).
   - This is **functional but NOT performant** for large clouds (>10M points will be slow to render without LOD). Acceptable for synthetic datasets and small real scans.
   - Logs a clear **warning** to the user: `PotreeConverter non trovato. Conversione fallback attiva — la visualizzazione 3D potrebbe essere lenta per file grandi. Installare PotreeConverter 2.x per prestazioni ottimali: https://github.com/potree/PotreeConverter/releases`

4. **If neither works**: return an error with clear instructions for the user to install PotreeConverter.

🏆 **Best practice — graceful degradation**: the app must NEVER crash or show a cryptic error because a binary is missing. The fallback ensures F3.S04 (viewer) can be developed and tested even without PotreeConverter installed.

### D2: Output directory structure

For a survey with `id=5`, the Potree output goes to:
```
<survey_output_dir>/potree/
  metadata.json
  hierarchy.bin
  octree.bin     (or multiple node files if PotreeConverter produces them)
```

The path is stored in the DB: `surveys.potree_path TEXT`.

### D3: Express static serving

The existing tile server (from F2.S06) already serves tiles via Express. Extend it to also serve the Potree output directory as static files under a route like `/potree/<surveyId>/...`. The Potree viewer (F3.S04) will fetch from this URL.

---

## 📋 IMPLEMENTATION STEPS

### STEP 0 — Read project state (5 min)

1. Read `CLAUDE.md`, `docs/SPEC.md` (3D sections), `docs/DEV-PLAN.md` (F3.S03).
2. Read recent reports: `docs/reports/F3.S01-report.md`, `docs/reports/F3.S02-report.md`.
3. Examine existing code:
   - `python-engine/src/heap_analyzer/io/las_reader.py` — understand `LasReader`, `iter_chunks`, `get_metadata`.
   - `python-engine/src/heap_analyzer/cli.py` — understand CLI pattern.
   - `electron/src/ipc/handlers.ts` — current handler registration.
   - Look for the Express tile server setup (from F2.S06): find where `express()` is configured, typically in `electron/src/main.ts` or a `services/tile-server.ts`. This is where we'll add the Potree static route.
4. Capture baseline test counts:
   ```bash
   cd python-engine && pytest -q 2>&1 | tail -3
   cd .. && npm run test -- --run 2>&1 | tail -5
   ```
5. `git log --oneline -8` — confirm F3.S02 commits are present.

**No commit in this step.**

---

### STEP 1 — Python: PotreeConverter detection + wrapper (25 min)

**Goal**: a module that detects PotreeConverter on the system and wraps its CLI.

#### 1.1 Context7 lookup (MANDATORY)

Query Context7 for:
- `laspy` — point format fields, color attributes (`red`, `green`, `blue`), `ScaleAwarePointRecord`.
- Search web for `PotreeConverter 2.x CLI flags` — especially `--outdir`, `--generate-page`, `--overwrite`, output format options.

#### 1.2 New module `python-engine/src/heap_analyzer/export/pointcloud_export.py`

```python
"""Point cloud export to Potree 2.0 format for 3D visualization."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

import numpy as np

from heap_analyzer.config import ProcessingConfig
from heap_analyzer.io.las_reader import LasReader


def find_potree_converter() -> Optional[Path]:
    """Detect PotreeConverter binary on the system.
    
    Search order:
      1. POTREE_CONVERTER_PATH env var (explicit override)
      2. System PATH (where/which)
      3. Project-local: ./tools/PotreeConverter/PotreeConverter.exe
      4. Common Windows locations
    
    Returns:
        Path to the executable, or None if not found.
    """
    # 1. Env var
    env_path = os.environ.get("POTREE_CONVERTER_PATH")
    if env_path and Path(env_path).is_file():
        return Path(env_path)
    
    # 2. System PATH
    which = shutil.which("PotreeConverter") or shutil.which("PotreeConverter2")
    if which:
        return Path(which)
    
    # 3. Project-local
    project_local = Path(__file__).resolve().parents[4] / "tools" / "PotreeConverter" / "PotreeConverter.exe"
    if project_local.is_file():
        return project_local
    
    # 4. Common Windows locations
    for candidate in [
        Path(r"C:\PotreeConverter\PotreeConverter.exe"),
        Path(r"C:\PotreeConverter2\PotreeConverter.exe"),
        Path(r"C:\Program Files\PotreeConverter\PotreeConverter.exe"),
        Path(os.path.expanduser("~")) / "PotreeConverter" / "PotreeConverter.exe",
    ]:
        if candidate.is_file():
            return candidate
    
    return None


def export_for_potree(
    las_path: str,
    output_dir: str,
    config: Optional[ProcessingConfig] = None,
    emit_progress=None,
) -> dict:
    """Convert LAS/LAZ to Potree 2.0 format.
    
    Tries PotreeConverter binary first; falls back to pure-Python conversion.
    
    Args:
        las_path: path to LAS/LAZ file
        output_dir: directory to write Potree output
        config: processing config (optional)
        emit_progress: callable(dict) to emit JSON Lines progress messages
    
    Returns:
        {
            "method": "PotreeConverter" | "python-fallback",
            "output_dir": str,
            "metadata_path": str,
            "num_points": int,
            "warnings": list[str],
        }
    
    Raises:
        FileNotFoundError: if las_path does not exist
        RuntimeError: if conversion fails
    """
    las_path = Path(las_path)
    output_dir = Path(output_dir)
    
    if not las_path.is_file():
        raise FileNotFoundError(f"LAS file not found: {las_path}")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    converter = find_potree_converter()
    
    if converter:
        return _convert_with_potree_converter(las_path, output_dir, converter, emit_progress)
    else:
        return _convert_python_fallback(las_path, output_dir, emit_progress)


def _convert_with_potree_converter(
    las_path: Path, output_dir: Path, converter_path: Path, emit_progress
) -> dict:
    """Use PotreeConverter binary for high-quality octree conversion."""
    if emit_progress:
        emit_progress({
            "type": "progress", "phase": "potree_convert",
            "percent": 10, "message": f"Conversione con PotreeConverter ({converter_path.name})..."
        })
    
    cmd = [
        str(converter_path),
        str(las_path),
        "-o", str(output_dir),
        "--overwrite",
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 min timeout for large files
            cwd=str(output_dir.parent),
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("PotreeConverter timed out after 10 minutes")
    except FileNotFoundError:
        raise RuntimeError(f"PotreeConverter binary not executable: {converter_path}")
    
    if result.returncode != 0:
        raise RuntimeError(
            f"PotreeConverter failed (exit {result.returncode}): {result.stderr[:500]}"
        )
    
    # Log PotreeConverter output to stderr (not stdout)
    if result.stdout:
        print(result.stdout, file=sys.stderr)
    
    metadata_path = output_dir / "metadata.json"
    if not metadata_path.is_file():
        raise RuntimeError(
            f"PotreeConverter did not produce metadata.json in {output_dir}. "
            f"Contents: {list(output_dir.iterdir())}"
        )
    
    with open(metadata_path) as f:
        metadata = json.load(f)
    
    num_points = metadata.get("points", 0)
    
    if emit_progress:
        emit_progress({
            "type": "progress", "phase": "potree_convert",
            "percent": 100, "message": f"Conversione completata ({num_points:,} punti)"
        })
    
    return {
        "method": "PotreeConverter",
        "output_dir": str(output_dir),
        "metadata_path": str(metadata_path),
        "num_points": num_points,
        "warnings": [],
    }
```

#### 1.3 Pure-Python fallback: `_convert_python_fallback`

This is the key fallback. It produces a **minimal Potree 2.0 compatible structure** without hierarchical LOD.

🏆 **Best practice — minimal viable Potree**: Potree 2.0 format expects `metadata.json` with bounding box, scale, offset, point attributes, and a hierarchy. For the fallback, we generate a **single root node** containing all points. This works for small-to-medium clouds; large clouds will load slowly but won't crash.

```python
def _convert_python_fallback(
    las_path: Path, output_dir: Path, emit_progress
) -> dict:
    """Pure-Python fallback: produce a minimal Potree 2.0 structure.
    
    WARNING: no hierarchical LOD. Large point clouds (>10M points)
    will render slowly. PotreeConverter is recommended for production use.
    """
    warnings = [
        "PotreeConverter non trovato. Conversione fallback Python attiva — "
        "la visualizzazione 3D potrebbe essere lenta per file grandi. "
        "Installare PotreeConverter 2.x per prestazioni ottimali: "
        "https://github.com/potree/PotreeConverter/releases"
    ]
    
    if emit_progress:
        emit_progress({
            "type": "warning",
            "message": warnings[0],
        })
        emit_progress({
            "type": "progress", "phase": "potree_convert",
            "percent": 10, "message": "Lettura nuvola di punti (fallback Python)..."
        })
    
    reader = LasReader(str(las_path))
    meta = reader.get_metadata()
    
    # Read all points (chunked to control memory)
    all_xyz = []
    all_rgb = []
    total_read = 0
    
    for chunk in reader.iter_chunks(chunk_size=1_000_000):
        xyz = np.column_stack([chunk.x, chunk.y, chunk.z])
        all_xyz.append(xyz)
        
        # Try to get RGB colors
        if hasattr(chunk, 'red') and hasattr(chunk, 'green') and hasattr(chunk, 'blue'):
            rgb = np.column_stack([
                (chunk.red / 256).astype(np.uint8),
                (chunk.green / 256).astype(np.uint8),
                (chunk.blue / 256).astype(np.uint8),
            ])
            all_rgb.append(rgb)
        
        total_read += len(chunk)
        if emit_progress:
            pct = min(10 + int(60 * total_read / meta.num_points), 70)
            emit_progress({
                "type": "progress", "phase": "potree_convert",
                "percent": pct,
                "message": f"Letti {total_read:,} / {meta.num_points:,} punti..."
            })
    
    xyz = np.concatenate(all_xyz)
    has_color = len(all_rgb) > 0 and len(all_rgb) == len(all_xyz)
    rgb = np.concatenate(all_rgb) if has_color else None
    
    if emit_progress:
        emit_progress({
            "type": "progress", "phase": "potree_convert",
            "percent": 75, "message": "Scrittura formato Potree..."
        })
    
    # Compute bounding box
    bb_min = xyz.min(axis=0)
    bb_max = xyz.max(axis=0)
    
    # Potree 2.0 uses offset + scale to encode positions as int32
    offset = bb_min.copy()
    extent = bb_max - bb_min
    # Scale: aim for ~1mm precision
    scale = np.full(3, 0.001)
    
    # Encode positions as int32
    positions_int = ((xyz - offset) / scale).astype(np.int32)
    
    # Write octree.bin (flat, single node)
    octree_dir = output_dir / "octree"
    octree_dir.mkdir(parents=True, exist_ok=True)
    node_path = octree_dir / "r.bin"
    
    # Binary layout: for each point, write x(4) y(4) z(4) [r(1) g(1) b(1) a(1)]
    with open(node_path, "wb") as f:
        for i in range(len(positions_int)):
            f.write(positions_int[i].tobytes())
            if has_color:
                f.write(bytes([rgb[i, 0], rgb[i, 1], rgb[i, 2], 255]))
    
    # Write hierarchy.bin (single root node)
    # Potree 2.0 hierarchy: each node entry = type(1) + childMask(1) + numPoints(4) + byteOffset(8) + byteSize(8)
    hierarchy_path = output_dir / "hierarchy.bin"
    import struct
    with open(hierarchy_path, "wb") as f:
        node_size = node_path.stat().st_size
        # type=2 (proxy/leaf), childMask=0 (no children), numPoints, byteOffset=0, byteSize
        f.write(struct.pack("<BBIqq", 2, 0, len(xyz), 0, node_size))
    
    # Build attributes list
    attributes = [
        {
            "name": "position",
            "description": "",
            "size": 12,
            "numElements": 3,
            "elementSize": 4,
            "type": "int32",
            "min": bb_min.tolist(),
            "max": bb_max.tolist(),
        }
    ]
    byte_per_point = 12
    
    if has_color:
        attributes.append({
            "name": "rgba",
            "description": "",
            "size": 4,
            "numElements": 4,
            "elementSize": 1,
            "type": "uint8",
            "min": [0, 0, 0, 0],
            "max": [255, 255, 255, 255],
        })
        byte_per_point += 4
    
    # Write metadata.json (Potree 2.0 format)
    metadata = {
        "version": "2.0",
        "name": las_path.stem,
        "description": "",
        "points": len(xyz),
        "projection": meta.crs or "",
        "hierarchy": {
            "firstChunkSize": hierarchy_path.stat().st_size,
            "stepSize": 4,
            "depth": 0,
        },
        "offset": offset.tolist(),
        "scale": scale.tolist(),
        "spacing": float(extent.max() / 128),
        "boundingBox": {
            "min": bb_min.tolist(),
            "max": bb_max.tolist(),
        },
        "encoding": "default",
        "attributes": attributes,
    }
    
    metadata_path = output_dir / "metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    
    if emit_progress:
        emit_progress({
            "type": "progress", "phase": "potree_convert",
            "percent": 100,
            "message": f"Conversione completata (fallback, {len(xyz):,} punti)"
        })
    
    return {
        "method": "python-fallback",
        "output_dir": str(output_dir),
        "metadata_path": str(metadata_path),
        "num_points": len(xyz),
        "warnings": warnings,
    }
```

**IMPORTANT NOTE**: The binary layout above is a best-effort approximation of Potree 2.0 format. When implementing, you MUST:
1. Use **Sequential Thinking** to verify the exact Potree 2.0 binary specification against the actual Potree viewer source code or documentation.
2. Search Context7 or web for `Potree 2.0 binary format specification` to confirm: byte order, hierarchy entry layout, attribute encoding.
3. Test that the output is actually loadable by the Potree viewer (this will be fully validated in F3.S04, but the metadata.json structure should match expectations).

If the exact binary format is uncertain, **prioritize getting metadata.json correct** (this is well-documented) and write the octree.bin in the simplest valid format. The fallback is meant to be functional, not optimal.

#### 1.4 CLI subcommand

Add to `cli.py`:

```python
@cli.command("export-pointcloud")
@click.option("--las", required=True, type=click.Path(exists=True))
@click.option("--output", required=True, type=click.Path())
@click.option("--config", default=None)
def export_pointcloud_cmd(las, output, config):
    """Convert LAS/LAZ to Potree 2.0 format for 3D visualization."""
    try:
        cfg = ProcessingConfig.model_validate_json(config) if config else ProcessingConfig()
        result = export_for_potree(las, output, cfg, emit_progress=emit)
        for w in result.get("warnings", []):
            emit({"type": "warning", "message": w})
        emit({"type": "result", "data": result})
    except Exception as e:
        emit({"type": "error", "code": "POTREE_EXPORT_FAILED", "message": str(e)})
        sys.exit(1)
```

#### 1.5 Run & commit

```bash
cd python-engine
pytest tests/test_pointcloud_export.py -v  # (created in STEP 2)
# ... will be added in the test step
```

Wait — write tests first (STEP 2), then run together.

---

### STEP 2 — Python: tests for pointcloud export (20 min)

Create `python-engine/tests/test_pointcloud_export.py`:

```python
"""Tests for Potree conversion (F3.S03)."""

import json
import os
import struct
from pathlib import Path

import numpy as np
import pytest

from heap_analyzer.export.pointcloud_export import (
    export_for_potree,
    find_potree_converter,
    _convert_python_fallback,
)


class TestFindPotreeConverter:
    def test_returns_path_or_none(self):
        """find_potree_converter returns a Path or None — never raises."""
        result = find_potree_converter()
        assert result is None or isinstance(result, Path)
    
    def test_respects_env_var(self, tmp_path, monkeypatch):
        """POTREE_CONVERTER_PATH env var is checked first."""
        fake = tmp_path / "FakePotreeConverter.exe"
        fake.write_text("fake")
        monkeypatch.setenv("POTREE_CONVERTER_PATH", str(fake))
        result = find_potree_converter()
        assert result == fake
    
    def test_env_var_nonexistent_file_skipped(self, monkeypatch):
        """If env var points to nonexistent file, skip it."""
        monkeypatch.setenv("POTREE_CONVERTER_PATH", r"C:\nonexistent\fake.exe")
        # Should not raise, should fall through to other methods
        result = find_potree_converter()
        # Result depends on system — just verify no crash
        assert result is None or isinstance(result, Path)


class TestPythonFallback:
    def test_fallback_produces_valid_structure(self, synthetic_site, tmp_path):
        """Fallback conversion produces metadata.json + hierarchy.bin + octree/r.bin."""
        output_dir = tmp_path / "potree_output"
        result = _convert_python_fallback(
            Path(synthetic_site.las_path), output_dir, emit_progress=None
        )
        
        assert result["method"] == "python-fallback"
        assert len(result["warnings"]) > 0  # must warn about fallback
        
        # Check file structure
        assert (output_dir / "metadata.json").is_file()
        assert (output_dir / "hierarchy.bin").is_file()
        assert (output_dir / "octree" / "r.bin").is_file()
    
    def test_fallback_metadata_has_required_fields(self, synthetic_site, tmp_path):
        """metadata.json must have version, points, boundingBox, attributes, offset, scale."""
        output_dir = tmp_path / "potree_output"
        _convert_python_fallback(Path(synthetic_site.las_path), output_dir, None)
        
        with open(output_dir / "metadata.json") as f:
            meta = json.load(f)
        
        assert meta["version"] == "2.0"
        assert meta["points"] > 0
        assert "boundingBox" in meta
        assert "min" in meta["boundingBox"]
        assert "max" in meta["boundingBox"]
        assert len(meta["boundingBox"]["min"]) == 3
        assert len(meta["boundingBox"]["max"]) == 3
        assert "attributes" in meta
        assert any(a["name"] == "position" for a in meta["attributes"])
        assert "offset" in meta
        assert "scale" in meta
        assert len(meta["offset"]) == 3
        assert len(meta["scale"]) == 3
    
    def test_fallback_bounding_box_matches_las(self, synthetic_site, tmp_path):
        """Potree bounding box must match LAS file bounds within tolerance."""
        from heap_analyzer.io.las_reader import LasReader
        
        output_dir = tmp_path / "potree_output"
        _convert_python_fallback(Path(synthetic_site.las_path), output_dir, None)
        
        with open(output_dir / "metadata.json") as f:
            meta = json.load(f)
        
        reader = LasReader(synthetic_site.las_path)
        las_meta = reader.get_metadata()
        
        bb_min = meta["boundingBox"]["min"]
        bb_max = meta["boundingBox"]["max"]
        
        # Bounds should match within 1m (generous tolerance for rounding)
        assert abs(bb_min[0] - las_meta.bounds[0]) < 1.0  # min_x
        assert abs(bb_min[1] - las_meta.bounds[1]) < 1.0  # min_y
        assert abs(bb_max[0] - las_meta.bounds[3]) < 1.0  # max_x
        assert abs(bb_max[1] - las_meta.bounds[4]) < 1.0  # max_y
    
    def test_fallback_point_count_matches(self, synthetic_site, tmp_path):
        """Number of points in metadata must match LAS file."""
        from heap_analyzer.io.las_reader import LasReader
        
        output_dir = tmp_path / "potree_output"
        result = _convert_python_fallback(Path(synthetic_site.las_path), output_dir, None)
        
        reader = LasReader(synthetic_site.las_path)
        las_meta = reader.get_metadata()
        
        assert result["num_points"] == las_meta.num_points
    
    def test_fallback_octree_bin_size_consistent(self, synthetic_site, tmp_path):
        """octree/r.bin size must equal num_points × bytes_per_point."""
        output_dir = tmp_path / "potree_output"
        result = _convert_python_fallback(Path(synthetic_site.las_path), output_dir, None)
        
        with open(output_dir / "metadata.json") as f:
            meta = json.load(f)
        
        bpp = sum(a["size"] for a in meta["attributes"])
        node_path = output_dir / "octree" / "r.bin"
        expected_size = meta["points"] * bpp
        assert node_path.stat().st_size == expected_size, (
            f"octree/r.bin size {node_path.stat().st_size} != "
            f"expected {expected_size} ({meta['points']} pts × {bpp} bpp)"
        )
    
    def test_fallback_progress_emitted(self, synthetic_site, tmp_path):
        """Progress callback is invoked with phase=potree_convert messages."""
        messages = []
        def capture(msg):
            messages.append(msg)
        
        output_dir = tmp_path / "potree_output"
        _convert_python_fallback(Path(synthetic_site.las_path), output_dir, capture)
        
        progress_msgs = [m for m in messages if m.get("type") == "progress"]
        assert len(progress_msgs) >= 3  # start, reading, done
        assert any(m["percent"] == 100 for m in progress_msgs)
        warning_msgs = [m for m in messages if m.get("type") == "warning"]
        assert len(warning_msgs) >= 1  # fallback warning


class TestExportForPotree:
    def test_export_with_nonexistent_las_raises(self, tmp_path):
        """Non-existent LAS file → FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            export_for_potree(str(tmp_path / "nonexistent.las"), str(tmp_path / "out"))
    
    def test_export_produces_output(self, synthetic_site, tmp_path):
        """export_for_potree produces valid output (uses whatever method is available)."""
        output_dir = tmp_path / "potree_output"
        result = export_for_potree(synthetic_site.las_path, str(output_dir))
        
        assert result["method"] in ("PotreeConverter", "python-fallback")
        assert result["num_points"] > 0
        assert Path(result["metadata_path"]).is_file()
    
    def test_cli_export_pointcloud_emits_json_lines(self, synthetic_site, tmp_path):
        """CLI `export-pointcloud` emits progress + result as JSON Lines on stdout."""
        import subprocess as sp
        output_dir = tmp_path / "potree_cli"
        proc = sp.run(
            ["heap-analyzer", "export-pointcloud",
             "--las", synthetic_site.las_path,
             "--output", str(output_dir)],
            capture_output=True, text=True, timeout=120,
        )
        assert proc.returncode == 0, f"CLI failed: {proc.stderr}"
        
        lines = [l for l in proc.stdout.strip().split("\n") if l.strip()]
        for line in lines:
            obj = json.loads(line)
            assert "type" in obj, f"Missing 'type' in JSON line: {line}"
        
        # Last line should be a result
        last = json.loads(lines[-1])
        assert last["type"] == "result"
        assert "data" in last
        assert last["data"]["num_points"] > 0
```

#### Run tests & commit

```bash
cd python-engine
pytest tests/test_pointcloud_export.py -v
pytest -q  # full suite green
ruff check src tests && mypy src --strict
cd ..
git add -A
git commit -m "F3.S03: Python pointcloud export + PotreeConverter detection + fallback + tests"
git push origin main
```

---

### STEP 3 — Electron: IPC handler + Express static serving + DB migration (25 min)

**Goal**: IPC to trigger conversion, serve Potree files via Express, store path in DB.

#### 3.1 DB migration: `potree_path` on surveys

```ts
const cols = db.pragma(`table_info(surveys)`) as {name: string}[];
if (!cols.some(c => c.name === 'potree_path')) {
  db.exec('ALTER TABLE surveys ADD COLUMN potree_path TEXT');
}
```

#### 3.2 IPC handler: `potree:convert`

| Channel | Input | Behavior |
|---|---|---|
| `potree:convert` | `{ surveyId }` | Fetch survey → get `las_path` → determine output dir (`<survey_output_dir>/potree/`) → call Python `export-pointcloud` → on success: update `surveys.potree_path` in DB → return `{ method, numPoints, warnings, potreeBaseUrl }` |

The `potreeBaseUrl` is the URL at which the Potree files are served (e.g., `http://localhost:<PORT>/potree/<surveyId>/`).

Also add:

| Channel | Input | Behavior |
|---|---|---|
| `potree:getStatus` | `{ surveyId }` | Check if `potree_path` exists and the directory contains `metadata.json` → return `{ available: boolean, method?: string, numPoints?: number, baseUrl?: string }` |

#### 3.3 Express static route

In the existing Express tile server (find the `app = express()` setup), add:

```ts
// Serve Potree files for each survey
app.use('/potree/:surveyId', (req, res, next) => {
  const surveyId = parseInt(req.params.surveyId, 10);
  // Look up survey.potree_path from DB
  const survey = db.getSurvey(surveyId);
  if (!survey?.potree_path) {
    return res.status(404).json({ error: 'Potree data not available' });
  }
  // Serve static files from the potree_path directory
  express.static(survey.potree_path)(req, res, next);
});
```

🏆 **Best practice — CORS headers**: the Express server should set `Access-Control-Allow-Origin: *` for Potree requests (the Electron renderer runs on a different origin than the Express server). Check if CORS is already configured from F2.S06.

🏆 **Best practice — Content-Type for .bin files**: ensure Express serves `.bin` files with `application/octet-stream`. By default Express should handle this, but verify.

#### 3.4 Preload API

```ts
api.potree = {
  convert:   (args) => ipcRenderer.invoke('potree:convert', args),
  getStatus: (args) => ipcRenderer.invoke('potree:getStatus', args),
}
```

Update type declarations.

#### 3.5 Vitest tests

Mock `PythonBridge` and `DatabaseService`:
- `potree:convert`: calls Python, updates DB `potree_path`, returns result with `potreeBaseUrl`.
- `potree:getStatus`: returns `available: true` when `potree_path` exists with `metadata.json`.
- `potree:getStatus`: returns `available: false` when no `potree_path`.

#### 3.6 Run & commit

```bash
npm run test -- --run
npm run typecheck && npm run lint
git add -A
git commit -m "F3.S03: Electron IPC potree:convert/getStatus + Express static route + DB migration"
git push origin main
```

---

### STEP 4 — Integration: auto-convert after processing + UI trigger (20 min)

**Goal**: Potree conversion happens automatically after survey processing completes, with a manual trigger also available.

#### 4.1 Auto-convert in processing pipeline

Find where the processing pipeline (from F2.S05) completes successfully — likely in a handler that receives the Python `result` message and updates the DB with heaps. After that success block, add:

```ts
// Auto-trigger Potree conversion after successful processing
try {
  const potreeResult = await handlePotreeConvert({ surveyId });
  console.error(`[F3.S03] Potree conversion done: ${potreeResult.method}, ${potreeResult.numPoints} points`);
} catch (err) {
  // Non-blocking: Potree conversion failure should NOT fail the processing
  console.error(`[F3.S03] Potree conversion failed (non-blocking): ${err}`);
}
```

🏆 **Best practice — non-blocking optional step**: Potree conversion is a "nice to have" after processing. If it fails (e.g., PotreeConverter not found + fallback error), the processing result is still valid. Log the error but don't propagate it to the user as a processing failure. Show a warning toast instead.

#### 4.2 Manual trigger button in UI

In the right panel or a toolbar, add a small button: `Converti per 3D` (icon: `Box`, lucide-react). Visible only when:
- A survey is loaded.
- `potree_path` is null OR the user wants to reconvert.

On click: call `window.api.potree.convert({ surveyId })`. Show progress toast. On success: toast `Conversione 3D completata ({numPoints} punti, metodo: {method})`. On failure: toast error.

This button is **optional** — the user may never click it if auto-convert succeeds. But it provides a manual fallback.

#### 4.3 3D toggle hint

In the header's 2D/3D toggle (from F2.S01), if `potree:getStatus` returns `available: false`, disable the "3D" toggle with tooltip: `Dati 3D non disponibili. Elabora il rilievo per generare la vista 3D.`

This is a **placeholder** — the actual 3D viewer is F3.S04.

#### 4.4 Run & commit

```bash
npm run test -- --run
npm run typecheck && npm run lint
git add -A
git commit -m "F3.S03: auto-convert after processing + manual Convert3D button + 3D toggle hint"
git push origin main
```

---

### STEP 5 — Regression sweep + final validation (10 min)

#### 5.1 Full regression

```bash
# Python
cd python-engine
pytest -q
ruff check src tests && mypy src --strict

# JS
cd ..
npm run test -- --run
npm run typecheck && npm run lint

# IPC hygiene
powershell -Command "Select-String -Path 'python-engine/src/heap_analyzer/*.py','python-engine/src/heap_analyzer/**/*.py' -Pattern '^\s*print\(' -SimpleMatch | Where-Object { $_.Line -notmatch 'click\.echo|sys\.stderr|file=sys\.stderr' }"
```

#### 5.2 Validate Potree output manually

```bash
# Run the CLI directly on synthetic data
cd python-engine
heap-analyzer export-pointcloud --las <path-to-synthetic-test.las> --output ../test-potree-output
```

Then check:
```bash
# Verify output structure
dir ..\test-potree-output
# Should contain: metadata.json, hierarchy.bin, octree\r.bin (or PotreeConverter's structure)

# Verify metadata.json is valid JSON
python -c "import json; m=json.load(open('../test-potree-output/metadata.json')); print(f'Points: {m[\"points\"]}, Version: {m[\"version\"]}')"

# Verify Express serving
# Open browser: http://localhost:<TILE_SERVER_PORT>/potree/<surveyId>/metadata.json
# Should return the JSON metadata
```

Report the `<TILE_SERVER_PORT>` from the existing Express tile server configuration.

#### 5.3 Commit

```bash
# Clean up test output
rmdir /s /q ..\test-potree-output 2>nul
git add -A
git commit -m "F3.S03: final validation + regression sweep green"
git push origin main
```

---

## ✅ FINAL VERIFICATION — MANDATORY MANUAL E2E

a. App running. DevTools console — no red errors.

b. Load the synthetic survey. Verify processing has already been run (heaps visible on map).

c. **Check auto-conversion**: if processing was run during a previous session, auto-convert might not have triggered. Click "Converti per 3D" button. Observe:
   - Progress toast with conversion phase messages.
   - Final toast: method used (`PotreeConverter` or `python-fallback`) + point count.
   - If fallback: warning toast about installing PotreeConverter.

d. **Verify Potree files**: in DevTools console, run:
   ```js
   await window.api.potree.getStatus({ surveyId: <current_survey_id> })
   ```
   Should return `{ available: true, method: '...', numPoints: ..., baseUrl: 'http://...' }`.

e. **Verify Express serving**: open the `baseUrl + "/metadata.json"` in a browser tab. Should return valid JSON with `version: "2.0"`, correct `points` count, and correct `boundingBox`.

f. **3D toggle**: the 2D/3D toggle in the header should now be enabled (not grayed out) since Potree data is available. Clicking "3D" won't show anything yet (F3.S04), but it should not crash.

g. **PotreeConverter detection log**: check the Python stderr output (in DevTools or terminal) for either:
   - `Using PotreeConverter at <path>` (if found), OR
   - `PotreeConverter non trovato, using Python fallback` (if not found).

h. `git log --oneline | head -10` — verify ~5 commits prefixed `F3.S03:`.

---

## 📊 REPORT BACK (required)

```
F3.S03 — REPORT

Commits pushed to main (N):
  <list each hash + message>

Test counts:
  Python pytest:   <before> → <after>  (new: test_pointcloud_export.py — N tests)
  Frontend vitest: <before> → <after>
  Electron vitest: <before> → <after>

PotreeConverter:
  Detected: yes / no
  Path: <path or "not found">
  Method used for synthetic: PotreeConverter / python-fallback

Potree output validation:
  metadata.json valid: yes/no
  points count matches LAS: yes/no
  hierarchy.bin exists: yes/no
  octree node(s) exist: yes/no
  Express serving: http://localhost:<PORT>/potree/<surveyId>/metadata.json → 200 OK

DB migrations:
  surveys.potree_path TEXT — added

Warnings emitted:
  <list any warnings, especially fallback warning>

Performance:
  Conversion time (synthetic ~200×200m): <X.X> s
  Method: <PotreeConverter or python-fallback>

UX deviations (if any):
  <describe or "none">

Open questions for F3.S04:
  - Was PotreeConverter found? If yes, F3.S04 can use full Potree 2.0 loader.
    If no (fallback), F3.S04 must handle the simplified single-node structure.
  - Express port used: <PORT>
  - Potree base URL pattern: http://localhost:<PORT>/potree/<surveyId>/
```

Save to `docs/reports/F3.S03-report.md` and commit.

---

## 🏆 BEST PRACTICES APPLIED

- 🏆 **Graceful degradation** — app never crashes for missing PotreeConverter; fallback + clear warning + install instructions.
- 🏆 **Detection order** — env var > PATH > project-local > common locations: flexible for any user setup.
- 🏆 **Non-blocking auto-convert** — Potree conversion failure after processing does NOT invalidate the processing result.
- 🏆 **Single-read chunked** — fallback reads LAS in chunks to control memory on large files.
- 🏆 **Metadata validation tests** — verify all required Potree 2.0 fields are present + bounding box matches source.
- 🏆 **Binary size consistency test** — `octree/r.bin` size == `num_points × bytes_per_point` (catches encoding bugs).
- 🏆 **Express CORS** — Potree viewer (F3.S04) will load from a different origin; CORS must be configured.
- 🏆 **DO NOT reimplement octree** — SPEC and DEV-PLAN are explicit: use PotreeConverter, focus on integration.

---

## 🚫 OUT OF SCOPE

- F3.S04 — Potree 3D viewer (next prompt — will consume the output of this task)
- F3.S05 — Cross sections
- Hierarchical LOD in fallback (nice-to-have for future optimization, not needed now)
- VLM classification (F4)

If you find yourself building a Three.js scene, writing `PotreeView.tsx`, or implementing cross-section extraction — STOP. You're outside F3.S03.
