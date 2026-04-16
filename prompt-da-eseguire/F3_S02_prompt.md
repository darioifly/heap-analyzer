# F3.S02 — Base Elevation Override + Known-Ground Selection

## 🎯 CONTEXT

You are Claude Code working on the **Heap Analyzer** project (Electron + React + Python). Desktop Windows app for volumetric heap analysis from LAS point clouds + GeoTIFF orthophotos. Used in steel plants.

**Completed**: F0 (setup), F1 (Python pipeline), F2 (UI 2D + map + export), **F3.S01** (polygon editing — Draw/Modify/Delete/Split/Merge + volume recalc + undo/redo).

**Current task**: **F3.S02 — Base Elevation Override + Known-Ground Selection**. This is task 2 of 5 in F3.

---

## 📚 AUTHORITATIVE REFERENCES (READ FIRST)

Before writing any code, read these project files:

1. `docs/SPEC.md` — technical spec v1.1 (authoritative). Focus on section [PIPELINE] Phase 2 (DTM) and Phase 4 (volume calculation).
2. `docs/DEV-PLAN.md` — task list. Locate F3.S02.
3. `docs/UX.md` — EVLOS design system (authoritative for UI).
4. `CLAUDE.md` — persistent instructions.
5. `docs/reports/F3.S01-report.md` — read to understand what was built in F3.S01 (especially `recompute_single_heap`, IPC handlers, `editingStore`).

**Key SPEC reminder** (from [PIPELINE] Phase 2):
> ⚠️ CRITICITÀ: errore 5 cm sulla base × 3.500 m² cumulo = ±175 m³ errore volume. Mostrare SEMPRE il valore stimato + permettere override manuale.

This task directly addresses this criticality.

---

## 🔒 CRITICAL RULES (NON-NEGOTIABLE)

### Runtime
- ❌ **DO NOT** run `npm run dev`, `npm run start`, or any dev server — already running in hot-reload.
- ❌ **DO NOT** run `npm run build`.
- ✅ **DO** run: `npm run test`, `cd python-engine && pytest`, `npm run typecheck`, `npm run lint`.

### IPC protocol
- Python stdout = **JSON Lines only** (`"type"` field ∈ `progress`, `result`, `error`, `warning`).
- Python stderr = logs/debug. **ZERO `print()` on stdout.**

### Git
- **Single branch `main`. NO feature branches.**
- After each step with green tests:
  ```bash
  git add -A && git commit -m "F3.S02: <description>" && git push origin main
  ```

### MCP plugins
- **Context7 MANDATORY** before touching: `rasterio.features.rasterize`, `ol/interaction/Draw`.
- **Sequential Thinking RECOMMENDED** for: ΔV approximation formula derivation, ground-sampling algorithm.
- **Memory**: save task summary at the end.

