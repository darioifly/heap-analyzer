# PROJECT_STATE.md — Heap Analyzer

> Generated: 2026-04-20 · Generator: Claude Code regen pass · Source of truth: live repo at commit `477b141` (tip-of-main at commit time)
> Every numeric/path fact in this file came from a command run during regeneration.
> Note: il grosso del contenuto è stato raccolto a `6e2227a`; durante la scrittura è arrivato in parallelo il commit `477b141` (F2.S10 DTM fix, 150 m kernel) — incluso qui sotto.

## [HEADER]
- Repo: `https://github.com/darioifly/heap-analyzer.git`
- Branch: `main` (single-branch workflow, no feature branches)
- HEAD al momento del commit di rigenerazione: `477b141` — *F2.S10 fix: downsampled opening with 150 m kernel to cover 100+ m pile areas*
- Commit di rigenerazione (questo file): `7d4fa76` — *docs: regenerate PROJECT_STATE from live repo*
- Working tree: clean
- Working dir: `C:\Users\iflys\projects\Heap Analyzer`
- OS: Windows 11 Pro, Python 3.11 at `C:\Users\iflys\AppData\Local\Programs\Python\Python311\python.exe`
- LOC (tracked source only): electron/src 3 802 · frontend/src 12 546 · python-engine/src 13 098 · total ≈ 29 446
- Tracked files (excl. `node_modules`, `.venv`, `dist`, `build`, `tools/PotreeConverter/`): 244

## [STATUS]
| Phase | Tasks | Done | Status | Evidence |
|-------|-------|------|--------|----------|
| F0 — Setup | 9 (S00–S08) | 9 | ✅ Completa | commit `76b3c44` (F0 bulk S02–S08) |
| F1 — Pipeline Python Core | 8 (S01–S08) | 8 | ✅ Completa | commits `8eaedd0`→`6a30867` |
| F2 — UI 2D | 9 (S01–S09) + F2.S10 DJI extra | 10 | ✅ Completa | commits `f421598`→`062dc5f`, `f7e3f9c`→`67bfe8c` + `docs/reports/F2.S10-report.md` |
| F3 — Editing + 3D | 5 (S01–S05) | 5 | ✅ Completa | commits `bbfb503`→`e56f2d5` + reports F3.S01/S02/S04 |
| F4 — Classificazione VLM | 5 headers in DEV-PLAN (S01–S05) | 2 | 🟡 Parziale | commits `518e30b` (S01) + `87b1344` (S02); S03–S05 pending |
| F5 — Report PDF | 3 (S01–S03) | 3 | ✅ Completa | commits `396bd0f`, `8ad9804`, `b79ba84` |
| F6 — Confronto Temporale | 4 (S01–S04) | 1 | 🟡 Parziale | commit `e005b5c` (S01 matching + CLI + DB); S02–S04 pending |
| F7 — Export GIS + Rifinitura | 4 (S01–S04) | 4 | ✅ Completa | commit `0fc5a60` + `docs/reports/F7-report.md` |
| F8 — Packaging | 2 (S01–S02) | 0 | ⏳ Non iniziata | — |

Totale: 42/48 task (88%). Oltre al piano base: F2.S10 (DJI Terra import) completata.

## [CONSTRAINTS]
- **Runtime**: MAI eseguire `npm run dev`, `npm run start`, `npm run build` — già attivi in hot-reload nei terminali utente. Il tile server Express, Vite e Electron girano lì.
- **IPC Python↔Electron**: stdout = SOLO JSON Lines (una riga = un oggetto con campo `"type"` ∈ `progress|result|error|warning`). stderr = log/debug liberi. Zero eccezioni. Guardato dal test `test_ipc_hygiene.py`.
- **Git**: singolo branch `main`, commit granulari con prefisso `F{X}.S{YY}: <desc>`, `git push origin main` dopo ogni step verde. Test devono passare PRIMA del commit.
- **Codice**: Python 3.11 + type hints + ruff + mypy strict; TS strict, zero `any`. Stringhe UI in italiano, identificatori (variabili/funzioni/classi) in inglese, commenti in inglese.
- **File grandi**: sempre chunked/tiled (`laspy.chunk_iterator`, `rasterio` windows).
- **MCP**: Context7 prima di toccare laspy, rasterio, scipy.ndimage, shapely 2.x, scikit-image, OpenLayers, potree-core, better-sqlite3, Electron IPC, recharts. Sequential Thinking per F1.S04, F1.S05, F1.S06, F6.S01 e per algoritmi > 3 step. Memory alla fine/inizio sessione.
- **Test gates**: ±5% su volume vs analitico, ±1% su recompute stessa base, ±5% su ΔV, ±1cm/±15%/±15cm su cross-section (vedi [TESTS]).

## [STACK]
### Frontend (`frontend/package.json`)
- React `18.3.1` + TypeScript `5.6.3` + Vite `5.4.10`
- Tailwind CSS `3.4.19` + `tailwindcss-animate 1.0.7`
- Zustand `5.0.12` · react-hook-form `7.72.1` + `@hookform/resolvers 5.2.2` + zod `4.3.6`
- UI kit: shadcn/ui pattern su Radix UI primitives (`@radix-ui/react-*`: alert-dialog, avatar, checkbox, dialog, dropdown-menu, label, progress, scroll-area, select, separator, slider, slot, tabs, tooltip)
- Toasts: `sonner 2.0.7` · Icone: `lucide-react 1.8.0` · Class merging: `clsx 2.1.1` + `tailwind-merge 3.5.0` + `class-variance-authority 0.7.1`
- Resizable: `react-resizable-panels 4.10.0` · Grafici: `recharts 3.8.1`
- 2D map: `ol 10.9.0` + `proj4 2.20.8` (proiezioni UTM native)
- 3D: `potree-core 2.0.15` + `three 0.184.0`
- Test: vitest `2.1.4` + `@testing-library/react 16.3.2` + happy-dom `20.9.0` / jsdom `29.0.2`

