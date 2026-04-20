# DEV-PLAN.md — Heap Analyzer Piano di Sviluppo per Claude Code

<!-- ISTRUZIONI PER CLAUDE CODE:
Questo file contiene i 48 task di sviluppo in formato compatto.
Cerca il task corrente con grep: `F0.S01`, `F1.S04`, ecc.
Per ogni task: leggi dipendenze → descrizione → done-criteria → file coinvolti.
Riferimento autorevole per specifiche: docs/SPEC.md (vince in caso di conflitto).
-->

## REGOLE GLOBALI (applica SEMPRE)

### Protocollo IPC
- stdout Python = SOLO JSON Lines (una riga = un JSON con campo `type`)
- stderr Python = log/debug (qualsiasi formato)
- ZERO eccezioni. Nessun print(), nessun logging su stdout.

### Convenzioni Codice
- Python: type hints ovunque, docstring Google-style, ruff formatting
- TypeScript: strict mode, interfacce esplicite, nessun `any`
- Test: pytest (Python), vitest (frontend), Playwright (screenshot)
- Lingua UI/commenti: italiano. Lingua codice: inglese.
- File grandi: SEMPRE chunked/tiled processing

### Git
- Branch: `feature/F{X}.S{YY}-{slug}`
- Commit: `F{X}.S{YY}: {descrizione breve}`
- Test devono passare PRIMA del commit

### Plugin MCP — Quando Usarli
- **Context7**: OBBLIGATORIO prima di codice con laspy, rasterio, scipy.ndimage, shapely 2.x, scikit-image, openlayers, potree, better-sqlite3, electron IPC. NON usare per numpy, click, pydantic, react base.
- **Sequential Thinking**: OBBLIGATORIO per F1.S04, F1.S05, F1.S06, F6.S01. Consigliato per algoritmi > 3 step.
- **Memory**: salvare a FINE task, leggere a INIZIO sessione.

### Dataset Sintetici (da F0.S07 in poi)
- SEMPRE usare per test. Confronto volumi analitici = gold standard.
- Sito standard: 200m × 200m, terreno piatto, 4 cumuli (2 conici, 1 semisfera, 1 irregolare), volumi noti.

### Comandi
```
npm run dev          # Electron + React dev mode
npm run test         # vitest + pytest
npm run test:visual  # Playwright screenshot
npm run lint         # eslint + ruff
cd python-engine && pip install -e .
heap-analyzer process --las X --tiff Y --output Z
heap-analyzer generate-test-data --output ./test-data
```

---

## Struttura Monorepo

```
heap-analyzer/
├── electron/src/          # Main process (TS): main.ts, preload.ts, ipc/, database/
├── frontend/src/          # React app (TS): components/, stores/, hooks/, types/
├── python-engine/src/heap_analyzer/  # Processing engine (Python 3.11+)
├── tests/playwright/      # Screenshot test
├── docs/                  # SPEC.md, DEV-PLAN.md
├── .claude/settings.json  # Config Claude Code
└── CLAUDE.md              # Istruzioni persistenti
```

---

## FASE 0 — Setup (9 task)
> Output atteso: app Electron aperta, Python subprocess con JSON Lines, SQLite, Playwright, dataset sintetico.

### F0.S00 — Config Ambiente Claude Code + Plugin MCP
- **Deps**: nessuna
- **Do**: installare 5 plugin MCP (filesystem, github, context7, sequential-thinking, memory). Creare `.claude/settings.json` e `CLAUDE.md`. Testare ogni plugin.
- **Done**: tutti i plugin funzionanti, file config presenti e committati
- **Files**: `.claude/settings.json`, `CLAUDE.md`

### F0.S01 — Init Repository e Struttura Monorepo
- **Deps**: F0.S00
- **Do**: creare struttura cartelle (vedi sopra), `.gitignore` (node_modules, __pycache__, .venv, *.pyc, dist/, build/, *.egg-info, .env, *.las, *.laz, *.tif), README.md, copiare spec in `docs/SPEC.md`, piano in `docs/DEV-PLAN.md`
- **Done**: repo init, git status pulito, tutte le cartelle e file presenti
- **Files**: tutti i file struttura (scaffold vuoti dove serve)

### F0.S02 — Electron + React + TypeScript + Vite
- **Deps**: F0.S01
- **Do**: frontend React+TS con Vite, electron main.ts crea BrowserWindow, preload.ts con contextBridge, HMR funzionante, script `dev` e `build` nel root package.json. Finestra mostra "Heap Analyzer — v0.1.0"
- **Done**: `npm run dev` apre finestra Electron con React. HMR funziona.
- **Files**: `electron/src/main.ts`, `preload.ts`, `frontend/src/App.tsx`, `main.tsx`, `vite.config.ts`, package.json (root + sub)

