# PROMPT F3.S03 — Point Cloud → Potree Conversion

## CONTEXT

You are working on **Heap Analyzer**, an Electron + React + Python desktop app for volumetric analysis of LiDAR point cloud heaps in steelworks. The project is at `C:\Users\iflys\projects\Heap Analyzer`.

**Completed**: F0 (setup), F1 (Python pipeline), F2 (frontend UI + map), F3.S01 (polygon editing), F3.S02 (base elevation override).  
**Current task**: F3.S03 — Convert LAS/LAZ point clouds to Potree 2.0 format for 3D visualization.  
**Test count**: 195+ tests (155 Python + 40 vitest). 21 pre-existing vitest failures (window not defined in test env).

## AUTHORITATIVE REFERENCES

- `docs/SPEC.md` — Technical specs (WINS on conflicts). Section [UI] Vista 3D, [LIBS].
- `docs/DEV-PLAN.md` — F3.S03 task definition.
- `docs/UX.md` — EVLOS design system.
- `CLAUDE.md` — Persistent rules (IPC protocol, conventions, MCP).

## CRITICAL RULES (apply ALWAYS)

1. **IPC Protocol**: Python stdout = ONLY JSON Lines (`{"type": "progress|result|error|warning", ...}`). ZERO exceptions.
2. **Python**: type hints everywhere, Google-style docstrings, ruff formatting.
3. **TypeScript**: strict mode, explicit interfaces, ZERO `any` types.
4. **UI language**: Italian. Code language (vars, functions, classes): English. Comments: English.
5. **Git**: commit format `F3.S03: {description}`. Tests MUST pass before commit. `git add -A && git commit -m "..." && git push origin main`.
6. **DO NOT** run `npm run dev` — already running in hot-reload.
7. **Python interpreter**: `py -3.11` or `C:\Users\iflys\AppData\Local\Programs\Python\Python311\python.exe`.
8. **MCP**: Context7 MANDATORY before writing code with Potree or electron IPC.
9. **Path with space**: working directory has a space in "Heap Analyzer" — always quote paths.

## EXISTING CODEBASE CONTEXT

### Python CLI (cli.py)
Existing Click commands: `process`, `validate`, `generate-test-data`, `create-tiles`, `export-csv`, `recompute-heap`, `split-polygon`, `merge-polygons`, `recompute-all-heaps`, `sample-ground`.

### Electron IPC Channels
- Python: `python:execute`, `python:cancel`
- DB: `db:projects:*`, `db:surveys:*`, `db:heaps:*`
- Dialog: `dialog:openFile`, `dialog:saveFile`
- Editing: `editing:createHeap`, `editing:recomputeHeap`, `editing:deleteHeap`, `editing:splitHeap`, `editing:mergeHeaps`, `editing:restoreSnapshot`
- Elevation: `elevation:recomputeAll`, `elevation:sampleGround`
- Tiles: `tiles:getBaseUrl`, `tiles:getMetadata`
- Shell: `shell:showItemInFolder`

### Preload API (window.api)
```typescript
api.python.execute(command, args)  // → ResultMessage
api.python.cancel()
api.python.onProgress(callback)
api.tiles.getBaseUrl()             // → "http://127.0.0.1:3001"
api.tiles.getMetadata(surveyId)    // → metadata JSON
api.dialog.openFile(options)
api.db.updateSurvey(id, data)
```

### Tile Server (Express on port 3001)
- Routes: `/tiles/:surveyId/:z/:x/:y.png`, `/tiles/:surveyId/metadata.json`, `/heatmap/:surveyId.png`
- File: `electron/src/main.ts` → `TileServer` class

### Database Schema — surveys table
```sql
surveys: id, project_id, survey_date, operator, las_path, tiff_path,
  processing_params, processing_status, dsm_path, dtm_path, ndsm_path,
  label_map_path, tiles_path, ndsm_heatmap_path, base_elevation,
  created_at, updated_at
```
Note: `tiles_path` and `ndsm_heatmap_path` were added via migrations. A new `potree_path` column will be needed.