### Electron (`electron/package.json`)
- Electron `33.2.1` + electron-builder `25.1.8`
- `better-sqlite3 11.5.0` (main process, NOT renderer)
- `express 5.2.1` (serve tile pyramid + Potree binary files)

### Python engine (`python-engine/pyproject.toml`)
- Python ≥ 3.11
- Core: `laspy[lazrs]>=2.0`, `rasterio>=1.3`, `numpy>=1.24`, `scipy>=1.10`, `scikit-image>=0.21`, `shapely>=2.0`, `geopandas>=0.13`, `fiona>=1.9`, `matplotlib>=3.7`, `reportlab`, `click`, `pydantic>=2.0`, `pyproj>=3.6`
- Extra `[vlm]`: `transformers>=4.45`, `torch>=2.1`, `huggingface-hub>=0.20`, `accelerate>=0.25`, `Pillow>=10.0`, `qwen-vl-utils>=0.0.2`
- Extra `[dev]`: `pytest>=7`, `pytest-cov`, `pypdf>=4.0`, `ruff`, `mypy`
- Entry point: `heap-analyzer = heap_analyzer.cli:main`

### Binari esterni
- PotreeConverter 2.1.2 Windows x64 in `tools/PotreeConverter/PotreeConverter_2.1.2_x64_windows/` (scaricato, NON committato, ignorato via `.gitignore`).

## [STRUCTURE]
Albero di directory a profondità max 3, solo codice tracciato. Annotazioni = scopo principale.