### F0.S03 — Python Engine Setup
- **Deps**: F0.S01
- **Do**: `pyproject.toml` con tutte le dipendenze (vedi SPEC.md [LIBS]). Package installabile (`pip install -e .`). CLI dummy con Click: `heap-analyzer process --input X --output Y` → stampa JSON Lines su stdout. `config.py` con Pydantic ProcessingConfig (vedi SPEC.md [CONFIG]). Test che CLI emette solo JSON su stdout.
- **Done**: `pip install -e .` OK, CLI stampa JSON valido, pytest passa
- **Files**: `python-engine/pyproject.toml`, `src/heap_analyzer/__init__.py`, `cli.py`, `config.py`, `tests/test_cli.py`

### F0.S04 — Bridge IPC: Electron ↔ Python JSON Lines
- **Deps**: F0.S02, F0.S03
- **Do**: `PythonBridge` class in `electron/src/ipc/python-bridge.ts`: spawn Python, parse stdout JSON Lines riga per riga (gestire buffer incompleti, BOM, righe vuote), stderr separato, eventi tipizzati (progress/result/error/warning), cancellazione SIGTERM→SIGKILL, timeout 30 min. Handler IPC: `python:execute`, `python:cancel`. Preload: `api.python.execute()`, `.cancel()`, `.onProgress()`. Bottone "Test Python" nel frontend.
- **Done**: click bottone → Python lanciato → JSON risposta nell'UI. Cancel funziona. Output non-JSON gestito gracefully.
- **Files**: `electron/src/ipc/python-bridge.ts`, `handlers.ts`, `preload.ts`, `frontend/src/App.tsx`, `cli.py`
- **⚠️ CRITICO**: protocollo JSON Lines è fondamento di tutta l'app. Testare edge cases: buffer parziali, encoding, crash a metà riga.

### F0.S05 — Database SQLite
- **Deps**: F0.S02
- **Do**: better-sqlite3. Schema completo (vedi SPEC.md [SCHEMA]): tabelle projects, surveys, heaps, comparisons. `initDatabase(dbPath)` + classe Database con CRUD per ogni entità. Handler IPC per operazioni DB. Test unitari CRUD.
- **Done**: test CRUD passano, DB creato automaticamente al primo avvio
- **Files**: `electron/src/database/schema.sql`, `db.ts`, `db.test.ts`, `ipc/handlers.ts`
- **MCP**: Context7 per better-sqlite3

### F0.S06 — Linting, Formatting, Test Runner
- **Deps**: F0.S02, F0.S03
- **Do**: ESLint strict (TS+React), Prettier, Vitest, ruff, mypy strict, pytest+coverage. Script root: `lint`, `format`, `test`, `typecheck`.
- **Done**: tutti gli script passano senza errori
- **Files**: `.eslintrc.json`, `.prettierrc`, `ruff.toml`, `mypy.ini`, `vitest.config.ts`, `package.json`

### F0.S07 — Generatore Dataset Sintetici
- **Deps**: F0.S03
- **Do**: `test_data_generator.py` con: generazione nuvola punti sintetica LAS (terreno piatto + N cumuli geometrici: cono, semisfera, piramide), ortofoto sintetica GeoTIFF (colori diversi per cumulo/terreno, stesse coordinate), volumi analitici esatti (cono: πr²h/3, semisfera: 2πr³/3). Funzione `create_test_site()`: 4 cumuli su terreno piatto 200×200m. CLI: `heap-analyzer generate-test-data --output <dir>`. Output: test.las, test.tif, ground_truth.json.
- **Done**: file LAS e TIFF validi (apribili con laspy/rasterio), volumi analitici in ground_truth.json
- **Files**: `python-engine/src/heap_analyzer/test_data_generator.py`, `tests/test_data_generator_test.py`
- **⚠️**: modulo fondamentale — usato come riferimento per validare TUTTA la pipeline

### F0.S08 — Playwright per Testing Visivo
- **Deps**: F0.S02
- **Do**: @playwright/test + Electron. Config per launch headless, directory screenshot. Test smoke: lancia app, screenshot, verifica testo "Heap Analyzer". Helper: `captureScreenshot()`, `waitForMapReady()`, `waitForThreeReady()`. Script: `npm run test:visual`. Test NON bloccanti CI: producono screenshot per review.
- **Done**: `npm run test:visual` cattura screenshot, test passa
- **Files**: `tests/playwright.config.ts`, `playwright/smoke.spec.ts`, `playwright/helpers.ts`
- **MCP**: Context7 per Playwright+Electron

---

## FASE 1 — Pipeline Python Core (8 task)
> Output atteso: `heap-analyzer process --las X --tiff Y --output Z` produce JSON con cumuli, volumi, metriche. Errore volume < 5% vs analitico.

### F1.S01 — Loader LAS/LAZ Chunked
- **Deps**: F0.S03, F0.S07
- **Do**: `io/las_reader.py` con classe `LasReader`: get_metadata() (bounds, num_points, CRS, point_format), get_bounds(), read_points(bounds=None), iter_chunks(chunk_size=1_000_000). Gestione errori: file corrotto, formato non supportato, CRS mancante. Supporto LAS+LAZ (lazrs).
- **Done**: lettura corretta dataset sintetico, metadata OK, chunked OK, errori testati
- **Files**: `python-engine/src/heap_analyzer/io/las_reader.py`, `tests/test_las_reader.py`
- **MCP**: Context7 per laspy (sintassi chunked, VLR/CRS)