### Windows environment
- Working dir: `C:\Users\iflys\projects\Heap Analyzer` (space in path — quote in bash).
- Python 3.11: `C:\Users\iflys\AppData\Local\Programs\Python\Python311\`, `PYTHONUNBUFFERED=1`.
- GitHub: `darioifly/heap-analyzer`, branch `main`.

### Design system (EVLOS)
- Fonts: **Space Grotesk** (sans), **JetBrains Mono** (numbers/UTM).
- Colors: `evlos-50`..`evlos-900`, `success`, `warning`, `danger`. `border-radius: 0.5rem`.
- Dark mode default. UI strings: **Italian**.

---

## 🧠 DESIGN DECISIONS (finalized)

### D1: Base elevation scope = GLOBAL per survey
The base elevation override applies to the **entire survey** (all heaps share the same base elevation). This is consistent with the flat-terrain assumption in the SPEC. The DB field `heaps.base_elevation` stores the effective value per heap row (set during volume calculation or override), but the user controls a **single global value** at the survey level.

### D2: ΔV feedback = instant approximation + precise on-demand
- **While the slider moves**: show an **instant ΔV estimate** in the UI, computed **client-side** with zero Python calls. Formula:
  ```
  ΔV_approx ≈ -δ × Σ planimetric_area_i
  ```
  Where `δ = new_base - old_base` (meters) and the sum is over all non-excluded heaps. This is exact for a flat DTM (our case) and a good approximation otherwise.
- **On "Ricalcola volumi" click**: call Python `recompute-all-heaps` endpoint for precise recalculation using the full nDSM + new base elevation. Update DB and UI.

### D3: Ground selection workflow
The user draws one or more polygons on the map where bare ground is visible (e.g., roads, paved areas). The system samples the DSM (not nDSM) within those polygons, computes the **mean Z**, and suggests it as the new base elevation. The user can accept or adjust.

---

## 📋 IMPLEMENTATION STEPS

### STEP 0 — Read project state (5 min)

1. Read `CLAUDE.md`, `docs/SPEC.md`, `docs/DEV-PLAN.md`, `docs/UX.md`.
2. Read `docs/reports/F3.S01-report.md` — understand current IPC, store, and test state.
3. Examine existing code:
   - `python-engine/src/heap_analyzer/processing/volume.py` — find `recompute_single_heap` and `_compute_metrics_for_mask` from F3.S01.
   - `electron/src/ipc/editing-handlers.ts` — understand IPC pattern.
   - `electron/src/database/db.ts` — find `updateSurvey`, `updateHeap`, `listHeaps`.
   - `frontend/src/stores/heapStore.ts` — understand refresh pattern.
   - `frontend/src/stores/editingStore.ts` — understand undo/redo (F3.S02 ops will push to this history too).
   - `frontend/src/components/heaps/HeapProperties.tsx` — right panel, where we'll add the base elevation section.
   - `frontend/src/components/map/EditingToolbar.tsx` — where we'll add the ground-selection tool.
4. Capture baseline test counts:
   ```bash
   cd python-engine && pytest -q 2>&1 | tail -3
   cd .. && npm run test -- --run 2>&1 | tail -5
   ```
5. `git log --oneline -8` — confirm F3.S01 commits are present.

**No commit in this step.**

---

### STEP 1 — Python: batch recompute all heaps with new base elevation (20 min)

**Goal**: a Python CLI command that takes a survey's `ndsm_path` + `label_map_path` (or per-heap polygons) + a new `base_elevation` and returns recomputed metrics for ALL heaps.

🏆 **Best practice — reuse**: call the same `_compute_metrics_for_mask` from F3.S01 for each heap. Do NOT write a new volume formula.

#### 1.1 New function in `volume.py`: `recompute_all_heaps`

```python
def recompute_all_heaps(
    ndsm_path: str,
    heaps: list[dict],        # each: {id, polygon_geojson}
    base_elevation: float,
    config: ProcessingConfig,
) -> list[dict]:
    """Recompute metrics for multiple heaps with a shared base elevation.
    
    Opens the nDSM once, iterates over heaps, returns list of
    {id, metrics: HeapMetrics} dicts.
    
    Used by F3.S02 base-elevation override (global recalc).
    """
    with rasterio.open(ndsm_path) as src:
        ndsm = src.read(1)
        transform = src.transform
        shape = ndsm.shape

    results = []
    for h in heaps:
        geom = shapely.geometry.shape(h["polygon_geojson"])
        if not geom.is_valid:
            geom = geom.buffer(0)
        mask = rasterio.features.rasterize(
            [(geom, 1)], out_shape=shape, transform=transform, fill=0, dtype=np.uint8
        ).astype(bool)
        if not mask.any():
            continue
        metrics = _compute_metrics_for_mask(ndsm, mask, transform, base_elevation, config.height_threshold)
        results.append({"id": h["id"], "metrics": metrics.model_dump()})
    return results
```

🏆 **Best practice — open file ONCE**: the nDSM is opened once outside the loop. For N heaps × 1 file read vs N reads, this saves significant I/O on large rasters.

#### 1.2 New function: `sample_dsm_in_polygons`

For ground selection. Add to `volume.py` or a new `processing/ground_sampling.py`:

```python
def sample_dsm_in_polygons(
    dsm_path: str,
    polygons_geojson: list[dict],
) -> dict:
    """Sample the DSM within user-drawn ground-reference polygons.
    
    Returns:
        {
            "mean_elevation": float,      # weighted mean Z across all polygons
            "std_elevation": float,        # std dev (quality indicator)
            "num_pixels": int,             # total pixels sampled
            "per_polygon": [               # per-polygon breakdown
                {"mean": float, "std": float, "num_pixels": int},
                ...
            ]
        }
    
    Raises ValueError if no polygon intersects the DSM.
    """
    with rasterio.open(dsm_path) as src:
        dsm = src.read(1)
        transform = src.transform
        nodata = src.nodata
    
    all_values = []
    per_polygon = []
    for pg in polygons_geojson:
        geom = shapely.geometry.shape(pg)
        if not geom.is_valid:
            geom = geom.buffer(0)
        mask = rasterio.features.rasterize(
            [(geom, 1)], out_shape=dsm.shape, transform=transform, fill=0, dtype=np.uint8
        ).astype(bool)
        if nodata is not None:
            mask &= dsm != nodata
        vals = dsm[mask]
        if len(vals) == 0:
            per_polygon.append({"mean": None, "std": None, "num_pixels": 0})
            continue
        per_polygon.append({
            "mean": float(np.mean(vals)),
            "std": float(np.std(vals)),
            "num_pixels": int(len(vals)),
        })
        all_values.append(vals)
    
    if not all_values:
        raise ValueError("No ground polygons intersect the DSM raster")
    
    combined = np.concatenate(all_values)
    return {
        "mean_elevation": float(np.mean(combined)),
        "std_elevation": float(np.std(combined)),
        "num_pixels": int(len(combined)),
        "per_polygon": per_polygon,
    }