```
Heap Analyzer/
├── electron/src/                            # Main process (TS strict)
│   ├── main.ts                              # entry, BrowserWindow, tile server boot, dialog IPC
│   ├── preload.ts                           # contextBridge → window.api (12 domain namespaces)
│   ├── database/
│   │   ├── db.ts                            # DatabaseService (better-sqlite3) + migrations auto-apply
│   │   ├── schema.sql                       # 5 tables + triggers (copiato in dist/ al build)
│   │   ├── db.test.ts
│   │   └── migrations.test.ts
│   ├── ipc/                                 # Un file per dominio IPC
│   │   ├── python-bridge.ts                 # spawn Python + JSON Lines parser + progress forwarding
│   │   ├── handlers.ts                      # python:execute/cancel, db:projects/surveys/heaps, shell
│   │   ├── editing-handlers.ts              # editing:* (6 ops, atomic split/merge con transaction)
│   │   ├── elevation-handlers.ts            # elevation:recomputeAll / sampleGround
│   │   ├── cross-section-handlers.ts        # crossSection:* (6 ops, lazy-load profile_json)
│   │   ├── potree-handlers.ts               # potree:convert / getStatus
│   │   ├── export-handlers.ts               # export:geo (GeoJSON/Shapefile)
│   │   ├── dji-handlers.ts                  # dji:scanFolder / importSurvey
│   │   ├── comparison-handlers.ts           # comparison:run / get / listForSurvey
│   │   ├── report-handlers.ts               # report:generate / cancel + shell:openPath
│   │   ├── settings-handlers.ts             # settings:* + log:renderer-error
│   │   ├── vlm-handlers.ts                  # vlm:gpuInfo / listModels / download / cancelDownload
│   │   ├── python-bridge.test.ts
│   │   └── dji-handlers.test.ts
│   └── services/
│       ├── tile-server.ts                   # Express: /tiles + /potree/:surveyId/* con CORS + Content-Type
│       ├── settings.ts                      # load/save/reset settings.json atomico
│       ├── settings.test.ts
│       └── vlm-service.ts                   # proxy IPC → Python VLM subcommands
├── frontend/src/                            # React app (TS strict)
│   ├── main.tsx, App.tsx
│   ├── components/
│   │   ├── layout/                          # HeaderBar (fix 100px), MainLayout, SidebarLeft/Right, StatusBar, Viewport (2D↔3D)
│   │   ├── projects/                        # ProjectList, ProjectCard, ProjectDialog, DeleteProjectDialog
│   │   ├── surveys/                         # SurveyList, SurveyCard, ImportSurveyDialog, ImportDJIDialog
│   │   ├── processing/                      # ProcessingDialog (progress + cancel + advanced params), ProcessingProgress
│   │   ├── map/                             # MapView (OpenLayers UTM), HeapOverlay, LayerControls, EditingToolbar, PolygonEditor, GroundSelectionTool, CrossSectionDrawTool, CrossSectionLayer, EditingActions
│   │   ├── three/                           # PotreeView, Toolbar3D, cameraPresets
│   │   ├── charts/                          # CrossSectionChart (recharts), CrossSectionPanel
│   │   ├── heaps/                           # HeapList (sort+filter), HeapProperties, BaseElevationControl, SurveySummary
│   │   ├── export/                          # ExportButton, ExportDialog, ReportDialog
│   │   ├── settings/                        # SettingsDialog + tabs/{General,Processing,Report,VLM}Tab + VLMSettings
│   │   ├── ui/                              # 24 shadcn primitives
│   │   ├── ErrorBoundary.tsx
│   │   └── *.test.tsx                       # 8 component specs
│   ├── stores/                              # 12 Zustand stores (vedi [STORES])
│   ├── hooks/useEditingShortcuts.ts         # tastiere V/P/M/X/U/G/S/Delete/Esc
│   ├── lib/                                 # projections.ts, utils.ts, comparisonColors.ts
│   ├── utils/categoryColors.ts              # palette 12-col — DEVE matchare python report/palette.py
│   ├── types/                               # electron.d.ts (window.api), dji.ts, index.ts
│   ├── styles/globals.css
│   └── test/                                # mock-api.ts, setup.ts (vitest)
├── python-engine/src/heap_analyzer/         # Processing engine
│   ├── cli.py                               # 21 @cli.command (vedi [PYTHON_CLI])
│   ├── config.py, pipeline.py, __init__.py
│   ├── io/
│   │   ├── las_reader.py                    # chunked LAS/LAZ + CRS estratto da header
│   │   ├── tiff_reader.py                   # rasterio windowed
│   │   └── dji_terra_scanner.py             # manifest DJI Terra + pyramid_complete check
│   ├── processing/
│   │   ├── dsm.py                           # IDW chunked
│   │   ├── dtm.py                           # morphological / percentile / manual + ASPRS class=2
│   │   ├── segmentation.py                  # nDSM + multi-criteria (area/height/slope)
│   │   ├── volume.py                        # trapezoidal vectorized + rasterize once
│   │   ├── polygon_ops.py                   # split/merge shapely 2.x
│   │   ├── ground_sampling.py
│   │   └── cross_section.py                 # profile DSM/DTM + band averaging
│   ├── export/
│   │   ├── csv_export.py                    # header IT, `;`, UTF-8 BOM
│   │   ├── geo_export.py                    # GeoJSON + Shapefile (fiona)
│   │   ├── tile_generator.py                # web tile pyramid
│   │   ├── heatmap_generator.py             # nDSM colormap PNG
│   │   └── pointcloud_export.py             # PotreeConverter wrapper + LAS bbox header repair
│   ├── report/
│   │   ├── pdf_generator.py                 # reportlab Platypus
│   │   ├── map_renderer.py                  # site overview + heap detail PNG
│   │   ├── charts.py, formatting.py, palette.py
│   ├── comparison/
│   │   ├── matcher.py                       # Hungarian (scipy.optimize.linear_sum_assignment)
│   │   ├── config.py, palette.py
│   ├── classification/
│   │   └── vlm_service.py                   # transformers + torch, Qwen3-VL / Gemma-4
│   ├── utils/errors.py, utils/logging.py    # stderr logger only
│   ├── test_data_generator.py               # synthetic site 200×200m, 4 heaps known volumes
│   └── tests/                               # 227 pytest collected (vedi [TESTS])
├── tests/playwright/
│   └── smoke.spec.ts                        # 1 spec (screenshot smoke test)
├── docs/
│   ├── SPEC.md                              # [CONSTRAINT]/[IPC]/[PIPELINE]/[SCHEMA]/[UI]/[EXPORT]
│   ├── DEV-PLAN.md                          # 48 task + regole
│   ├── UX.md
│   ├── performance-targets.md
│   ├── decisions/                           # F3.S04-3d-library, F4-vlm-runtime, F5-pdf-runtime, F6-matching-algorithm
│   ├── reports/                             # F2.S10, F3.S01, F3.S02, F3.S04, F7
│   └── PROJECT_STATE.md                     # questo file
├── .claude/                                 # Claude Code project config
├── CLAUDE.md                                # regole progetto (override su default)
├── PROMPT-F3-S03.md, PROMPT-F3-S04.md, PROMPT-F3-S05.md
├── package.json (workspaces: frontend, electron)
├── mypy.ini, ruff.toml, .eslintrc.json, .prettierrc
├── vitest.config.ts
└── .gitignore                               # include Esempio/, tools/PotreeConverter/, *.las, *.tif, *.db
```

## [DB_SCHEMA]
Base schema in `electron/src/database/schema.sql`. Migrazioni additive applicate allo startup in `electron/src/database/db.ts:110-125` (pattern: `PRAGMA table_info` + `ALTER TABLE ADD COLUMN` idempotente).

```sql
-- 1. projects
CREATE TABLE projects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  location TEXT,
  crs TEXT DEFAULT 'EPSG:32632',
  notes TEXT,
  material_categories TEXT,          -- JSON array di stringhe
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2. surveys (schema base + 6 migrazioni additive applicate in db.ts)
CREATE TABLE surveys (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  survey_date DATE NOT NULL,
  operator TEXT,
  las_path TEXT NOT NULL,
  tiff_path TEXT NOT NULL,
  processing_params TEXT,            -- JSON ProcessingConfig
  processing_status TEXT DEFAULT 'pending',  -- pending|processing|completed|error
  dsm_path TEXT,
  dtm_path TEXT,
  ndsm_path TEXT,
  label_map_path TEXT,
  tiles_path TEXT,                   -- MIGR db.ts:110 (F2.S06)
  ndsm_heatmap_path TEXT,            -- MIGR db.ts:113 (F2.S07)
  base_elevation REAL,               -- MIGR db.ts:116 (F3.S02)
  potree_path TEXT,                  -- MIGR db.ts:119 (F3.S03)
  source_type TEXT DEFAULT 'manual', -- MIGR db.ts:122 (F2.S10) — 'manual' | 'dji_terra'
  dji_folder_path TEXT,              -- MIGR db.ts:125 (F2.S10)
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 3. heaps
CREATE TABLE heaps (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  survey_id INTEGER NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
  label TEXT,
  polygon TEXT NOT NULL,             -- GeoJSON geometry
  volume REAL, planimetric_area REAL, surface_area REAL,
  max_height REAL, mean_height REAL, base_elevation REAL,
  centroid_e REAL, centroid_n REAL,
  bbox_min_e REAL, bbox_min_n REAL, bbox_max_e REAL, bbox_max_n REAL,
  material_category TEXT, material_confidence REAL,
  is_manually_confirmed INTEGER DEFAULT 0,
  is_excluded INTEGER DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 4. comparisons (F6.S01)
CREATE TABLE comparisons (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  survey_a_id INTEGER NOT NULL REFERENCES surveys(id),
  survey_b_id INTEGER NOT NULL REFERENCES surveys(id),
  results TEXT,                      -- JSON matching results
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 5. cross_sections (F3.S05)
CREATE TABLE cross_sections (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  survey_id INTEGER NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
  label TEXT,
  line_geojson TEXT NOT NULL,
  profile_json TEXT,                 -- lazy: omesso da list(), fetched da get(id)
  section_area REAL, length REAL, max_height REAL,
  band_width REAL DEFAULT 1.0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_cross_sections_survey ON cross_sections(survey_id);

-- Triggers updated_at per projects, surveys, heaps, cross_sections
```