### F1.S02 — Loader GeoTIFF con Tiling
- **Deps**: F0.S03, F0.S07
- **Do**: `io/tiff_reader.py` con classe `TiffReader`: get_metadata() (bounds, CRS, risoluzione, dimensioni, bande), read_tile(window), iter_tiles(tile_size), read_region(bounds), check_crs_compatibility(las_crs).
- **Done**: lettura corretta GeoTIFF sintetico, metadata OK, tiling OK, verifica CRS OK
- **Files**: `python-engine/src/heap_analyzer/io/tiff_reader.py`, `tests/test_tiff_reader.py`
- **MCP**: Context7 per rasterio (Window, windowed reading, CRS)

### F1.S03 — Generazione DSM
- **Deps**: F1.S01
- **Do**: `processing/dsm.py` con `generate_dsm(las_path, output_path, config)`: lettura chunked → griglia regolare → Z percentile 95° per cella → interpolazione IDW celle vuote → GeoTIFF output con CRS originale. Progress JSON Lines su stdout. Processing out-of-core se raster troppo grande.
- **Done**: GeoTIFF valido, Z corrispondono a altezze note cumuli (±tolleranza discretizzazione), progress JSON OK
- **Files**: `python-engine/src/heap_analyzer/processing/dsm.py`, `tests/test_dsm.py`

### F1.S04 — Stima DTM ⚠️ CRITICO
- **Deps**: F1.S03
- **Do**: `processing/dtm.py` con `estimate_dtm(dsm_path, output_path, config, ground_regions=None)`:
  - Auto: morphological opening (scipy.ndimage.grey_opening, kernel morpho_kernel_size) + verifica percentile basso zone periferiche
  - Manuale: ground_regions → media Z in quei poligoni, oppure manual_base_elevation → DTM piatto
  - Output: DTM GeoTIFF + JSON `{estimated_base_elevation, method}`
- **Done**: quota base stimata ±0.05 m dal valore noto su dataset sintetico. Morphological e percentile coerenti.
- **Files**: `python-engine/src/heap_analyzer/processing/dtm.py`, `tests/test_dtm.py`
- **MCP**: Sequential Thinking OBBLIGATORIO (pianificare strategia prima di codice). Context7 per scipy.ndimage.
- **⚠️**: componente PIÙ critico per accuratezza. Testare sensibilità a morpho_kernel_size.

### F1.S05 — nDSM + Segmentazione Cumuli
- **Deps**: F1.S03, F1.S04
- **Do**: `processing/segmentation.py` con:
  - `compute_ndsm(dsm_path, dtm_path, output_path)` → nDSM GeoTIFF
  - `segment_heaps(ndsm_path, config)`: sogliatura → morpho opening (3-5 px) → closing (5-10 px) → connected components (scipy.ndimage.label) → per componente: area, compattezza (4π×area/perimetro²), std altezze → filtri (vedi SPEC.md [PIPELINE] Fase 3) → label map + poligoni GeoJSON
  - `labels_to_polygons(label_map, transform)`: rasterio.features.shapes → semplificazione Shapely
  - `split_with_watershed(ndsm, label_map, label_id)`: scikit-image watershed, markers = massimi locali
- **Done**: 4 cumuli trovati su dataset sintetico (0 falsi positivi), poligoni validi, filtro macchinari funziona (test con parallelepipedo 5×3m h=3m uniforme → filtrato)
- **Files**: `python-engine/src/heap_analyzer/processing/segmentation.py`, `tests/test_segmentation.py`
- **MCP**: Sequential Thinking OBBLIGATORIO. Context7 per scipy.ndimage, scikit-image.

### F1.S06 — Calcolo Volumetrico e Metriche ⚠️ TEST CRITICO
- **Deps**: F1.S05
- **Do**: `processing/volume.py` con `compute_heap_metrics(ndsm_path, label_map_path, base_elevation, config)` → lista HeapMetrics (Pydantic, vedi SPEC.md [PIPELINE] Fase 4 per campi). Calcolo VETTORIZZATO numpy.
- **Done**: TUTTI i volumi ≤ 5% errore vs analitico a 0.10 m. Area ±5%. Altezza max ±0.15 m. Test convergenza multi-risoluzione (0.05, 0.10, 0.20, 0.50 m).
- **Files**: `python-engine/src/heap_analyzer/processing/volume.py`, `tests/test_volume.py`
- **MCP**: Sequential Thinking OBBLIGATORIO (verificare formula + edge cases).
- **⚠️**: test di validazione PIÙ importante del progetto. Insistere su confronto quantitativo rigoroso.

### F1.S07 — Pipeline Integrata + CLI Completa
- **Deps**: F1.S01–F1.S06
- **Do**: `pipeline.py` con ProcessingPipeline: validazione input → DSM → DTM → nDSM+segmentazione → volumi. Progress JSON Lines 0-100%. Salva output intermedi (GeoTIFF) + results.json. Gestione errori con contesto.
  CLI Click: `heap-analyzer process --las X --tiff Y --output Z [--config JSON]`, `validate --las X --tiff Y`, `generate-test-data --output DIR`. Exit code 0/1.