```

#### 1.3 CLI subcommands

Add to `cli.py`:

```python
@cli.command("recompute-all-heaps")
@click.option("--ndsm", required=True, type=click.Path(exists=True))
@click.option("--heaps-json", required=True, help="JSON array of {id, polygon_geojson}")
@click.option("--base-elevation", required=True, type=float)
@click.option("--config", default=None)
def recompute_all_heaps_cmd(ndsm, heaps_json, base_elevation, config):
    """Recompute metrics for all heaps with a new base elevation."""
    try:
        cfg = ProcessingConfig.model_validate_json(config) if config else ProcessingConfig()
        heaps = json.loads(heaps_json)
        emit({"type": "progress", "phase": "recompute", "percent": 0, "message": "Ricalcolo volumi..."})
        results = recompute_all_heaps(ndsm, heaps, base_elevation, cfg)
        emit({"type": "result", "data": {"heaps": results, "base_elevation": base_elevation}})
    except Exception as e:
        emit({"type": "error", "code": "RECOMPUTE_ALL_FAILED", "message": str(e)})
        sys.exit(1)

@cli.command("sample-ground")
@click.option("--dsm", required=True, type=click.Path(exists=True))
@click.option("--polygons-json", required=True, help="JSON array of GeoJSON polygon geometries")
def sample_ground_cmd(dsm, polygons_json):
    """Sample DSM elevation within user-drawn ground-reference polygons."""
    try:
        polygons = json.loads(polygons_json)
        result = sample_dsm_in_polygons(dsm, polygons)
        emit({"type": "result", "data": result})
    except Exception as e:
        emit({"type": "error", "code": "GROUND_SAMPLE_FAILED", "message": str(e)})
        sys.exit(1)
```

#### 1.4 Tests

Create `python-engine/tests/test_base_elevation.py`:

```python
def test_recompute_all_heaps_with_higher_base_reduces_volumes(synthetic_site):
    """Raising the base elevation by 0.5m must reduce all volumes."""
    original_base = synthetic_site.base_elevation  # e.g. 100.0
    new_base = original_base + 0.5
    
    heaps_input = [
        {"id": i, "polygon_geojson": p}
        for i, p in synthetic_site.polygons.items()
    ]
    results = recompute_all_heaps(
        synthetic_site.ndsm_path, heaps_input, new_base, ProcessingConfig()
    )
    original_metrics = compute_heap_metrics(
        synthetic_site.ndsm_path,
        synthetic_site.label_map_path,
        original_base,
        ProcessingConfig(),
    )
    for r in results:
        orig = next(m for m in original_metrics if m.label == r["id"])
        new_vol = r["metrics"]["volume"]
        # Volume must decrease when base goes up
        assert new_vol < orig.volume, (
            f"Heap {r['id']}: raising base by 0.5m should reduce volume "
            f"(was {orig.volume:.2f}, got {new_vol:.2f})"
        )

def test_recompute_all_zero_delta_matches_original(synthetic_site):
    """Same base elevation → volumes within ±1% of original (regression guard)."""
    heaps_input = [
        {"id": i, "polygon_geojson": p}
        for i, p in synthetic_site.polygons.items()
    ]
    results = recompute_all_heaps(
        synthetic_site.ndsm_path, heaps_input,
        synthetic_site.base_elevation, ProcessingConfig()
    )
    original_metrics = compute_heap_metrics(
        synthetic_site.ndsm_path,
        synthetic_site.label_map_path,
        synthetic_site.base_elevation,
        ProcessingConfig(),
    )
    for r in results:
        orig = next(m for m in original_metrics if m.label == r["id"])
        rel_err = abs(r["metrics"]["volume"] - orig.volume) / orig.volume
        assert rel_err < 0.01, f"Heap {r['id']}: same-base recompute drift {rel_err*100:.2f}%"