### Survey TypeScript interface (frontend/src/types/index.ts)
```typescript
interface Survey {
  id: number; projectId: number; surveyDate: string; operator: string | null;
  lasPath: string; tiffPath: string; processingParams: Record<string, unknown> | null;
  processingStatus: ProcessingStatus;
  dsmPath: string | null; dtmPath: string | null; ndsmPath: string | null;
  labelMapPath: string | null; tilesPath: string | null;
  ndsmHeatmapPath: string | null; baseElevation: number | null;
  createdAt: string; updatedAt: string;
}
```

### uiStore (frontend/src/stores/uiStore.ts)
```typescript
viewMode: "2d" | "3d"  // already exists but toggle NOT wired in HeaderBar
```

---

## STEP 1 — Download PotreeConverter 2.x Binary

### Objective
Download PotreeConverter from GitHub releases into `tools/PotreeConverter/` and add to `.gitignore`.

### 🏆 Best Practice
Keep external binaries out of git. Detect platform (Windows) and download correct release. Verify the binary is executable.

### Implementation

1. Create directory:
```bash
mkdir -p "tools/PotreeConverter"
```

2. Download PotreeConverter 2.1.1 from GitHub:
```bash
curl -L -o "tools/PotreeConverter/PotreeConverter.zip" "https://github.com/potree/PotreeConverter/releases/download/2.1.1/PotreeConverter_2.1.1_windows_x64.zip"
cd "tools/PotreeConverter" && unzip PotreeConverter.zip && rm PotreeConverter.zip
```

If the exact release URL differs, check https://github.com/potree/PotreeConverter/releases for the latest 2.x Windows release. The binary should be at `tools/PotreeConverter/PotreeConverter.exe` after extraction.

3. Add to `.gitignore`:
```
# PotreeConverter binary (downloaded, not tracked)
tools/PotreeConverter/
```

4. Verify:
```bash
"tools/PotreeConverter/PotreeConverter.exe" --help
```

If the download fails or the binary is not found, continue with the implementation — the code must handle missing PotreeConverter gracefully (see Step 2).

---

## STEP 2 — Python: export_for_potree()

### Objective
Create `python-engine/src/heap_analyzer/export/pointcloud_export.py` with Potree conversion via subprocess.

### 🏆 Best Practices
- Detect PotreeConverter binary path with fallback search order: (1) `tools/PotreeConverter/PotreeConverter.exe` relative to project root, (2) system PATH, (3) custom path via argument.
- Graceful failure: if PotreeConverter not found, emit `{"type": "error", "code": "POTREE_NOT_FOUND", ...}`.
- Progress parsing from PotreeConverter stdout.

### Context7 Query (MANDATORY)
Look up PotreeConverter CLI usage and output format (metadata.json structure, hierarchy.bin, octree/).

### Implementation

Create `python-engine/src/heap_analyzer/export/pointcloud_export.py`:

```python
"""Potree 2.0 point cloud conversion via PotreeConverter."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from pydantic import BaseModel


class PotreeExportResult(BaseModel):
    """Result of Potree conversion."""
    output_dir: str
    metadata_path: str
    num_points: int
    bounds: dict  # {"min": [x,y,z], "max": [x,y,z]}
    success: bool
    error: str | None = None


def find_potree_converter(custom_path: str | None = None) -> Path | None:
    """Find PotreeConverter binary.

    Search order:
    1. custom_path argument
    2. tools/PotreeConverter/PotreeConverter.exe (relative to project root)
    3. System PATH

    Returns:
        Path to PotreeConverter binary, or None if not found.
    """
    # 1. Custom path
    if custom_path:
        p = Path(custom_path)
        if p.exists():
            return p

    # 2. Project tools/ directory
    # Walk up from this file to find project root (contains package.json or CLAUDE.md)
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "tools" / "PotreeConverter" / "PotreeConverter.exe"
        if candidate.exists():
            return candidate
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
    progress_callback: callable | None = None,
) -> PotreeExportResult:
    """Convert LAS/LAZ to Potree 2.0 format.

    Args:
        las_path: Path to input LAS/LAZ file.
        output_dir: Directory for Potree output files.
        potree_converter_path: Optional custom path to PotreeConverter binary.
        progress_callback: Optional callback for progress updates.

    Returns:
        PotreeExportResult with conversion details.
    """
    las_path = Path(las_path)
    output_dir = Path(output_dir)

    # Validate input
    if not las_path.exists():
        return PotreeExportResult(
            output_dir=str(output_dir),
            metadata_path="",
            num_points=0,
            bounds={},
            success=False,
            error=f"LAS file not found: {las_path}",
        )

    # Find PotreeConverter
    converter = find_potree_converter(potree_converter_path)
    if converter is None:
        return PotreeExportResult(
            output_dir=str(output_dir),
            metadata_path="",
            num_points=0,
            bounds={},
            success=False,
            error="PotreeConverter not found. Install it in tools/PotreeConverter/ or add to PATH.",
        )

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build command
    cmd = [
        str(converter),
        str(las_path),
        "-o", str(output_dir),
    ]

    if progress_callback:
        progress_callback(0, "Avvio conversione Potree...")

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        # Parse progress from stdout
        stdout_lines = []
        for line in process.stdout:
            line = line.strip()
            if line:
                stdout_lines.append(line)
                # PotreeConverter outputs progress like "xyz% ..."
                if "%" in line:
                    try:
                        pct_str = line.split("%")[0].strip().split()[-1]
                        pct = int(float(pct_str))
                        if progress_callback:
                            progress_callback(pct, f"Conversione: {pct}%")
                    except (ValueError, IndexError):
                        pass

        stderr_output = process.stderr.read()
        return_code = process.wait()

        if return_code != 0:
            return PotreeExportResult(
                output_dir=str(output_dir),
                metadata_path="",
                num_points=0,
                bounds={},
                success=False,
                error=f"PotreeConverter failed (exit {return_code}): {stderr_output[:500]}",
            )

    except FileNotFoundError:
        return PotreeExportResult(
            output_dir=str(output_dir),
            metadata_path="",
            num_points=0,
            bounds={},
            success=False,
            error=f"PotreeConverter binary not executable: {converter}",
        )

    # Read metadata.json
    metadata_path = output_dir / "metadata.json"
    if not metadata_path.exists():
        return PotreeExportResult(
            output_dir=str(output_dir),
            metadata_path="",
            num_points=0,
            bounds={},
            success=False,
            error="PotreeConverter ran but metadata.json not found in output.",
        )

    with open(metadata_path, "r") as f:
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
        output_dir=str(output_dir),
        metadata_path=str(metadata_path),
        num_points=num_points,
        bounds=bounds,
        success=True,
    )
```

### 🏆 Best Practice: IPC stdout cleanliness
The function returns a Pydantic model — the CLI wrapper (next) handles JSON Lines output.

---

## STEP 3 — CLI Command: export-pointcloud

### Objective
Add `export-pointcloud` Click command to `cli.py`.

### Implementation

In `python-engine/src/heap_analyzer/cli.py`, add:

```python
@main.command("export-pointcloud")
@click.option("--las", required=True, type=click.Path(exists=True), help="Input LAS/LAZ file")
@click.option("--output", required=True, type=click.Path(), help="Output directory for Potree files")
@click.option("--converter-path", default=None, type=click.Path(), help="Custom PotreeConverter path")
def export_pointcloud_cmd(las: str, output: str, converter_path: str | None) -> None:
    """Convert LAS/LAZ to Potree 2.0 format."""
    from heap_analyzer.export.pointcloud_export import export_for_potree

    def progress_cb(pct: int, msg: str) -> None:
        _emit({"type": "progress", "phase": "potree_conversion", "percent": pct, "message": msg})

    result = export_for_potree(
        las_path=las,
        output_dir=output,
        potree_converter_path=converter_path,
        progress_callback=progress_cb,
    )

    if result.success:
        _emit({
            "type": "result",
            "data": {
                "output_dir": result.output_dir,
                "metadata_path": result.metadata_path,
                "num_points": result.num_points,
                "bounds": result.bounds,
            },
        })
    else:
        _emit({
            "type": "error",
            "code": "POTREE_CONVERSION_FAILED",
            "message": result.error,
        })
```

Where `_emit` is the existing JSON Lines emitter function in cli.py (should already exist — if not, define it as `json.dumps(obj)` to stdout).

---

## STEP 4 — Database Migration: potree_path

### Objective
Add `potree_path TEXT` column to `surveys` table.

### 🏆 Best Practice
Follow the same migration pattern used for `tiles_path` and `ndsm_heatmap_path` — PRAGMA table_info check + ALTER TABLE on startup.

### Implementation

In `electron/src/database/db.ts` (or wherever migrations run), add:

```typescript
// Migration: add potree_path to surveys
const surveyColumns = db.pragma('table_info(surveys)') as Array<{ name: string }>;
const hasPotreePath = surveyColumns.some((c) => c.name === 'potree_path');
if (!hasPotreePath) {
  db.exec('ALTER TABLE surveys ADD COLUMN potree_path TEXT');
}
```

Update `frontend/src/types/index.ts` — add to Survey interface:
```typescript
potreePath: string | null;
```

Update the DB→Frontend mapping function (in handlers.ts or wherever rows are mapped) to include `potree_path → potreePath`.

---

## STEP 5 — Electron IPC: potree:convert + potree:getStatus

### Objective
Add IPC handlers for Potree conversion and status check.

### Implementation

Create `electron/src/ipc/potree-handlers.ts`:

```typescript
import { ipcMain } from 'electron';
import path from 'path';
import fs from 'fs';
import type { DatabaseService } from '../database/db';

export function setupPotreeHandlers(dbService: DatabaseService): void {
  // Convert LAS to Potree format
  ipcMain.handle('potree:convert', async (_event, { surveyId }: { surveyId: number }) => {
    const survey = dbService.getSurvey(surveyId);
    if (!survey) throw new Error(`Survey ${surveyId} not found`);

    const outputDir = path.join(path.dirname(survey.las_path), 'potree');

    // Call Python CLI
    // Use existing PythonBridge pattern from handlers.ts
    // python:execute('export-pointcloud', ['--las', survey.las_path, '--output', outputDir])
    // On success: update survey.potree_path in DB

    return { outputDir };
  });

  // Check if Potree data exists for a survey
  ipcMain.handle('potree:getStatus', async (_event, { surveyId }: { surveyId: number }) => {
    const survey = dbService.getSurvey(surveyId);
    if (!survey) return { available: false, reason: 'Survey not found' };

    if (!survey.potree_path) return { available: false, reason: 'Not converted yet' };

    const metadataPath = path.join(survey.potree_path, 'metadata.json');
    if (!fs.existsSync(metadataPath)) return { available: false, reason: 'Potree files missing' };

    // Read metadata
    const metadata = JSON.parse(fs.readFileSync(metadataPath, 'utf-8'));
    return {
      available: true,
      potreePath: survey.potree_path,
      metadata,
    };
  });
}
```

Register in `electron/src/main.ts`:
```typescript
import { setupPotreeHandlers } from './ipc/potree-handlers';
// ... after setupIpcHandlers(dbService):
setupPotreeHandlers(dbService);
```