- **Done**: pipeline end-to-end su sintetico OK, tutti gli output creati, volumi ≤ 5%, progress JSON completo, config personalizzati funzionano
- **Files**: `python-engine/src/heap_analyzer/pipeline.py`, `cli.py`, `tests/test_pipeline.py`

### F1.S08 — Export CSV
- **Deps**: F1.S07
- **Do**: `export/csv_export.py` con `export_csv(heap_metrics, survey_metadata, output_path)`. Colonne: vedi SPEC.md [EXPORT] CSV. Separatore `;`, UTF-8 BOM, punto decimale. CLI: `heap-analyzer export-csv --results JSON --output CSV`.
- **Done**: CSV valido, apribile in Excel, dati corretti
- **Files**: `python-engine/src/heap_analyzer/export/csv_export.py`, `tests/test_csv_export.py`

---

## FASE 2 — UI Funzionale 2D (9 task)
> Output atteso: layout 3 pannelli, gestione progetti/rilievi, processing con progress, mappa OpenLayers con ortofoto+contorni, selezione cumulo con metriche.

### F2.S01 — Layout 3 Pannelli
- **Deps**: F0.S02
- **Do**: MainLayout con sidebar sinistra (250px, collassabile), viewport (flex-grow), pannello destro (300px, collassabile). Divisori draggable. Header bar + status bar. Tema scuro. UI italiana.
- **Done**: layout renderizzato, pannelli ridimensionabili, collapse OK
- **Files**: `frontend/src/components/layout/MainLayout.tsx`, `SidebarLeft.tsx`, `Viewport.tsx`, `SidebarRight.tsx`, `HeaderBar.tsx`, `StatusBar.tsx`

### F2.S02 — State Management (Zustand)
- **Deps**: F2.S01
- **Do**: store separate: projectStore, surveyStore, heapStore, uiStore, processingStore. Interfaccia con DB via IPC. Tipizzazione TS completa. Test unitari.
- **Done**: store create, tipizzate, testate. CRUD comunica con DB via IPC.
- **Files**: `frontend/src/stores/` (5 file), `frontend/src/types/` (interfacce)

### F2.S03 — Gestione Progetti CRUD
- **Deps**: F2.S01, F2.S02, F0.S05
- **Do**: lista progetti, dialog nuovo/modifica (nome, località, CRS dropdown 32632/32633, note, categorie materiali chip input), elimina con conferma, selezione → carica rilievi. Persistenza DB.
- **Done**: CRUD completo, dati persistono al riavvio, categorie OK
- **Files**: `frontend/src/components/projects/ProjectList.tsx`, `ProjectDialog.tsx`, `ProjectCard.tsx`

### F2.S04 — Import Rilievi (LAS + TIFF)
- **Deps**: F2.S03, F1.S01, F1.S02
- **Do**: bottone "Nuovo Rilievo", dialog: file picker LAS + TIFF (Electron native), data rilievo, operatore. Bottone "Valida" → Python `validate`. Mostra risultato. Bottone "Importa" (post validazione). Salva in DB (referenzia path, non copia).
- **Done**: select file → valida → importa → appare in lista
- **Files**: `frontend/src/components/surveys/SurveyList.tsx`, `ImportSurveyDialog.tsx`, `electron/src/ipc/handlers.ts`

### F2.S05 — Processing con Progress Bar
- **Deps**: F2.S04, F1.S07, F0.S04
- **Do**: bottone "Elabora", dialog parametri opzionale (risoluzione slider 0.05–0.50, soglia altezza 0.1–2.0, area min, modalità base auto/manuale). Progress bar: fase corrente, %, messaggio, tempo trascorso/stima rimanente, bottone annulla. Al completamento: salva heaps in DB, aggiorna survey paths, notifica "N cumuli trovati". Gestione errori.
- **Done**: processing parte, progress real-time da JSON Lines, risultati in DB, cancel OK, errori gestiti
- **Files**: `frontend/src/components/processing/ProcessingDialog.tsx`, `ProgressBar.tsx`, `stores/processingStore.ts`

### F2.S06 — Mappa 2D OpenLayers + Ortofoto
- **Deps**: F2.S01, F1.S02
- **Do**:
  - Python: `heap-analyzer create-tiles --tiff X --output DIR --min-zoom 0 --max-zoom 6` → tile piramidali `{z}/{x}/{y}.png`
  - Frontend: ol/Map + ol/View con proiezione EPSG:32632 (proj4.defs + ol/proj/proj4.register). ol/source/XYZ per tile locali. Pan/zoom fluido. ScaleLine. Coordinate cursore (E, N UTM).
- **Done**: ortofoto sintetica visualizzata, pan/zoom fluido, tile generati, coordinate UTM corrette, proiezione UTM nativa (NO Mercator)
- **Files**: `frontend/src/components/map/MapView.tsx`, `python-engine/src/heap_analyzer/export/tile_generator.py`, `tests/test_tile_generator.py`
- **MCP**: Context7 per OpenLayers (ol/Map, ol/View, ol/proj, ol/source/XYZ) e rasterio. Sequential Thinking per strategia tiling.