def test_delta_v_approximation_accuracy(synthetic_site):
    """Verify that ΔV ≈ -δ × Σ area is accurate within 5% for flat terrain.
    
    This validates the client-side instant-feedback formula used by the slider.
    On flat terrain (synthetic dataset), the approximation should be very close.
    """
    delta = 0.10  # raise base by 10 cm
    original_base = synthetic_site.base_elevation
    new_base = original_base + delta
    
    heaps_input = [
        {"id": i, "polygon_geojson": p}
        for i, p in synthetic_site.polygons.items()
    ]
    original_metrics = compute_heap_metrics(
        synthetic_site.ndsm_path, synthetic_site.label_map_path,
        original_base, ProcessingConfig()
    )
    new_results = recompute_all_heaps(
        synthetic_site.ndsm_path, heaps_input, new_base, ProcessingConfig()
    )
    
    total_area = sum(m.planimetric_area for m in original_metrics)
    approx_delta_v = -delta * total_area  # client-side formula
    
    total_original_v = sum(m.volume for m in original_metrics)
    total_new_v = sum(r["metrics"]["volume"] for r in new_results)
    precise_delta_v = total_new_v - total_original_v
    
    # On flat terrain, approximation should match within 5%
    if abs(precise_delta_v) > 1.0:  # skip if delta too small
        rel_err = abs(approx_delta_v - precise_delta_v) / abs(precise_delta_v)
        assert rel_err < 0.05, (
            f"ΔV approximation error {rel_err*100:.1f}%: "
            f"approx={approx_delta_v:.1f} precise={precise_delta_v:.1f}"
        )

def test_sample_dsm_in_ground_polygons(synthetic_site):
    """Ground polygons in known-flat area → mean ≈ base_elevation ± 0.05m."""
    # Create a small polygon in a ground area (no heap)
    # The synthetic site has terrain at known base_elevation
    import shapely.geometry
    # Use a corner of the 200x200m site that is guaranteed ground-only
    ground_poly = shapely.geometry.box(
        synthetic_site.bounds[0] + 5,   # min_e + 5m
        synthetic_site.bounds[1] + 5,   # min_n + 5m
        synthetic_site.bounds[0] + 25,  # 20m × 20m square
        synthetic_site.bounds[1] + 25,
    )
    result = sample_dsm_in_polygons(
        synthetic_site.dsm_path,
        [shapely.geometry.mapping(ground_poly)]
    )
    assert abs(result["mean_elevation"] - synthetic_site.base_elevation) < 0.05
    assert result["num_pixels"] > 100  # sanity: 20m×20m @ 0.1m/px = 40000 px
    assert result["std_elevation"] < 0.10  # flat terrain → low std

def test_sample_dsm_no_intersection_raises():
    """Polygon outside DSM extent → ValueError."""
    # ...

def test_cli_recompute_all_emits_json_lines():
    """CLI recompute-all-heaps emits progress + result JSON Lines."""
    # ...

def test_cli_sample_ground_emits_json_lines():
    """CLI sample-ground emits result JSON Lines."""
    # ...