Il database risiede in `app.getPath('userData')` a runtime — non leggibile da regen; lo schema sopra è autorevole, ricavato da `schema.sql` + ALTER TABLE in `db.ts`.

## [IPC]
12 namespace esposti su `window.api` via `contextBridge` in [electron/src/preload.ts](electron/src/preload.ts). Ogni channel è registrato con `ipcMain.handle(...)` (invoke-based) tranne `log:renderer-error` (fire-and-forget `ipcMain.on`).

### Python bridge & shell (`ipc/handlers.ts`, `main.ts`, `ipc/report-handlers.ts`)
- `python:execute` · `python:cancel`
- `python:progress` (push renderer) · `python:warning` (push renderer)
- `shell:showItemInFolder` · `shell:openPath`
- `dialog:openFile` · `dialog:saveFile` · `dialog:openDirectory` (registrati in `ipc/handlers.ts` via `setupDialogHandlers`)

### Database (`ipc/handlers.ts`)
- `db:projects:list` · `db:projects:create` · `db:projects:update` · `db:projects:delete`
- `db:surveys:list` · `db:surveys:create` · `db:surveys:update` · `db:surveys:delete`
- `db:heaps:list` · `db:heaps:create` · `db:heaps:update` · `db:heaps:bulkCreate`

### Tiles (`main.ts`)
- `tiles:getBaseUrl` · `tiles:getMetadata`

### Editing (F3.S01, `ipc/editing-handlers.ts`)
- `editing:createHeap` · `editing:recomputeHeap` · `editing:deleteHeap`
- `editing:splitHeap` · `editing:mergeHeaps` (atomici con transaction better-sqlite3)
- `editing:restoreSnapshot` (per undo/redo)

### Base elevation (F3.S02, `ipc/elevation-handlers.ts`)
- `elevation:recomputeAll` · `elevation:sampleGround`

### Cross sections (F3.S05, `ipc/cross-section-handlers.ts`)
- `crossSection:create` · `crossSection:list` · `crossSection:get`
- `crossSection:update` · `crossSection:delete` · `crossSection:recompute`
- `list` restituisce righe senza `profile_json`; `get(id)` le fa fetch.

### Potree (F3.S03, `ipc/potree-handlers.ts`)
- `potree:convert` · `potree:getStatus`

### Export (F7.S01, `ipc/export-handlers.ts`)
- `export:geo` (params `format: 'geojson' | 'shapefile' | 'both'`)

### Report PDF (F5.S03, `ipc/report-handlers.ts`)
- `report:generate` · `report:cancel` · `report:progress` (push)

### Comparison (F6.S01, `ipc/comparison-handlers.ts`)
- `comparison:run` · `comparison:get` · `comparison:listForSurvey` · `comparison:progress` (push)

### DJI Terra (F2.S10, `ipc/dji-handlers.ts`)
- `dji:scanFolder` · `dji:importSurvey`

### Settings (F7.S02, `ipc/settings-handlers.ts`)
- `settings:load` · `settings:save` · `settings:reset` · `settings:getProcessingSchema`
- `log:renderer-error` (`ipcMain.on`, fire-and-forget)

### VLM (F4.S01, `ipc/vlm-handlers.ts`)
- `vlm:gpuInfo` · `vlm:listModels` · `vlm:isDownloaded`
- `vlm:download` · `vlm:cancelDownload` · `vlm:downloadProgress` (push)

## [STORES]
12 Zustand stores in [frontend/src/stores/](frontend/src/stores/). Pattern: `export const use<Name>Store = create<...>((set, get) => ({...}))`.

| Hook | File | Dominio |
|------|------|---------|
| `useProjectStore` | `projectStore.ts` | progetti list + selectedProjectId + CRUD |
| `useSurveyStore` | `surveyStore.ts` | surveys list + selectedSurveyId + CRUD |
| `useHeapStore` | `heapStore.ts` | heaps list + filter/sort + selection |
| `useProcessingStore` | `processingStore.ts` | stato esecuzione Python (phase/%/cancel) |
| `useUiStore` | `uiStore.ts` | viewMode 2D/3D, layout state, dialog flags |
| `useMapStore` | `mapStore.ts` | tile URL, layer visibility, map bounds |
| `useEditingStore` | `editingStore.ts` | editing tool + undo/redo stack |
| `useCrossSectionStore` | `crossSectionStore.ts` | sezioni attive + profili |
| `useReportStore` | `reportStore.ts` | report generation state + progress |
| `useSettingsStore` | `settingsStore.ts` | app settings (general/processing/report/vlm) |
| `useVlmStore` | `vlmStore.ts` | VLM gpu info + modelli + download state |
| `useComparisonStore` | `comparisonStore.ts` | confronto temporale state |