### F2.S07 — Overlay Contorni Cumuli
- **Deps**: F2.S06, F1.S05
- **Do**: ol/layer/Vector + ol/source/Vector + ol/format/GeoJSON. Poligoni colorati (per ID/categoria), bordo 2px, fill semitrasparente. Labels ID al centro. Hover highlight (ol/interaction/Select con pointerMove). Click → selezione cumulo → pannello destro. Overlay heatmap nDSM (scala blu→giallo→rosso, opacità slider). Toggle visibilità layer.
- **Done**: contorni sopra ortofoto, colorati, cliccabili. nDSM overlay OK. Toggle OK.
- **Files**: `frontend/src/components/map/HeapOverlay.tsx`, `NdsmOverlay.tsx`, `LayerControls.tsx`, `MapView.tsx`

### F2.S08 — Pannello Metriche Cumulo
- **Deps**: F2.S07, F2.S02
- **Do**: pannello destro con sezioni: identità (ID, label editabile, categoria dropdown), metriche (volume 3 dec, aree, altezze, quota base), posizione (centroide, bbox), azioni (escludi toggle, conferma manualmente, centra sulla mappa). Miniatura crop ortofoto. Riepilogo rilievo se nessun cumulo selezionato. Lista cumuli ordinabile in sidebar.
- **Done**: selezione mappa → metriche nel pannello. Lista sidebar. Miniatura. Azioni OK.
- **Files**: `frontend/src/components/heaps/HeapProperties.tsx`, `HeapList.tsx`, `HeapMinimap.tsx`

### F2.S09 — Export CSV dal Frontend
- **Deps**: F2.S08, F1.S08
- **Do**: bottone "Esporta CSV", dialog "Salva come" nativo, chiama Python engine, notifica completamento. Solo cumuli non esclusi e confermati.
- **Done**: CSV valido esportato
- **Files**: `frontend/src/components/export/ExportButton.tsx`, `electron/src/ipc/handlers.ts`

---

## FASE 3 — Editing Manuale + Vista 3D (5 task)

### F3.S01 — Editing Contorni Poligoni
- **Deps**: F2.S07
- **Do**: toolbar editing: Seleziona (default), Disegna poligono (ol/interaction/Draw), Modifica vertici (ol/interaction/Modify + Snap), Elimina (con conferma). Avanzati: dividi (linea taglio), unisci (merge Shapely Python). Dopo modifica: ricalcolo volume+metriche (Python), update DB, flag is_manually_confirmed. Undo/redo (≥10 step).
- **Done**: disegno, modifica, elimina, dividi, unisci OK. Volume ricalcolato. Undo/redo OK.
- **Files**: `frontend/src/components/map/EditingToolbar.tsx`, `PolygonEditor.tsx`, `MapView.tsx`, `python-engine/.../volume.py`
- **MCP**: Context7 per OpenLayers Draw/Modify/Snap

### F3.S02 — Override Quota Base + Terreno Noto
- **Deps**: F2.S08, F1.S04
- **Do**: pannello destro sezione "Quota di base": valore stimato, input override, slider ±1m (step 0.01), bottone "Ricalcola volumi", indicatore ΔV real-time. Strumento "Seleziona terreno noto": disegno poligoni sulla mappa → media Z DSM → suggerimento quota. Stile: tratteggio verde.
- **Done**: modifica quota → ricalcolo corretto. Selezione terreno noto OK.
- **Files**: `frontend/src/components/heaps/BaseElevationControl.tsx`, `map/GroundSelectionTool.tsx`, `processing/volume.py`

### F3.S03 — Conversione Point Cloud → Potree
- **Deps**: F0.S04, F1.S01
- **Do**: `export/pointcloud_export.py` con `export_for_potree(las_path, output_dir, config)`: lancia PotreeConverter (binario esterno) → output metadata.json + hierarchy.bin + octree nodes (Potree 2.0). CLI: `heap-analyzer export-pointcloud --las X --output DIR`. IPC handler per servire file Potree.
- **Done**: file Potree generati, metadata.json valido
- **Files**: `python-engine/src/heap_analyzer/export/pointcloud_export.py`, `tests/test_pointcloud_export.py`
- **⚠️**: NON reimplementare octree. Usare PotreeConverter. Focus su integrazione.

### F3.S04 — Vista 3D Potree
- **Deps**: F3.S03, F2.S01
- **Do**: `PotreeView.tsx`: Potree.Viewer in div React, loadPointCloud, 3 modalità colore (RGB, altezza nDSM, cumulo ID), point budget 2M. Navigazione OrbitControls + preset (top, side, reset). Piano base griglia (Three.js mesh). Toggle 2D/3D nel header. Performance > 30 FPS.
- **Done**: nuvola punti sintetica in 3D. Navigazione fluida. 3 colori OK. Toggle 2D/3D OK. Piano base visibile.
- **Files**: `frontend/src/components/three/PotreeView.tsx`, `PotreeWrapper.tsx`
- **MCP**: Context7 per Potree API
- **Nota**: Potree ha proprio lifecycle/canvas. Wrapper React gestire mount/unmount/resize. Potrebbe servire @pnext/three-loader come alternativa npm-friendly.