```

🏆 **Best practice — test the client-side formula server-side**: `test_delta_v_approximation_accuracy` validates that the fast ΔV ≈ -δ × Σ area formula (which the frontend will use for instant slider feedback) is actually accurate on the synthetic flat terrain. If this test fails, the formula needs refinement.

#### 1.5 Run & commit

```bash
cd python-engine
pytest tests/test_base_elevation.py -v
pytest -q  # full suite green
ruff check src tests && mypy src --strict
cd ..
git add -A
git commit -m "F3.S02: Python recompute_all_heaps + sample_dsm_in_polygons + CLI"
git push origin main
```

---

### STEP 2 — Electron IPC handlers (15 min)

**Goal**: 2 new IPC channels.

#### 2.1 New handlers in `electron/src/ipc/editing-handlers.ts` (or a new `base-elevation-handlers.ts`)

| Channel | Input | Behavior |
|---|---|---|
| `elevation:recomputeAll` | `{ surveyId, baseElevation: number }` | Fetch all non-excluded heaps for `surveyId` from DB → build `heaps_json` array → call Python `recompute-all-heaps` → in a **transaction**: update each heap row (volume, areas, heights, `base_elevation`) + update survey's stored `base_elevation` → return updated heaps array |
| `elevation:sampleGround` | `{ surveyId, polygonsGeoJSON: dict[] }` | Fetch survey → get `dsm_path` → call Python `sample-ground` → return `{ mean_elevation, std_elevation, num_pixels, per_polygon }` |

Important implementation details:

- **`elevation:recomputeAll`** MUST:
  - Use `db.transaction(() => { ... })()` to update ALL heaps atomically.
  - Store the new `base_elevation` on the **survey row** too (add column if not present via migration — see 2.2).
  - Emit the full updated heaps list in the return so the frontend can refresh in one shot.
  - Support undo: this operation integrates with F3.S01's undo/redo. The frontend will push a `HistoryEntry` with `op: 'modify'` containing snapshots of all affected heaps before/after.

- **`elevation:sampleGround`** is read-only (no DB mutation). If the survey's `dsm_path` is null/empty, return `{ error: "DSM not available" }`.

#### 2.2 DB migration: `base_elevation` on surveys table

Check if `surveys` already has a `base_elevation` column. If not, add a migration:

```ts
// In initDatabase or migrations
const cols = db.pragma(`table_info(surveys)`) as {name: string}[];
if (!cols.some(c => c.name === 'base_elevation')) {
  db.exec('ALTER TABLE surveys ADD COLUMN base_elevation REAL');
}
```

This stores the survey-level base elevation (used as default for all heaps).

#### 2.3 Preload API

```ts
api.elevation = {
  recomputeAll: (args) => ipcRenderer.invoke('elevation:recomputeAll', args),
  sampleGround: (args) => ipcRenderer.invoke('elevation:sampleGround', args),
}
```

Update type declarations.

#### 2.4 Vitest tests

Mock `PythonBridge` and `DatabaseService`. Cover:
- `elevation:recomputeAll`: transaction called, all heaps updated, survey `base_elevation` updated.
- `elevation:sampleGround`: returns sampling result; returns error if `dsm_path` is null.

#### 2.5 Run & commit

```bash
npm run test -- --run
npm run typecheck && npm run lint
git add -A
git commit -m "F3.S02: Electron IPC elevation:recomputeAll + elevation:sampleGround + DB migration"
git push origin main
```

---

### STEP 3 — Frontend: BaseElevationControl component (40 min)

**Goal**: a collapsible section in the right panel showing the base elevation with override controls.

#### 3.1 Sequential Thinking (RECOMMENDED)

Before coding, use Sequential Thinking to plan the component state:
- What triggers a fresh read of `base_elevation`? (survey change, recalc completion)
- How does the instant ΔV interact with the recalculation loading state?
- How to integrate with F3.S01's undo/redo?

#### 3.2 Component `frontend/src/components/heaps/BaseElevationControl.tsx`

**Placement**: inside the right panel (`SidebarRight.tsx` or `HeapProperties.tsx`), ABOVE the per-heap details. Visible whenever a survey is loaded (not tied to heap selection).

**UI layout** (translate this mockup literally to JSX):

```
┌─────────────────────────────────────┐
│ ▾ Quota di base                     │  ← collapsible section header
├─────────────────────────────────────┤
│ Metodo: stima automatica            │  ← or "override manuale" / "terreno noto"
│                                     │
│ Quota:  ┌──────────┐  m s.l.m.     │  ← input, JetBrains Mono, step 0.01
│         │  100.32   │               │
│         └──────────┘                │
│                                     │
│ ──────────────●─────────────        │  ← slider ±1m from estimated, step 0.01
│ 99.32                    101.32     │  ← min/max labels in JetBrains Mono
│                                     │
│ ΔV stimato: -350.4 m³              │  ← orange if |δ| > 0.1m, JetBrains Mono
│ (approssimazione lineare)           │  ← small muted text
│                                     │
│ ┌─────────────────────────────┐     │
│ │  🔄  Ricalcola volumi      │     │  ← primary button, disabled if δ=0
│ └─────────────────────────────┘     │
│                                     │
│ ┌─────────────────────────────┐     │
│ │  📍  Seleziona terreno noto │     │  ← outline button, activates map tool
│ └─────────────────────────────┘     │
│                                     │
│ ⚠️ Variazione ±5cm = ±175 m³      │  ← warning banner (always visible)
│    su cumulo tipico 3500 m²         │
└─────────────────────────────────────┘
```

**State management**:

```ts
// Local state
const [localBase, setLocalBase] = useState<number>(survey.base_elevation ?? estimated);
const [isRecalculating, setIsRecalculating] = useState(false);
const [groundSelectionActive, setGroundSelectionActive] = useState(false);

// Derived: instant ΔV
const delta = localBase - (survey.base_elevation ?? estimated);
const totalArea = heaps
  .filter(h => !h.is_excluded)
  .reduce((sum, h) => sum + h.planimetric_area, 0);