Add to `electron/src/preload.ts`:
```typescript
potree: {
  convert: (params: { surveyId: number }) =>
    ipcRenderer.invoke('potree:convert', params),
  getStatus: (params: { surveyId: number }) =>
    ipcRenderer.invoke('potree:getStatus', params),
},
```

---

## STEP 6 — Serve Potree Files via Express

### Objective
Add a static file route to the existing Express tile server so Potree files are accessible via HTTP.

### 🏆 Best Practice
Potree viewer (and @pnext/three-loader) needs HTTP access to point cloud data. Reuse the existing Express server on port 3001.

### Implementation

In `electron/src/main.ts` (TileServer class), add a route:

```typescript
// Serve Potree files: /potree/:surveyId/*
this.app.use('/potree/:surveyId', (req, res, next) => {
  const surveyId = parseInt(req.params.surveyId, 10);
  const survey = this.dbService.getSurvey(surveyId);
  if (!survey?.potree_path) {
    res.status(404).json({ error: 'Potree data not available' });
    return;
  }
  express.static(survey.potree_path)(req, res, next);
});
```

This means Potree metadata will be accessible at:
`http://127.0.0.1:3001/potree/{surveyId}/metadata.json`

And octree data at:
`http://127.0.0.1:3001/potree/{surveyId}/octree.bin` (or hierarchy.bin, etc.)

---

## STEP 7 — Pipeline Integration (Optional Auto-Convert)

### Objective
After the main processing pipeline completes successfully, optionally run Potree conversion.

### 🏆 Best Practice
Make it optional — if PotreeConverter is not available, skip silently with a warning. Don't block the main pipeline.

### Implementation

In the processing flow (when `python:execute('process', ...)` completes), add a post-processing step:

In `electron/src/ipc/handlers.ts` or a new handler, after processing result is received:

```typescript
// After successful processing, attempt Potree conversion
try {
  const potreeResult = await executePython('export-pointcloud', [
    '--las', survey.las_path,
    '--output', potreeOutputDir,
  ]);
  if (potreeResult.type === 'result') {
    dbService.updateSurvey(surveyId, { potree_path: potreeOutputDir });
  }
  // If it fails (POTREE_NOT_FOUND), just log a warning — 3D view disabled gracefully
} catch {
  console.warn('Potree conversion skipped — PotreeConverter not available');
}
```

Alternatively, keep conversion as a separate user-triggered action via a "Converti per 3D" button.

---

## STEP 8 — Tests

### Objective
Write tests for the Python pointcloud_export module.

### 🏆 Best Practice
- Test with mock subprocess when PotreeConverter is not available.
- Test find_potree_converter search logic.
- Test error handling (missing input, converter not found, conversion failure).
- Do NOT test actual PotreeConverter binary execution in CI (it may not be installed).

### Implementation

Create `python-engine/src/heap_analyzer/tests/test_pointcloud_export.py`:

```python
"""Tests for Potree point cloud export."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from heap_analyzer.export.pointcloud_export import (
    PotreeExportResult,
    export_for_potree,
    find_potree_converter,
)


class TestFindPotreeConverter:
    """Tests for PotreeConverter binary detection."""

    def test_custom_path_exists(self, tmp_path: Path) -> None:
        """Custom path takes priority when it exists."""
        fake_binary = tmp_path / "PotreeConverter.exe"
        fake_binary.touch()
        result = find_potree_converter(str(fake_binary))
        assert result == fake_binary

    def test_custom_path_not_exists(self) -> None:
        """Custom path that doesn't exist returns None (falls through)."""
        result = find_potree_converter("/nonexistent/PotreeConverter.exe")
        # May still find system PATH version, so just check it doesn't crash
        assert result is None or result.exists()

    def test_none_when_not_found(self) -> None:
        """Returns None when converter not found anywhere."""
        with patch("shutil.which", return_value=None):
            result = find_potree_converter("/nonexistent/path")
            # Result depends on whether tools/ exists in project
            # At minimum, should not raise
            assert result is None or isinstance(result, Path)


class TestExportForPotree:
    """Tests for Potree conversion."""

    def test_missing_input_file(self, tmp_path: Path) -> None:
        """Returns error result when LAS file doesn't exist."""
        result = export_for_potree(
            las_path=str(tmp_path / "nonexistent.las"),
            output_dir=str(tmp_path / "output"),
        )
        assert not result.success
        assert "not found" in result.error

    def test_converter_not_found(self, tmp_path: Path) -> None:
        """Returns error result when PotreeConverter is not found."""
        # Create a dummy LAS file
        las_file = tmp_path / "test.las"
        las_file.touch()

        with patch(
            "heap_analyzer.export.pointcloud_export.find_potree_converter",
            return_value=None,
        ):
            result = export_for_potree(
                las_path=str(las_file),
                output_dir=str(tmp_path / "output"),
            )
        assert not result.success
        assert "not found" in result.error.lower()

    def test_successful_conversion_mock(self, tmp_path: Path) -> None:
        """Simulates successful PotreeConverter execution."""
        las_file = tmp_path / "test.las"
        las_file.touch()
        output_dir = tmp_path / "output"

        # Create fake metadata.json that PotreeConverter would produce
        def fake_run(*args, **kwargs):
            output_dir.mkdir(parents=True, exist_ok=True)
            metadata = {
                "points": 1000000,
                "boundingBox": {
                    "lx": 500000.0, "ly": 4500000.0, "lz": 100.0,
                    "ux": 500200.0, "uy": 4500200.0, "uz": 110.0,
                },
            }
            (output_dir / "metadata.json").write_text(json.dumps(metadata))
            mock_proc = MagicMock()
            mock_proc.stdout = iter(["50%\n", "100%\n"])
            mock_proc.stderr.read.return_value = ""
            mock_proc.wait.return_value = 0
            return mock_proc

        fake_converter = tmp_path / "PotreeConverter.exe"
        fake_converter.touch()

        with patch(
            "heap_analyzer.export.pointcloud_export.find_potree_converter",
            return_value=fake_converter,
        ), patch("subprocess.Popen", side_effect=fake_run):
            result = export_for_potree(
                las_path=str(las_file),
                output_dir=str(output_dir),
            )

        assert result.success
        assert result.num_points == 1000000
        assert result.bounds["min"][0] == 500000.0

    def test_progress_callback_called(self, tmp_path: Path) -> None:
        """Progress callback receives updates."""
        las_file = tmp_path / "test.las"
        las_file.touch()
        output_dir = tmp_path / "output"

        def fake_run(*args, **kwargs):
            output_dir.mkdir(parents=True, exist_ok=True)
            metadata = {"points": 100, "boundingBox": {"lx": 0, "ly": 0, "lz": 0, "ux": 1, "uy": 1, "uz": 1}}
            (output_dir / "metadata.json").write_text(json.dumps(metadata))
            mock_proc = MagicMock()
            mock_proc.stdout = iter(["25%\n", "75%\n", "100%\n"])
            mock_proc.stderr.read.return_value = ""
            mock_proc.wait.return_value = 0
            return mock_proc

        progress_calls = []
        def on_progress(pct, msg):
            progress_calls.append((pct, msg))

        fake_converter = tmp_path / "PotreeConverter.exe"
        fake_converter.touch()

        with patch(
            "heap_analyzer.export.pointcloud_export.find_potree_converter",
            return_value=fake_converter,
        ), patch("subprocess.Popen", side_effect=fake_run):
            export_for_potree(
                las_path=str(las_file),
                output_dir=str(output_dir),
                progress_callback=on_progress,
            )

        # Should have at least start + end progress
        assert len(progress_calls) >= 2
        assert progress_calls[0][0] == 0  # initial
        assert progress_calls[-1][0] == 100  # final


class TestCLIExportPointcloud:
    """Tests for the CLI command."""

    def test_cli_emits_json_lines(self, tmp_path: Path) -> None:
        """CLI command outputs only valid JSON Lines."""
        import subprocess
        las_file = tmp_path / "test.las"
        las_file.touch()

        result = subprocess.run(
            ["py", "-3.11", "-m", "heap_analyzer.cli", "export-pointcloud",
             "--las", str(las_file), "--output", str(tmp_path / "out")],
            capture_output=True, text=True, cwd=str(tmp_path),
        )

        # Every stdout line must be valid JSON
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                parsed = json.loads(line)
                assert "type" in parsed


class TestIPCStdoutHygiene:
    """Verify no non-JSON output on stdout."""

    def test_no_print_statements_in_module(self) -> None:
        """Grep for bare print() calls in pointcloud_export.py."""
        import ast
        source_path = Path(__file__).parent.parent / "export" / "pointcloud_export.py"
        if not source_path.exists():
            pytest.skip("Module not yet created")
        tree = ast.parse(source_path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "print":
                    pytest.fail(f"Found print() call at line {node.lineno}")
```