## [PYTHON_CLI]
Entry: `heap-analyzer` → `heap_analyzer.cli:main`. Tutti i comandi in [python-engine/src/heap_analyzer/cli.py](python-engine/src/heap_analyzer/cli.py).

| Comando | Funz | Scopo |
|---------|------|-------|
| `process` | `process` | Pipeline completa LAS+TIFF → DSM/DTM/nDSM/heaps JSON |
| `validate` | `validate` | Pre-flight check LAS+TIFF (CRS, overlap) |
| `generate-test-data` | `generate_test_data` | Sito sintetico 200×200m per test |
| `compare` | `compare_cmd` | F6.S01 — match spaziale tra due surveys |
| `create-tiles` | `create_tiles` | F2.S06 — web tile pyramid |
| `export-csv` | `export_csv` | F1.S08 — CSV IT con `;` e UTF-8 BOM |
| `generate-report` | `generate_report_cmd` | F5.S02 — PDF reportlab |
| `recompute-heap` | `recompute_heap` | F3.S01 — ricalcola volume/area per polygon modificato |
| `split-polygon` | `split_polygon` | F3.S01 — shapely split via linea |
| `merge-polygons` | `merge_polygons_cmd` | F3.S01 — unione shapely |
| `recompute-all-heaps` | `recompute_all_heaps_cmd` | F3.S02 — applica nuova base_elevation |
| `sample-ground` | `sample_ground_cmd` | F3.S02 — DSM media su poligoni terreno |
| `export-pointcloud` | `export_pointcloud_cmd` | F3.S03 — LAS→Potree via PotreeConverter |
| `cross-section` | `cross_section_cmd` | F3.S05 — profilo DSM/DTM lungo linea |
| `render-site-overview` | `render_site_overview_cmd` | F5.S01 — PNG ortofoto + overlay |
| `render-heap-detail` | `render_heap_detail_cmd` | F5.S01 — PNG dettaglio singolo cumulo |
| `export-geo` | `export_geo_cmd` | F7.S01 — GeoJSON + Shapefile |
| `config-schema` | `config_schema_cmd` | F7.S02 — dump ProcessingConfig schema (per Settings UI) |
| `scan-dji-terra` | `scan_dji_terra_cmd` | F2.S10 — manifest DJI Terra folder |
| `vlm gpu-info` | `vlm_gpu_info` | F4.S01 — CUDA/VRAM detection |
| `vlm list-models` | `vlm_list_models` | F4.S01 — modelli disponibili + `is_downloaded` |
| `vlm is-downloaded` | `vlm_is_downloaded` | F4.S01 |
| `vlm download` | `vlm_download` | F4.S01 — scarica pesi HF con progress JSON Lines |

## [TESTS]
- **pytest** (`python-engine/`): **227 test collected** in 20 file sotto `python-engine/src/heap_analyzer/tests/`. File: `test_base_elevation.py`, `test_cli.py`, `test_cross_section.py`, `test_csv_export.py`, `test_data_generator.py`, `test_dsm.py`, `test_dtm.py`, `test_ipc_hygiene.py`, `test_las_reader.py`, `test_map_renderer.py`, `test_matcher.py`, `test_pdf_generator.py`, `test_pipeline.py`, `test_pointcloud_export.py`, `test_polygon_ops.py`, `test_segmentation.py`, `test_tiff_reader.py`, `test_vlm_service.py`, `test_volume.py`, `test_volume_recompute.py`. Marker `slow` per e2e reali.
- **vitest** (frontend + electron): **19 file .test.ts(x) · ~108 test cases** (grep `^\s*(it|test)\(`):
  - Frontend componenti: `ErrorBoundary`, `Layout`, `MainLayout`, `ProcessingProgress`, `ProjectList`, `VLMSettings`, `ImportDJIDialog`, `SurveyList`
  - Frontend stores: `editingStore`, `processingStore`, `projectStore`, `reportStore`, `settingsStore`, `vlmStore`
  - Electron: `db.test.ts`, `migrations.test.ts`, `python-bridge.test.ts`, `dji-handlers.test.ts`, `settings.test.ts`
- **Playwright**: **1 spec** — `tests/playwright/smoke.spec.ts`

### Cross-cutting test guards (invarianti da NON rompere)
1. `test_ipc_hygiene.py` — nessun `print(` verso stdout in `python-engine/src/heap_analyzer/**/*.py` (solo CLI emette JSON).
2. ±1% volume recompute su poligono invariato (`test_volume_recompute.py`).
3. ±5% volume vs analitico su dataset sintetici conici/semisfera/irregolare (`test_volume.py`).
4. Recompute stessa base → ±1%.
5. ΔV approssimato ±5%.
6. Potree output: bbox + point count + dimensione byte coerenti (`test_pointcloud_export.py`).
7. Cross-section su cono: lunghezza = 2r ± 1 cm, max_height = h ± 15 cm, area = r·h ± 15% (`test_cross_section.py`).
8. `test_matcher.py` — palette frontend (`comparisonColors.ts`) = palette Python (`comparison/palette.py`), byte-identica.

## [DESIGN_SYSTEM]
Da `frontend/tailwind.config.ts` + `frontend/src/styles/globals.css` + `frontend/src/components/ui/`.