const approxDeltaV = -delta * totalArea;
```

**Behaviors**:

- **Slider change** (`onChange` with debounce 50ms): updates `localBase`, ΔV recalculates instantly client-side. No Python call.
- **Input change**: same as slider, synced bidirectionally.
- **"Ricalcola volumi" click**:
  1. Set `isRecalculating = true`, show spinner on button.
  2. Snapshot current heaps for undo (`before`).
  3. Call `window.api.elevation.recomputeAll({ surveyId, baseElevation: localBase })`.
  4. On success: refresh `heapStore`, push `HistoryEntry` with `op: 'modify'` + `before`/`after` snapshots into `editingStore`.
  5. Toast: `Volumi ricalcolati con quota base {localBase.toFixed(2)} m` (success).
  6. Set `isRecalculating = false`.
  7. On error: toast error, reset `localBase` to previous value.
- **Undo of base elevation change**: since the heaps snapshot is pushed to `editingStore.undoStack`, Ctrl+Z restores the previous heap state. The `localBase` in this component should re-read from the survey/heap `base_elevation` after undo restores the DB.

#### 3.3 Styling details (EVLOS)

- Section header: `text-sm font-medium text-evlos-200 uppercase tracking-wide`.
- Input: `bg-evlos-800 border-evlos-600 text-evlos-50 font-mono text-right w-24`.
- Slider: use shadcn/ui `Slider` with evlos accent color. If shadcn Slider not available, use native `<input type="range">` with tailwind styling.
- ΔV display: `font-mono text-lg`. Color: `text-evlos-300` if `|delta| < 0.01`, `text-warning` (orange) if `0.01 ≤ |delta| < 0.5`, `text-danger` (red) if `|delta| ≥ 0.5`.
- Warning banner: `bg-warning/10 border-warning/30 text-warning text-xs p-2 rounded`.
- Buttons: shadcn/ui `Button`. "Ricalcola": `variant="default"`, "Seleziona terreno": `variant="outline"`.

#### 3.4 Mount in right panel

In `HeapProperties.tsx` (or `SidebarRight.tsx`), add `<BaseElevationControl />` at the top, above the per-heap details section. Pass `survey`, `heaps` (from stores), and `estimated` (from the survey's original processing result, typically stored in `processing_params` JSON or as a separate field).

If the survey has no `base_elevation` yet (null in DB), default to the value from `processing_params` → `estimated_base_elevation`. If that's also absent, default to `0.0` and show a warning.

#### 3.5 Vitest tests

- `BaseElevationControl.test.tsx`:
  - Renders with initial value from survey.
  - Slider change updates ΔV display instantly (no async call).
  - ΔV formula correct: delta=+0.1, totalArea=3500 → ΔV ≈ -350 m³.
  - "Ricalcola" button disabled when delta = 0.
  - "Ricalcola" button shows spinner during recalc.
  - Warning banner always visible with correct text.

#### 3.6 Run & commit

```bash
npm run test -- --run
npm run typecheck && npm run lint
git add -A
git commit -m "F3.S02: BaseElevationControl with slider + instant ΔV + recalc button"
git push origin main
```

---

### STEP 4 — Frontend: GroundSelectionTool (35 min)

**Goal**: a map interaction tool that lets the user draw ground-reference polygons, sample DSM elevation, and suggest a base elevation.

#### 4.1 Context7 lookup (MANDATORY)

Query Context7 for:
- `ol/interaction/Draw` — type `Polygon`, `drawend` event, styling during draw.
- `ol/layer/Vector` + `ol/source/Vector` — for the ground-polygon layer.

#### 4.2 Add tool to EditingToolbar

In `EditingToolbar.tsx` (from F3.S01), add a new tool button AFTER the existing editing tools and BEFORE Undo/Redo:

- Icon: `MapPin` (lucide-react) or `Target`.
- Tooltip: `Seleziona terreno noto (G)`.
- Keyboard shortcut: `G`.
- This tool sets `editingStore.activeTool = 'ground-select'`.

Update `EditingTool` type to include `'ground-select'`.

#### 4.3 Component `frontend/src/components/map/GroundSelectionTool.tsx`

Behavior:

1. **When `activeTool === 'ground-select'`**: add a new OL `Draw` interaction (type `Polygon`) + a dedicated `VectorSource` + `VectorLayer` for ground polygons.

2. **Ground polygon style**: 
   ```ts
   stroke: new Stroke({ color: '#22c55e', width: 2, lineDash: [8, 4] }),  // green dashed
   fill: new Fill({ color: 'rgba(34, 197, 94, 0.08)' }),                  // green 8% opacity
   ```
   This matches the SPEC requirement: "tratteggio verde" (green dashed).

3. **On each `drawend`**: the polygon is added to the ground source. A count badge updates in the toolbar (e.g., "3 aree selezionate").

4. **On tool deactivation** (user switches to another tool or clicks "Seleziona terreno noto" button in `BaseElevationControl`):
   - If ≥1 ground polygon exists: call `window.api.elevation.sampleGround({ surveyId, polygonsGeoJSON })`.
   - On success: toast with `Quota stimata dal terreno: {mean.toFixed(2)} m (σ = {std.toFixed(3)} m, {numPixels} pixel)`.
   - Auto-update the slider/input in `BaseElevationControl` to `mean_elevation`.
   - Show per-polygon breakdown in a small summary (optional — can be a tooltip or small list).
   - If `std_elevation > 0.15`: show warning toast `Attenzione: alta variabilità nel terreno selezionato (σ = {std.toFixed(2)} m). Valutare se le aree scelte sono realmente terreno.`
   - Clear the ground polygon layer.

5. **Cancel**: pressing `Esc` while in ground-select mode clears any in-progress draw AND all accumulated ground polygons, returning to Select tool.

#### 4.4 Communication between GroundSelectionTool and BaseElevationControl

Use a lightweight pub/sub approach. Options:
- **Zustand slice**: add `suggestedBaseElevation: number | null` to a shared store (e.g., `editingStore` or `surveyStore`). `GroundSelectionTool` sets it, `BaseElevationControl` reads it.
- This is simpler than React context or prop drilling through MapView.

When `suggestedBaseElevation` changes from null to a value:
- `BaseElevationControl` shows a transient banner: `Suggerito da terreno noto: {val.toFixed(2)} m` with an "Applica" button.
- Clicking "Applica" sets `localBase = suggestedBaseElevation`, clears the suggestion.
- The user can then optionally click "Ricalcola volumi" to persist.

#### 4.5 Vitest tests

- `GroundSelectionTool.test.tsx`:
  - Tool active → Draw interaction added to map mock.
  - Tool deactivated with polygons → `sampleGround` IPC called.
  - Esc clears polygons.
- Integration: GroundSelectionTool sets `suggestedBaseElevation` → BaseElevationControl shows "Applica" banner.

#### 4.6 Run & commit

```bash
npm run test -- --run
npm run typecheck && npm run lint
git add -A
git commit -m "F3.S02: GroundSelectionTool + map interaction + auto-suggestion in BaseElevationControl"
git push origin main
```

---

### STEP 5 — Integration + regression sweep (15 min)

#### 5.1 Wiring check

Verify the full flow works by reading through:
1. `SidebarRight.tsx` or `HeapProperties.tsx` → renders `<BaseElevationControl />`.
2. `MapView.tsx` → renders `<GroundSelectionTool />` when `activeTool === 'ground-select'`.
3. `EditingToolbar.tsx` → includes ground-select button.
4. `editingStore` → `activeTool` type includes `'ground-select'`, `suggestedBaseElevation` field exists.
5. `useEditingShortcuts` → `G` key mapped.

#### 5.2 Regression sweep

```bash
# Python
cd python-engine
pytest -q  # all green
ruff check src tests && mypy src --strict

