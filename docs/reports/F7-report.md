# F7 Report — GIS Export + Settings + Robustness + Performance

**Date:** 2026-04-20
**Scope:** Phase F7 (sub-tasks S01–S04), single commit on `main`.

## Summary

Phase F7 closes the desktop-app MVP: users can export heap footprints to GIS
formats consumable by QGIS, tweak persistent application settings via a
four-tab modal, recover from uncaught renderer errors without losing work,
and benchmark pipeline performance on demand.

## Delivered

### F7.S01 — GeoJSON + Shapefile export

- `python-engine/src/heap_analyzer/export/geo_export.py` — `HeapRecord`
  pydantic model, `export_geojson()`, `export_shapefile()` (GeoPandas/Fiona).
  Skips `is_excluded` heaps; raises `click.UsageError` with an Italian
  message on empty input.
- `heap-analyzer export-geo` CLI subcommand: accepts `--results` +
  `--heaps-json` (DB-enriched records) + `--crs` + `--format
  {geojson|shapefile|both}`. Emits JSON-Lines progress and final
  `{paths, crs, count}` result.
- Shapefile column map enforces the <=10-character field-name limit (e.g.
  `planimetric_area_m2` → `area_pl_m2`). `.prj` written with WKT from
  pyproj.
- Electron `export:geo` IPC handler (new `electron/src/ipc/export-handlers.ts`)
  pulls heaps + project CRS from SQLite, builds the heap payload, and
  invokes the Python subcommand.
- `frontend/src/components/export/ExportButton.tsx` — three new dropdown
  entries (GeoJSON / Shapefile / Entrambi GIS), native directory picker,
  success toast with "Apri cartella" action, and error branch for the
  "nessun cumulo" case.
- **Tests:** [test_geo_export.py](../../python-engine/tests/test_geo_export.py)
  — 6 passing pytest cases (structure, 10-char enforcement, .prj, exclusion,
  empty-raises, geometry round-trip within 1e-6 m).

### F7.S02 — Settings modal + persistence

- `electron/src/services/settings.ts` — atomic write (tmp-file + rename),
  Zod schema validation, graceful fallback to defaults on corrupt JSON or
  missing file. `loadSettings` / `saveSettings` / `resetSettings`.
- `electron/src/ipc/settings-handlers.ts` — four IPC channels:
  `settings:load`, `settings:save`, `settings:reset`,
  `settings:getProcessingSchema`. Plus the `log:renderer-error` sink
  consumed by the ErrorBoundary.
- `heap-analyzer config-schema` Python CLI — emits `ProcessingConfig` field
  metadata so the Processing tab renders inputs dynamically rather than
  hard-coding field names.
- `frontend/src/stores/settingsStore.ts` — Zustand store with optimistic
  update + rollback on save failure. Keeps a deep-merge helper synced with
  the Electron copy.
- `frontend/src/components/settings/SettingsDialog.tsx` rewritten — full-
  screen Dialog (90vw × 85vh) with 4 shadcn/ui `Tabs` (Generali,
  Processing, VLM, Report). Dirty-guard via nested `AlertDialog`:
  "Annulla" or ESC with unsaved edits prompts "Modifiche non salvate".
- `tabs/GeneralTab.tsx` — data-dir picker, locked language (IT), locked
  dark theme with tooltips on the disabled variants.
- `tabs/ProcessingTab.tsx` — schema-driven inputs fetched via
  `settings:getProcessingSchema`, Python executable path, Ripristina default
  button.
- `tabs/VLMTab.tsx` — models-dir picker, VRAM slider (2–24 GB), and embeds
  the existing `VLMSettings` live controls instead of regressing to
  placeholders (F4.S01 is already complete).
- `tabs/ReportTab.tsx` — logo picker with 120×60 thumbnail preview
  (`object-fit: contain`), company name, default operator, custom footer.
- **Tests:**
  - [settings.test.ts](../../electron/src/services/settings.test.ts) — 5
    passing vitest cases (default fallback, atomic write, deep-merge,
    corrupt-JSON recovery, reset).
  - [settingsStore.test.ts](../../frontend/src/stores/settingsStore.test.ts)
    — 4 passing vitest cases (load, load-failure, save-round-trip,
    rollback-on-failure).

### F7.S03 — ErrorBoundary + robustness