- **Font**: `Space Grotesk` (sans), `JetBrains Mono` (numeri/UTM/percentuali)
- **Palette dominante**: `evlos-50…900` (scala freddo/blu-grigio). Semantici via CSS vars shadcn: `border`, `input`, `ring`, `background`, `foreground`, `primary`, `secondary`, `destructive`, `muted`, `accent`, `popover`, `card`
- **Dark mode**: `darkMode: "class"`, default dark
- **Header**: fissa 100px, toni `evlos-700/800`
- **Toast**: `sonner` (non blocking). **Modal**: shadcn `AlertDialog` solo per operazioni distruttive (delete project/heap, overwrite)
- **Categorie materiali**: palette 12 colori sincronizzata tra `frontend/src/utils/categoryColors.ts` e `python-engine/src/heap_analyzer/report/palette.py` — byte-identica, se cambi una cambia l'altra nello stesso commit
- **Comparison states**: `frontend/src/lib/comparisonColors.ts` sincronizzata con `python-engine/src/heap_analyzer/comparison/palette.py` (guard `test_matcher.py`)

### Shortcut tastiera (`frontend/src/hooks/useEditingShortcuts.ts`)
| Tasto | Azione |
|-------|--------|
| `V` | tool `select` |
| `P` | tool `draw` (disegna poligono) |
| `M` | tool `modify` |
| `X` | tool `split` |
| `U` | tool `merge` |
| `G` | tool `ground-select` (campionamento terreno) |
| `S` | tool `cross-section` |
| `Delete`/`Backspace` | tool `delete` |
| `Escape` | torna a `select` |
| `Ctrl+Z` / `Ctrl+Shift+Z` | undo / redo (editingStore history) |

Isolation: gli shortcut sono disabilitati se il focus è su `input`/`textarea`/`select`/`[contenteditable="true"]`. Tasti `2`/`3` per toggle 2D/3D **NON** attualmente bindati da tastiera — il cambio view è esposto solo via UI (`Viewport.tsx` + `useUiStore.viewMode`).

## [DECISIONS]
Decisioni architetturali con una riga di contesto. Fonte: `docs/decisions/*.md` + pattern ricorrenti nel codice.

- **3D library** → `potree-core@2.0.15` + `three@0.184.0`. Scelto vs `@pnext/three-loader` (pinnato a three ~0.160.0) e Potree viewer embedded (non npm-friendly). Docs: [docs/decisions/F3.S04-3d-library.md](docs/decisions/F3.S04-3d-library.md)
- **VLM runtime** → `transformers` + `torch` (HF ecosystem) vs `llama-cpp-python` GGUF. Motivo: qualità FP16, ergonomia Windows (no VS Build Tools), supporto ufficiale Qwen3-VL/Gemma-4. Docs: [docs/decisions/F4-vlm-runtime.md](docs/decisions/F4-vlm-runtime.md)
- **PDF runtime** → `reportlab` (Platypus) vs WeasyPrint. Motivo: install Windows pulito, font DejaVu bundled, determinismo layout, PyInstaller-friendly. Docs: [docs/decisions/F5-pdf-runtime.md](docs/decisions/F5-pdf-runtime.md)
- **Matching F6.S01** → algoritmo **Hungarian** (`scipy.optimize.linear_sum_assignment`) vs greedy IoU. Motivo: ottimo globale O(n³) trascurabile per n ≤ 100. Docs: [docs/decisions/F6-matching-algorithm.md](docs/decisions/F6-matching-algorithm.md)
- **Interpolazione raster**: bilineare ovunque (non nearest-neighbor) per DSM/DTM sampling.
- **Rasterizzazione poligoni**: one-shot + numpy vettorizzato, mai loop pixel-per-pixel (guard `test_vectorization_no_pixel_loops`).
- **Apertura raster**: una volta sola fuori dai loop batch (recompute-all heaps).
- **Split/merge/recompute-all**: transaction atomiche `better-sqlite3` (tutto o niente).
- **NaN → null**: numpy NaN convertiti in Python `None` prima dell'IPC per rendering recharts con gap.
- **DSM/DTM hard-fail**: mismatch di `transform`/`shape`/CRS → eccezione esplicita, niente silent-cast.
- **3D dispose discipline**: ogni geometry / material / renderer / listener viene distrutto in cleanup (PotreeView unmount).
- **Lazy load cross-sections**: `list` omette `profile_json` (campo pesante); `get(id)` lo fa fetch on demand.
- **Express + CORS**: tile server serve sia `/tiles/...` sia `/potree/:surveyId/...` con headers corretti per binary octree files.
- **LAS bbox repair** (commit `6e2227a`): prima di invocare PotreeConverter, riscansiona i punti e patcha l'header a offset 179 se il bbox dichiarato non combacia (tolleranza 1e-4 CRS units).
- **Python 3.11 pin**: path hardcoded `C:\Users\iflys\AppData\Local\Programs\Python\Python311\python.exe` per evitare conflitti con Python di sistema.
- **DJI Terra ground class**: quando `has_ground_classification=True` nel manifest DJI, DTM usa classi ASPRS class=2 invece di stima morfologica; class=2 di picco cumuli viene strippata come rumore (commit `efbb406`).

## [DIFF]
Questo è lo **snapshot iniziale**: non esisteva `docs/PROJECT_STATE.md` prima di questa rigenerazione. Nessun file precedente da confrontare.

### Aggiunti (tutto)
Tutto il contenuto in questo documento è nuovo rispetto al vuoto.