# JS
cd ..
npm run test -- --run  # all green
npm run typecheck
npm run lint

# IPC hygiene
powershell -Command "Select-String -Path 'python-engine/src/heap_analyzer/*.py','python-engine/src/heap_analyzer/**/*.py' -Pattern '^\s*print\(' -SimpleMatch | Where-Object { $_.Line -notmatch 'click\.echo|sys\.stderr' }"

# Playwright (non-blocking)
npm run test:visual || echo "Review screenshots"
```

#### 5.3 Commit

```bash
git add -A
git commit -m "F3.S02: integration wiring + regression sweep green"
git push origin main
```

---

## ✅ FINAL VERIFICATION — MANDATORY MANUAL E2E

Perform these steps in order and report exact results:

a. App is hot-reloaded. Open DevTools console — no red errors.

b. Load a synthetic survey with 4 heaps. Note the current base elevation displayed in `BaseElevationControl` (e.g., `base = 100.00 m`). Note total volume in the riepilogo (e.g., `V_total = 2100.5 m³`).

c. **Slider test**: move slider to `100.10 m` (δ = +0.10). ΔV display shows approximately `-Σarea × 0.10`. For 4 heaps of ~3500 m² total area: ΔV ≈ -350 m³. Verify the number is in `text-warning` color (orange, since |δ|=0.10 ≥ 0.01).

d. **Input test**: type `100.05` in the input field. Slider position updates. ΔV updates. Both are in sync.

e. **Ricalcola test**: with base = `100.10`, click "Ricalcola volumi". Spinner appears. Within ~3s on synthetic data, toast: `Volumi ricalcolati con quota base 100.10 m`. All heap volumes in sidebar decrease. Check that a specific heap's volume decreased by roughly `area × 0.10 m³`.

f. **Undo test (Ctrl+Z)**: volumes revert to original. `BaseElevationControl` reads back the old base (100.00). ΔV resets to 0.

g. **Ground selection test**: click `Seleziona terreno noto` button (or press G). Cursor becomes crosshair. Draw a rectangle on a ground-only area of the ortofoto (corner of the 200×200m synthetic site). Double-click to close.

h. Switch back to Select tool (V) or click "Seleziona terreno noto" again. Within ~1s: toast `Quota stimata dal terreno: ~100.00 m (σ ≈ 0.00 m, N pixel)`. The `BaseElevationControl` shows a banner "Suggerito da terreno noto: 100.00 m" with "Applica" button.

i. Click "Applica". The slider/input updates to ~100.00 m. ΔV ≈ 0.

j. **Edge case**: try ground-selecting an area OVER a heap. The sampled `mean_elevation` will be high (~103m). The ΔV should show a large negative number, alerting the user that this is wrong.

k. **Warning banner**: verify the text `Variazione ±5cm = ±175 m³ su cumulo tipico 3500 m²` is always visible at the bottom of the section.

l. **Style check**: verify fonts (JetBrains Mono for numbers/coordinates, Space Grotesk for labels), colors match EVLOS dark palette, green dashed polygons for ground selection.

m. `git log --oneline | head -10` — verify ~5 commits prefixed `F3.S02:`.

---

## 📊 REPORT BACK (required)

```
F3.S02 — REPORT