### Test Execution
```bash
cd "python-engine" && py -3.11 -m pytest src/heap_analyzer/tests/test_pointcloud_export.py -v
```

---

## STEP 9 — IPC Stdout Hygiene Check

### 🏆 Best Practice (CRITICAL)
Verify that NO print() statements exist in any Python source file that could contaminate stdout.

```bash
cd "python-engine" && grep -rn "^[^#]*print(" src/heap_analyzer/ --include="*.py" | grep -v "stderr" | grep -v "test_" | grep -v "__pycache__"
```

Any match = BUG. Fix immediately.

---

## STEP 10 — Verify & Commit

### Run ALL tests
```bash
cd "python-engine" && py -3.11 -m pytest -x -v
```

Frontend tests (expect 21 pre-existing failures):
```bash
npm run test
```

### Manual Verification
1. Check `tools/PotreeConverter/PotreeConverter.exe` exists (or document if download failed)
2. Check `python-engine/src/heap_analyzer/export/pointcloud_export.py` exists
3. Check CLI: `py -3.11 -m heap_analyzer.cli export-pointcloud --help` shows the command
4. Check IPC: `potree:convert` and `potree:getStatus` registered
5. Check Express: `/potree/:surveyId/*` route added
6. Check DB migration: `potree_path` column in surveys
7. Check `.gitignore` includes `tools/PotreeConverter/`

### Commit
```bash
git add -A && git commit -m "F3.S03: PotreeConverter integration + export-pointcloud CLI + IPC + Express serving" && git push origin main
```

---

## REPORT BACK

After completing all steps, report:

1. **PotreeConverter status**: Downloaded successfully? Version? Path?
2. **New Python module**: `pointcloud_export.py` — functions count, lines of code
3. **New CLI command**: `export-pointcloud` — arguments
4. **New IPC channels**: list all new channels added
5. **Express routes**: new routes added
6. **DB migration**: `potree_path` column added?
7. **Test results**: new tests count, all passing?
8. **Total test count**: Python + vitest
9. **IPC hygiene**: any print() found? Fixed?
10. **Known issues/blockers for F3.S04**

## BEST PRACTICES APPLIED

- 🏆 External binary not in git (`.gitignore`)
- 🏆 Graceful fallback when PotreeConverter unavailable
- 🏆 Search order for binary: project tools/ → PATH → custom
- 🏆 JSON Lines protocol respected — zero stdout contamination
- 🏆 Pydantic model for structured result
- 🏆 Progress callback for real-time UI updates
- 🏆 Mock-based tests (no dependency on actual PotreeConverter in CI)
- 🏆 Reuse existing Express server (no new port)
- 🏆 DB migration follows established pattern (PRAGMA + ALTER TABLE)
- 🏆 Type hints everywhere, Google-style docstrings