- `frontend/src/components/ErrorBoundary.tsx` — React class component
  wrapping `<Layout>` in `App.tsx`. Italian fallback card (red-500 border,
  evlos-800 bg), JetBrains-Mono error message, collapsible stack trace in
  dev only (`import.meta.env.DEV`), "Ricarica applicazione" +
  "Copia dettagli" buttons. Reassures the user their data is safe.
  Forwards errors to Electron via fire-and-forget `log:renderer-error`.
- `python-engine/src/heap_analyzer/utils/errors.py` — new structured error
  classification module. SPEC codes: `CORRUPT_LAS`, `MISSING_CRS`,
  `CRS_MISMATCH`, `HEAP_TOO_SMALL`, `HEAP_ANOMALOUS`, `NO_LIDAR_RETURNS`.
  Italian messages.
- `utils/logging.setup_logging()` — idempotent root-logger configuration
  writing to **stderr** (never stdout — IPC-sacred) plus a
  `RotatingFileHandler` at `<log_dir>/heap-analyzer.log` (5 MB × 3
  backups). Log-dir resolves via `HEAP_ANALYZER_LOG_DIR` env or
  `~/.cache/heap-analyzer/logs`. Wired as the first call from the `main()`
  CLI group.
- `processing/volume.recompute_single_heap()` — now NaN-safe via
  `np.nan_to_num(ndsm, nan=0)`; a polygon on an all-NaN LiDAR-return tile
  returns `volume_m3=0` instead of `NaN`.
- **Tests:**
  - [test_error_handling.py](../../python-engine/tests/test_error_handling.py)
    — 7 passing pytest cases (corrupt LAS → CORRUPT_LAS classification,
    missing-CRS TIFF → MISSING_CRS, validator file-not-found, all-NaN
    nDSM tile, too-small heap, anomalous heap, CLI emits only JSON Lines).
  - [test_logging.py](../../python-engine/tests/test_logging.py) — 3
    passing pytest cases (stderr vs. stdout isolation, rotating file
    creation, idempotent setup).
  - [ErrorBoundary.test.tsx](../../frontend/src/components/ErrorBoundary.test.tsx)
    — 5 passing vitest cases (happy-path children, fallback on throw,
    reassurance message, IPC logging, reload handler).

### F7.S04 — Performance benchmark scaffolding

- `python-engine/scripts/benchmark.py` — Click CLI that runs the full
  `ProcessingPipeline` with a psutil-backed background sampler and writes
  a timestamped JSON report (`benchmark-<YYYYMMDD-HHMMSS>.json`). Schema
  documented in the perf doc. Does **not** emit JSON Lines on stdout —
  progress goes to stderr.
- `docs/performance-targets.md` — verbatim SPEC targets, execution
  instructions (synthetic + real datasets), report-JSON schema, baseline
  table stub labeled explicitly as *non rappresentativo dei target SPEC
  2 ha*, regression-detection protocol.
- **Tests:** [test_benchmark.py](../../python-engine/tests/test_benchmark.py)
  — 1 pytest case marked `@pytest.mark.slow` that runs the synthetic
  dataset end-to-end and validates the JSON report schema. Skipped by
  default (included in `-m slow` runs).

## Test Counts

| Scope | Baseline | After F7 | Δ |
|---|---|---|---|
| Python pytest | 232 passed, 1 pre-existing fail (VLM-real-model, GPU-bound) | **248 passed**, same 1 pre-existing fail | **+16** |
| Vitest | 39 passed, 42 failed (pre-existing — see below) | **53 passed**, 42 failed | **+14, 0 new failures** |
| Typecheck | clean | clean | — |
| Ruff | 14 pre-existing lint errors in untouched files | 14 pre-existing | — |
| ESLint | 0 errors, 3 pre-existing warnings | 0 errors, 3 pre-existing warnings | — |