Commits pushed to main (N):
  <list each hash + message>

Test counts:
  Python pytest:   <before> → <after>  (new: test_base_elevation.py)
  Frontend vitest: <before> → <after>
  Electron vitest: <before> → <after>

New IPC channels:
  elevation:recomputeAll — batch recalc with new base
  elevation:sampleGround — DSM sampling in ground polygons

DB migrations:
  surveys.base_elevation REAL — added

Key validations:
  ✅ Same-base recompute within ±1% of original (regression guard)
  ✅ Higher base → lower volumes (monotonicity test)
  ✅ ΔV ≈ -δ × Σ area accurate within 5% on flat synthetic terrain
  ✅ Ground sampling: mean ≈ known base_elevation ± 0.05m
  ✅ No print() in engine source

Performance:
  Batch recompute (4 heaps, synthetic): <X.X> s
  Ground sampling (1 polygon):          <X.X> s
  Slider ΔV update:                     instant (client-side)

UX deviations (if any):
  <describe or "none">

Open questions for F3.S03:
  <list>
```

Save to `docs/reports/F3.S02-report.md` and commit.

---

## 🏆 BEST PRACTICES APPLIED

- 🏆 **Single-read nDSM**: `recompute_all_heaps` opens the raster file ONCE outside the loop — O(1) I/O instead of O(N).
- 🏆 **Formula validation via test**: the client-side ΔV ≈ -δ × Σ area approximation is validated server-side against precise recalculation, proving it's safe to show in the UI.
- 🏆 **Regression guards carried forward**: ±1% same-base test reused from F3.S01 pattern.
- 🏆 **Atomic batch update**: all heap updates in a single DB transaction — partial failure leaves clean state.
- 🏆 **Undo integration**: base elevation change pushes to F3.S01's undo stack, giving consistent Ctrl+Z behavior.
- 🏆 **Variance warning**: `std_elevation > 0.15` on ground sampling triggers a user-visible warning — prevents silent bad calibration.
- 🏆 **SPEC criticality addressed**: the warning banner explicitly shows the ±5cm impact (175 m³ on 3500 m²), directly from the SPEC.
- 🏆 **Instant feedback**: slider ΔV is pure arithmetic (no async, no Python), <1ms response, maintaining fluid interaction.

---

## 🚫 OUT OF SCOPE

- F3.S03 — PotreeConverter integration (next prompt)
- F3.S04 — Potree 3D viewer
- F3.S05 — Cross sections
- Per-heap base elevation override (deferred — currently global per survey as per D1 decision)

If you find yourself editing `PotreeView.tsx`, `CrossSectionTool.tsx`, or adding per-heap elevation controls — STOP. You're outside F3.S02.