### F3.S05 — Sezioni Trasversali
- **Deps**: F3.S04
- **Do**: strumento "Sezione": linea sulla mappa 2D → Python estrae profilo (dsm, dtm) → grafico altezza vs distanza (recharts/chart.js) in pannello flottante. Area colorata = volume sezione. In 3D: piano sezione semitrasparente (mesh Three.js). CLI: `heap-analyzer cross-section --dsm X --dtm Y --line x1,y1,x2,y2 --output JSON`.
- **Done**: sezione tracciabile, profilo visibile, piano in 3D OK
- **Files**: `frontend/src/components/map/CrossSectionTool.tsx`, `charts/CrossSectionChart.tsx`, `python-engine/.../processing/cross_section.py`

---

## FASE 4 — Classificazione VLM (4 task)

### F4.S01 — Setup VLM Locale + GPU
- **Deps**: F0.S04
- **Do**: `classification/vlm_service.py` con VLMService: check_gpu(), list_available_models() (qwen2.5-vl-7b ~14GB, qwen2.5-vl-14b ~28GB warning, gemma-3-12b ~24GB), check/download/load/unload model. Cartella modelli configurabile. UI impostazioni: stato GPU/VRAM, lista modelli, download con progress, selezione attivo, warning VRAM. Gestione GPU assente: messaggio chiaro + solo manuale.
- **Done**: GPU rilevata, modelli listati, download+load funzionano, gestione graceful senza GPU
- **Files**: `python-engine/.../classification/vlm_service.py`, `electron/src/services/vlm-service.ts`, `frontend/.../settings/VLMSettings.tsx`

### F4.S02 — Crop Ortofoto per Cumulo
- **Deps**: F1.S02, F1.S05
- **Do**: `processing/ortho_crop.py` con `crop_ortho_for_heap(tiff_path, polygon, output_path, padding_percent=20)`: bbox + padding → rasterio windowed read → maschera opzionale → resize max 1024×1024 → PNG/JPEG. Batch: `crop_all_heaps()`. CLI: `heap-analyzer crop-ortho`.
- **Done**: crop corretti per ogni cumulo
- **Files**: `python-engine/.../processing/ortho_crop.py`, `tests/test_ortho_crop.py`

### F4.S03 — Classificazione VLM
- **Deps**: F4.S01, F4.S02
- **Do**: `classification/vlm_classifier.py` con VLMClassifier: classify(image_path, categories) → {category, confidence, reasoning}. Prompt strutturato (vedi SPEC.md [VLM]). Gestione errori (timeout, parsing, VRAM). Batch: classify_all_heaps() con modello caricato una volta. Progress JSON per cumulo. CLI: `heap-analyzer classify`. Integrazione pipeline come Fase 5. Salva in DB: material_category, material_confidence.
- **Done**: classificazione produce risultati per ogni cumulo. Errori gestiti. DB aggiornato.
- **Files**: `python-engine/.../classification/vlm_classifier.py`, `tests/test_vlm_classifier.py`

### F4.S04 — UI Classificazione + Manuale Rapida
- **Deps**: F4.S03, F2.S08
- **Do**: pannello destro: categoria VLM + confidence + crop preview + dropdown override + warning se confidence < 0.7 + bottone "Reclassifica". **Workflow manuale rapido** (Ctrl+Shift+C): cumuli uno per uno con crop grande, hotkey 1-9 per categorie, frecce ← → navigazione, spazio skip, indicatore progresso. Vista d'insieme sidebar: icona/colore categoria, filtro, conteggio. Bottone "Classifica tutto" (VLM batch, richiede modello caricato, warning se non disponibile).
- **Done**: classificazione visibile, override OK, workflow manuale fluido con hotkey, filtro categoria OK
- **Files**: `frontend/.../heaps/MaterialClassification.tsx`, `QuickClassifyView.tsx`, `processing/ClassificationDialog.tsx`

### F4.S05 — Validazione VLM della Segmentazione (QA)
- **Deps**: F4.S01, F4.S02, F2.S10 (DTM fix)
- **Do**: nuovo passaggio QA post-segmentazione. Per ogni cumulo rilevato: crop ortofoto bbox + margine 10% con contorno poligono sovrapposto → VLM con prompt binario "valido|falso|incerto + confidenza 0-1 + motivazione breve" (falsi tipici su siti industriali: binari, strade, marciapiedi, ombre, muri). Salva in DB `heaps.vlm_validation_label` TEXT + `heaps.vlm_validation_score` REAL + `heaps.vlm_validation_reason` TEXT. UI: badge rosso/giallo/verde nella heap list, click apre preview con crop + motivazione, bottone "Escludi" o "Conferma". Opzione avanzata: immagine ibrida RGB + nDSM colormap per sfruttare info altezza (testare se Qwen3-VL-8B la gestisce).
- **Done**: validazione eseguita per tutti i cumuli, badge visibili, workflow di review funzionante, accuracy misurabile su dataset reale (falsi positivi scartati rispetto a ground truth manuale).
- **Files**: `python-engine/.../classification/vlm_validator.py`, `tests/test_vlm_validator.py`, `frontend/.../heaps/ValidationBadge.tsx`, `ValidationReviewDialog.tsx`
- **Rationale**: dataset reale Pittini (260330 Acciaieria) ha prodotto cumuli con falsi positivi su binari/strade. F2.S10 fix DTM ha ridotto il problema (da 21 a 16 rilevamenti, con eliminazione di molti FP), ma VLM come safety net cattura errori sistematici residui che l'algoritmo non auto-diagnostica.