### Ultimi commit rilevanti (git log -10)
```
477b141 F2.S10 fix: downsampled opening with 150 m kernel to cover 100+ m pile areas
6e2227a chore: WIP fixes — Potree LAS bbox repair, tailwind shadcn vars, schema copy, layout
67bfe8c F2.S10 fix: use model_dump(mode='json') so Path fields serialize for IPC
efbb406 F2.S10 fix: thread precomputed DSM + strip DJI class=2 pile-top noise
2977f51 F2.S10: documentation — report and DEV-PLAN update
435904f F2.S10: end-to-end test on real DJI Terra Acciaieria dataset
d276982 F2.S10: ImportDJIDialog component and Importa da DJI Terra button
e7ea3f5 F2.S10: IPC channels dji:scanFolder and dji:importSurvey
841f3f5 F2.S10: add surveys.source_type and surveys.dji_folder_path columns
9cc4b68 F2.S10: pipeline accepts precomputed DSM and DTM uses ASPRS ground classification when available
f7e3f9c F2.S10: add DJI Terra folder scanner with manifest model and CLI
```

### Flag / note per planning agent
- `F3.S03` e `F3.S05` sono completi (commits presenti) ma **senza file report dedicato** in `docs/reports/` (solo F3.S01, F3.S02, F3.S04). Se servono report di chiusura, vanno generati.
- `F4.S03-S05`, `F6.S02-S04`, `F8.S01-S02` **non iniziati**: nessun commit, nessun file.
- `F4.S05` è l'idea VLM-QA per validazione della segmentazione (vedi memory `idea_vlm_segmentation_qa.md`).
- Summary `docs/DEV-PLAN.md` dice "F4 | 4" ma i header in DEV-PLAN sono 5 (S01–S05) — `F4.S05` aggiunto dopo il riepilogo. Il totale 48 considera 4 task per F4.
- `electron/src/database/schema.sql` viene copiato in `dist/database/schema.sql` al build (commit `6e2227a`) — prima il file mancante causava failure a runtime su Electron impacchettato.
- Tasto `Backspace` triggera lo stesso tool `delete` di `Delete` — comportamento voluto (vedi `useEditingShortcuts.ts:70`).

## [HOW_TO_RESUME]
1. Leggi `CLAUDE.md` (regole progetto).
2. Leggi questo file (`docs/PROJECT_STATE.md`).
3. Leggi il report più recente della fase target: `docs/reports/F<X>.S<YY>-report.md` (se esiste).
4. Consulta `docs/SPEC.md` per specifiche tecniche (vince in caso di conflitto con qualunque altro documento).
5. Consulta `docs/DEV-PLAN.md` per descrizione task + done-criteria + file coinvolti.
6. Consulta `docs/decisions/` per decisioni architetturali già prese.
7. Attendi il prompt utente con il task specifico.
8. **Non avviare** dev server: verifica nei terminali utente che Electron/Vite/tile-server siano già in hot-reload.
9. Baseline test counts prima di iniziare: `python -m pytest --collect-only -q` (atteso 227), `npm run typecheck`.
10. Commit granulari con prefisso `F{X}.S{YY}: <desc>`, push dopo ogni step verde.
11. A fine task: scrivi `docs/reports/F<X>.S<YY>-report.md` e aggiorna [STATUS] + aggiungi entry in testa a [HISTORY] di questo file.

## [HISTORY]
Cronologia dei task completati (newest first). Ogni entry re-derivata da `git log --grep="F<X>.S<YY>"` + report in `docs/reports/` + diff di contenuto.

### F7 — GIS Export + Settings + Robustezza + Performance (bundle)
**Commit**: `0fc5a60`. **Report**: [docs/reports/F7-report.md](docs/reports/F7-report.md) (2026-04-20)
**What**: impacchettato in un singolo commit F7.S01 (GeoJSON + Shapefile), F7.S02 (Settings app persistente), F7.S03 (error handling: ErrorBoundary, renderer error log), F7.S04 (perf benchmark).
**Deliverables**: `export:geo` IPC + `export_geo_cmd` CLI (fiona); SettingsDialog + 4 tabs + `settings.ts` service atomico; ErrorBoundary componente + `log:renderer-error` channel; benchmark suite.
**Tests**: aggiunti test per settings, error boundary, export geo.

### F6.S01 — Matching Spaziale Cumuli
**Commit**: `e005b5c`. **Decision**: [docs/decisions/F6-matching-algorithm.md](docs/decisions/F6-matching-algorithm.md) (2026-04-19)
**What**: Hungarian via `scipy.optimize.linear_sum_assignment`. Matching per IoU tra heaps di surveys A/B. Persistenza tabella `comparisons`. IPC `comparison:run/get/listForSurvey`.
**Tests**: `test_matcher.py` + palette sync guard.

### F4.S01–S02 — VLM Setup + Modelli
**Commits**: `518e30b` (F4.S01 VLM service + GPU detection + Settings UI), `87b1344` (F4.S02 Qwen3-VL-8B + Gemma-4 E4B nel registry)
**What**: `transformers`+`torch` runtime; CUDA/VRAM detection; download manager con progress JSON Lines + cancel; VLMSettings UI + VLMTab.
**Deliverables**: `vlm_service.py` (Python), `vlm-handlers.ts` (IPC), `vlmStore`.
**Decision**: [docs/decisions/F4-vlm-runtime.md](docs/decisions/F4-vlm-runtime.md)