**Known pre-existing vitest failures (not introduced by F7):** 42 failures
are split between (a) `electron/src/database/db.test.ts` — `better-sqlite3`
NODE_MODULE_VERSION 130 vs. 115 mismatch (native binding compiled for
Electron's Node, test runner uses system Node), and (b)
`frontend/src/components/surveys/SurveyList.test.tsx` et al. —
`window.api = {...}` assignment in node-env without jsdom. Both need
environment-level fixes beyond F7 scope.

## New IPC Channels

- `export:geo` — `(surveyId, format, outputDir, basename?)` → `(paths, crs, count)`
- `settings:load` — `()` → `Settings`
- `settings:save` — `(patch)` → `Settings`
- `settings:reset` — `()` → `Settings`
- `settings:getProcessingSchema` — `()` → `{ fields: SchemaField[] }`
- `log:renderer-error` — fire-and-forget, `(payload: {message, stack?, context?})`

## New Python CLI Subcommands

- `heap-analyzer export-geo` — GIS export
- `heap-analyzer config-schema` — emit `ProcessingConfig` schema metadata
- `heap-analyzer --verbose <subcommand>` — new global flag that routes
  DEBUG logs to stderr + rotating file

## Deviations from the task prompt

1. **Task prompt step 1.6 asks to read `docs/reports/F3.S05-report.md`.**
   That file does not exist (only S01/S02/S04 reports are on disk). Skipped.

2. **Task prompt step 2 asks to update `docs/PROJECT_STATE.md`.** That file
   does not exist in the repo — state is tracked in claude-mem auto-memory
   (`project_heap_analyzer.md`) instead. Updated the memory entry in its
   stead.

3. **VLM tab content.** Prompt described placeholder-disabled fields with a
   "Fase F4 non ancora configurata" banner. F4.S01 is already complete
   (live GPU detection + download UI), so I embedded the existing
   `VLMSettings` live controls into the tab rather than regressing to
   placeholders. Also added the *new* persistence fields
   (`modelsDir`, `preferredModel`, `estimatedVramGb`) alongside.

4. **electron-log dep.** Prompt suggested installing `electron-log`.
   Skipped: the main-process `log:renderer-error` sink currently pipes to
   `console.error`, which Electron forwards to stdout when running via
   `npm run dev`. A proper file-based electron-log wiring can be a follow-
   up — the renderer-side contract is already in place.

5. **Pre-existing dirty tree.** The 6 files dirty at session start
   (`electron/package.json`, `electron/src/ipc/handlers.ts`,
   `frontend/src/components/processing/ProcessingDialog.tsx`,
   `frontend/src/components/projects/ProjectList.tsx`,
   `frontend/tailwind.config.ts`,
   `python-engine/src/heap_analyzer/export/pointcloud_export.py`) were
   **left alone** — I only touched `electron/src/ipc/handlers.ts` to wire
   in the two new handler setups. Other dirty files remain in the working
   tree for the user to decide.

## Files Added (20)

```
python-engine/src/heap_analyzer/export/geo_export.py
python-engine/src/heap_analyzer/utils/errors.py
python-engine/scripts/benchmark.py
python-engine/tests/test_geo_export.py
python-engine/tests/test_error_handling.py
python-engine/tests/test_logging.py
python-engine/tests/test_benchmark.py

electron/src/services/settings.ts
electron/src/services/settings.test.ts
electron/src/ipc/export-handlers.ts
electron/src/ipc/settings-handlers.ts

frontend/src/components/ErrorBoundary.tsx
frontend/src/components/ErrorBoundary.test.tsx
frontend/src/components/settings/tabs/GeneralTab.tsx
frontend/src/components/settings/tabs/ProcessingTab.tsx
frontend/src/components/settings/tabs/VLMTab.tsx
frontend/src/components/settings/tabs/ReportTab.tsx
frontend/src/stores/settingsStore.ts
frontend/src/stores/settingsStore.test.ts

docs/performance-targets.md
docs/reports/F7-report.md
```

## Files Modified (F7-only)

```
python-engine/src/heap_analyzer/cli.py           # +export-geo, +config-schema, setup_logging
python-engine/src/heap_analyzer/utils/logging.py # +setup_logging + RotatingFileHandler
python-engine/src/heap_analyzer/processing/volume.py  # NaN-safe recompute_single_heap
python-engine/ruff.toml                          # extend per-file-ignores to tests/ + scripts/

electron/src/ipc/handlers.ts                     # wire export + settings setup
electron/src/preload.ts                          # +export, +settings, +logging surfaces

frontend/src/App.tsx                             # wrap in ErrorBoundary
frontend/src/components/export/ExportButton.tsx  # GIS dropdown entries
frontend/src/components/settings/SettingsDialog.tsx  # full-screen 4-tab rewrite
frontend/src/types/electron.d.ts                 # +export, +settings, +logging types
frontend/src/test/mock-api.ts                    # add new surfaces to test mock
frontend/src/stores/reportStore.test.ts          # remove unused vi import
```