---

## FASE 2b — Import Flussi Alternativi

### F2.S10 — Import da cartella DJI Terra ✅ DONE
- **Do**: scanner cartella DJI (`map/dsm.tif`, `map/result.tif`, `cloud_merged.las`), DJITerraManifest Pydantic, CLI `scan-dji-terra`. Pipeline accetta `precomputed_dsm_path` per saltare la generazione DSM. DTM usa classificazione ASPRS ground (class=2) dal LAS quando disponibile (fallback: morfologico). DB: `surveys.source_type` e `surveys.dji_folder_path`. IPC `dji:scanFolder`/`dji:importSurvey`. UI `ImportDJIDialog` con toggle "Usa DSM DJI" (ON default) e "Copia file" (OFF default).
- **Impact measured**: su sito reale Acciaieria Udine, cumuli 21→16 (FP binari rimossi), volume 5084→16760 m³ (DTM non tronca più cime), durata 516→304 s.
- **Files**: `python-engine/.../io/dji_terra_scanner.py`, `.../processing/dtm.py` (+strategy), `electron/src/ipc/dji-handlers.ts`, `frontend/.../surveys/ImportDJIDialog.tsx`

---

## FASE 5 — Report PDF (3 task)

### F5.S01 — Mappa Panoramica per Report
- **Deps**: F2.S06, F2.S07
- **Do**: `report/map_renderer.py`: render_site_overview() (ortofoto + contorni numerati/colorati + legenda + scala + nord + titolo → PNG 150dpi), render_heap_detail() (crop con contorno + annotazioni). Usa matplotlib.
- **Done**: immagini generate ad alta risoluzione con tutti gli elementi
- **Files**: `python-engine/.../report/map_renderer.py`, `tests/test_map_renderer.py`

### F5.S02 — Report PDF Completo
- **Deps**: F5.S01, F1.S06, F4.S02
- **Do**: `report/pdf_generator.py` con ReportGenerator. Struttura: vedi SPEC.md [EXPORT] PDF. Layout professionale (serif titoli, sans-serif testo). Lingua italiana. reportlab o WeasyPrint. CLI: `heap-analyzer generate-report`.
- **Done**: PDF generato con tutte le sezioni, layout professionale, dati corretti
- **Files**: `python-engine/.../report/pdf_generator.py`, `tests/test_pdf_generator.py`

### F5.S03 — Export Report dal Frontend
- **Deps**: F5.S02, F2.S09
- **Do**: menu "Genera Report" (PDF / CSV / entrambi), dialog (cartella, logo, note, checkbox solo confermati), progress bar, notifica con link apertura.
- **Done**: report PDF generato dall'interfaccia
- **Files**: `frontend/.../export/ReportDialog.tsx`, `ExportButton.tsx`

---

## FASE 6 — Confronto Temporale (4 task)

### F6.S01 — Matching Spaziale Cumuli
- **Deps**: F1.S05, F1.S06
- **Do**: `comparison/matcher.py` con match_heaps(heaps_a, heaps_b, iou_threshold=0.3): IoU poligoni Shapely → matrice → assegnamento greedy/Hungarian → MatchResult (matched con delta, removed, added, total_delta_volume). CLI: `heap-analyzer compare`. Salva in DB (comparisons). Test: 2 dataset sintetici (1 aggiunto, 1 rimosso, 1 modificato).
- **Done**: matching corretto su sintetici, delta OK, nuovi/rimossi identificati
- **Files**: `python-engine/.../comparison/matcher.py`, `tests/test_matcher.py`
- **MCP**: Sequential Thinking OBBLIGATORIO (greedy vs Hungarian, casi ambigui)

### F6.S02 — Mappa Differenziale + Delta
- **Deps**: F6.S01, F2.S07
- **Do**: Python: `compute_delta_ndsm(ndsm_a, ndsm_b, output)` → delta GeoTIFF. Frontend: selezione 2 rilievi, overlay rosso/blu, tabella comparativa (metriche A, B, delta, %), indicatore riepilogo, colori contorni (verde=nuovo, rosso=cresciuto, blu=diminuito, grigio=rimosso).
- **Done**: visualizzazione differenziale OK, tabella delta corretta, colori OK
- **Files**: `python-engine/.../comparison/delta.py`, `frontend/.../comparison/ComparisonView.tsx`, `DeltaOverlay.tsx`, `ComparisonTable.tsx`