### F5.S01–S03 — Report PDF Completo
**Commits**: `396bd0f` (S01 map renderer), `8ad9804` (S02 PDF generator reportlab), `b79ba84` (S03 UI dialog + progress + toast)
**What**: overview+detail PNG via matplotlib; PDF Platypus con TOC, tabelle IT, immagini; frontend `ReportDialog` + `reportStore` + IPC `report:generate/cancel/progress`.
**Decision**: [docs/decisions/F5-pdf-runtime.md](docs/decisions/F5-pdf-runtime.md)

### F2.S10 — Import DJI Terra (extra rispetto ai 48 task)
**Commits**: `f7e3f9c`→`67bfe8c` (9 commit) + fix successivo `477b141` (downsampled opening con kernel 150 m per coprire pile >100 m). **Report**: [docs/reports/F2.S10-report.md](docs/reports/F2.S10-report.md)
**What**: scanner cartella DJI Terra → manifest (orthophoto, dsm, las, crs, bbox, has_ground_classification, pipeline_complete, warnings); import con opzione `useDjiDsm`/`copyFiles`; pipeline accetta DSM precomputato; DTM usa ASPRS ground class quando disponibile; rumore di picco (class=2) strippato.
**DB**: `surveys.source_type` + `surveys.dji_folder_path` (migrazione additiva).
**Post-fix `477b141`**: `ground_classification_opening_m` da 60 → 150 m. Introdotta `_downsampled_opening()` in `processing/dtm.py`: quando DSM è più fine di ~0.5 m/px (DJI 3 cm/px), `skimage.block_reduce(np.min)` a griglia 0.5 m, `grey_opening` su griglia coarse, poi `zoom` bilineare. Risolve polygon-solo-perimetro su aree scrap 80×150 m dove la ground class=2 non esiste all'interno del cumulo.

### F3.S05 — Sezioni Trasversali
**Commit**: `e56f2d5`.
**What**: Python `cross_section.py` (profilo DSM/DTM lungo linea, band averaging); IPC `crossSection:*` (6 ops); recharts `CrossSectionChart`; piano 3D in PotreeView; `CrossSectionDrawTool` + `CrossSectionLayer`. 16 test.
**DB**: tabella `cross_sections` con `profile_json` lazy-load.

### F3.S04 — Vista 3D Potree
**Commit**: `a45ccd5`. **Report**: [docs/reports/F3.S04-report.md](docs/reports/F3.S04-report.md)
**What**: `PotreeView` con potree-core + three.js; toggle 2D/3D; camera presets (top/iso/front); color modes (RGB/elevation/classification); heap overlay 3D.
**Decision**: potree-core@2.0.15 + three@0.184.0 — [docs/decisions/F3.S04-3d-library.md](docs/decisions/F3.S04-3d-library.md)

### F3.S03 — Conversione Point Cloud → Potree
**Commit**: `ef8a41f`.
**What**: wrapper `pointcloud_export.py` su PotreeConverter 2.1.2; CLI `export-pointcloud`; IPC `potree:convert/getStatus`; Express serve `/potree/:surveyId/*` con CORS.
**Post-fix** (commit `6e2227a`): repair header bbox LAS in-place per aggirare rifiuto PotreeConverter su mismatch.

### F3.S02 — Override Quota Base + Terreno Noto
**Commits**: `c01190d`→`209f643` (4). **Report**: [docs/reports/F3.S02-report.md](docs/reports/F3.S02-report.md)
**What**: Python `recompute_all_heaps` + `sample_dsm_in_polygons`; IPC `elevation:recomputeAll/sampleGround`; `BaseElevationControl` (slider + ΔV istantaneo + recalc); `GroundSelectionTool` (disegno poligoni terreno su mappa); 10 test.
**DB**: aggiunta colonna `surveys.base_elevation`.

### F3.S01 — Editing Contorni Poligoni
**Commits**: `bbfb503`→`53bc977` (4). **Report**: [docs/reports/F3.S01-report.md](docs/reports/F3.S01-report.md)
**What**: Python `recompute_single_heap` + `split`/`merge` shapely 2.x; IPC `editing:*` (6 ops, atomici con transaction); `EditingToolbar` + `PolygonEditor` + `editingStore` con undo/redo; shortcut V/P/M/X/U/Delete/Esc. 16 test per editingStore.

### F2.S01–S09 — UI 2D Funzionale
**Commits**: `f421598` (S01 design system 3-panel), `23f2886` (S02 Zustand), `2ee3f02` (S03 projects CRUD), `18fd324` (S04 import survey), `c0996de` (S05 processing dialog), `a381849` (S05b DB handlers), `b37563a` (S06 tiles + OpenLayers + UTM), `831bd53` (S07 heap overlay + nDSM heatmap), `7bb17ce` (S08 heap properties + sortable list), `062dc5f` (S09 CSV export frontend).

### F1.S01–S08 — Pipeline Python Core
**Commits**: `8eaedd0` (S01 LAS chunked), `a814ddd` (S02 GeoTIFF tiled), `36ec6a8` (S03 DSM IDW), `5c8180b` (S04 DTM strategies), `1f68810` (S04b pyproj dep), `4a28468` (S05 nDSM+segmentazione), `0efb156` (S06 volume vectorized), `ac79c4e` (S07 pipeline integrata + CLI `process`/`validate`/`generate-test-data`), `6a30867` (S08 CSV IT BOM).

### F0.S00–S08 — Setup
**Commit**: `76b3c44` (bundle) + `53af4f7` (F1.S00 fix cone volume comment).
**What**: Electron+React+Vite, Python engine, IPC JSON Lines, SQLite, linting ruff/eslint, test data generator, Playwright.

---
End of PROJECT_STATE.md