### F6.S03 — Timeline e Grafici
- **Deps**: F6.S01, F0.S05
- **Do**: TimelineChart (recharts): andamento volume per cumulo nel tempo. Barre stacked volume totale per rilievo/categoria. Tab "Storico": grafici + tabella storica.
- **Done**: grafici con dati multi-rilievo, timeline corretta
- **Files**: `frontend/.../comparison/TimelineChart.tsx`, `VolumeHistoryChart.tsx`

### F6.S04 — Confronto nel Report PDF
- **Deps**: F6.S01, F5.S02
- **Do**: sezione opzionale report: mappa differenziale (matplotlib), tabella comparativa, grafico delta volumi, riepilogo testuale. Aggiornare ReportGenerator.
- **Done**: report PDF include sezione confronto quando disponibile
- **Files**: `python-engine/.../report/pdf_generator.py`, `comparison_renderer.py`

---

## FASE 7 — Export GIS + Rifinitura (4 task)

### F7.S01 — Export GeoJSON + Shapefile
- **Deps**: F1.S05, F1.S06
- **Do**: `export/geo_export.py`: export_geojson() e export_shapefile() con GeoPandas/Fiona. Attributi: tutte le metriche. CRS dal progetto. Shapefile: nomi colonna ≤ 10 char. CLI: `heap-analyzer export-geo`. UI: opzione in ExportDialog.
- **Done**: file apribili in QGIS, attributi corretti, CRS valido
- **Files**: `python-engine/.../export/geo_export.py`, `tests/test_geo_export.py`

### F7.S02 — Impostazioni App
- **Deps**: F2.S01
- **Do**: pagina impostazioni: generali (cartella dati), processing (default parametri, path Python), VLM (cartella modelli, modello preferito, VRAM), report (logo, nome azienda). Persistenza JSON in userData Electron.
- **Done**: impostazioni salvate, persistono al riavvio, influenzano processing e report
- **Files**: `frontend/.../settings/SettingsPage.tsx`, `electron/src/services/settings.ts`

### F7.S03 — Gestione Errori + Robustezza
- **Deps**: tutte le fasi
- **Do**: Error boundary React. Python: gestione graceful di file corrotto, non-GeoTIFF, CRS mismatch, zone senza dati, cumuli piccoli/grandi. Logging strutturato (Python stderr, electron-log). Rotazione log. Crash recovery (intermedi non cancellati). Test per ogni edge case.
- **Done**: app non crasha per errori prevedibili, messaggi chiari, log funzionante
- **Files**: `frontend/.../ErrorBoundary.tsx`, `python-engine/.../utils/logging.py`

### F7.S04 — Ottimizzazione Performance
- **Deps**: tutte le fasi
- **Do**: benchmark pipeline (target < 15 min su 2 ha). Benchmark 3D (> 30 FPS via Potree). RAM < 16 GB. UI mai bloccata. Script: `python-engine/scripts/benchmark.py`.
- **Done**: tutti i target performance rispettati
- **Files**: `python-engine/scripts/benchmark.py`

---

## FASE 8 — Packaging (2 task)

### F8.S01 — Packaging Electron + Python Embedded
- **Deps**: tutte le fasi
- **Do**: electron-builder. Python embedded (PyInstaller o embeddable package Windows). PotreeConverter nel bundle. Modelli VLM NON inclusi (download al primo avvio). Installer .exe (NSIS) o .msi. Target < 2 GB senza VLM.
- **Done**: installer genera OK, installazione su Windows pulito funziona, Python processing OK
- **Files**: `electron-builder.yml`, `python-bridge.ts`, script build

### F8.S02 — Test End-to-End su Macchina Pulita
- **Deps**: F8.S01
- **Do**: workflow completo su Windows pulito: crea progetto → import → processing → mappa 2D → 3D → editing → classificazione VLM+manuale → report PDF → CSV+GeoJSON → confronto. Screenshot Playwright.
- **Done**: workflow completo senza errori su macchina pulita
- **Files**: documentazione test, fix eventuali

---

## Riepilogo

| Fase | Task | Focus |
|------|------|-------|
| F0 | 9 | Setup: Electron, Python, IPC, DB, test, Playwright |
| F1 | 8 | Pipeline core: DSM, DTM, segmentazione, volumi |
| F2 | 9 | UI 2D: layout, progetti, OpenLayers, metriche |
| F3 | 5 | Editing, quota base, Potree 3D, sezioni |
| F4 | 4 | VLM locale, classificazione, UI review |
| F5 | 3 | Report PDF |
| F6 | 4 | Confronto temporale |
| F7 | 4 | Export GIS, impostazioni, robustezza, performance |
| F8 | 2 | Packaging Windows |
| **Tot** | **48** | |

## Task Parallelizzabili
- F0.S02 ∥ F0.S03 (Electron ∥ Python setup)
- F1.S01 ∥ F1.S02 (loader LAS ∥ loader TIFF)
- F2.S01–F2.S03 ∥ F1.S01–F1.S08 (UI ∥ pipeline, dopo F0)
