# SPEC.md — Heap Analyzer Specifiche Tecniche v1.1

<!-- ISTRUZIONI PER CLAUDE CODE:
Questo file è il riferimento autorevole per TUTTE le decisioni di implementazione.
Quando c'è conflitto tra questo file e DEV-PLAN.md, questo file vince.
Struttura: le sezioni sono taggate con [TAG] per lookup rapido via grep.
Usa `ctrl+f` o grep per: [CONSTRAINT], [PIPELINE], [SCHEMA], [IPC], [UI], [EXPORT], [VLM], [PERF], [RISK].
-->

## [CONSTRAINT] Vincoli Non Negoziabili

OS: Windows 10/11 64-bit.
GPU: NVIDIA RTX 3090, 24 GB VRAM.
RAM: 32 GB sistema, budget processing < 16 GB.
Stack: Electron + React + TypeScript (frontend), Python 3.11+ subprocess (processing), SQLite (dati), Potree+Three.js (3D), OpenLayers (2D map).
Esecuzione: 100% locale, zero cloud, zero server remoto.
Lingua UI/report: italiano.
Lingua codice (variabili, funzioni, classi): inglese.
CRS: UTM Zona 32N (EPSG:32632) o 33N (EPSG:32633).

## [CONSTRAINT] Dati di Input

### Nuvola di Punti
- Formato: LAS / LAZ
- Origine: fotogrammetria drone DJI Matrice M3
- Densità: 100–500+ punti/m²
- Classificazione: raw (default); ground/non-ground se pre-processata DJI Modify
- CRS: UTM 32N o 33N
- Size: 1–5 GB

### Ortofoto
- Formato: GeoTIFF (.tif)
- Origine: stesso volo della nuvola di punti → co-registrata perfettamente
- Risoluzione: ~1 cm/pixel (es. 21118×17746 px per ~2 ha)
- CRS: stesso della nuvola di punti
- Size: ~1 GB

### Scala Siti
- Sito tipico: ~2 ha (20.000 m²)
- Cumulo tipico: ~3.500 m²
- Altezza cumuli: 1–8 m
- Terreno: generalmente piatto/quasi piatto
- Cumuli: SEMPRE fisicamente separati (non sovrapposti)
- Contesto: acciaierie/impianti siderurgici
- Presenti: macchinari mobili (gru, escavatori, container) che cambiano posizione tra rilievi

## [IPC] Protocollo Comunicazione Electron ↔ Python

REGOLA ASSOLUTA: ogni riga su stdout del processo Python = un oggetto JSON autonomo (JSON Lines).
Campo obbligatorio: `"type"` con valore in: `"progress"`, `"result"`, `"error"`, `"warning"`.
VIETATO: qualsiasi output non-JSON su stdout (print, log, stack trace).
Log/debug: SOLO su stderr.
Encoding: UTF-8 (gestire BOM Windows).
Cancellazione: SIGTERM con grace period → SIGKILL.
Timeout: configurabile, default 30 min.
Buffer: il parser Electron deve accumulare righe parziali fino a newline.

Esempi:
```
{"type": "progress", "phase": "dsm", "percent": 45, "message": "Generazione DSM..."}
{"type": "result", "data": {"heaps": [...], "metadata": {...}}}
{"type": "error", "code": "CRS_MISMATCH", "message": "CRS LAS e TIFF non compatibili"}
{"type": "warning", "message": "3 celle DSM senza dati, interpolate"}
```

## [PIPELINE] Pipeline di Elaborazione — 5 Fasi Sequenziali

### Fase 1: DSM (Digital Surface Model)
- Input: LAS/LAZ
- Output: GeoTIFF raster, risoluzione configurabile (default 0.10 m/pixel)
- Metodo: rasterizzazione su griglia regolare, Z = percentile 95° (default) o max per cella
- Celle vuote: interpolazione IDW
- MUST: processing chunked/out-of-core per file fino a 5 GB

### Fase 2: DTM (Digital Terrain Model) / Piano di Riferimento
- Input: DSM, opzionalmente classificazione ground
- Output: GeoTIFF raster DTM + valore scalare `estimated_base_elevation`
- Strategia automatica: morphological opening (kernel ampio, default 50 px = 5m @0.10m/px) oppure percentile basso (5°–10°) delle zone periferiche
- Strategia manuale: quota inserita dall'operatore, oppure selezione grafica aree "terreno noto" → media Z in quelle aree
- ⚠️ CRITICITÀ: errore 5 cm sulla base × 3.500 m² cumulo = ±175 m³ errore volume. Mostrare SEMPRE il valore stimato + permettere override manuale.

### Fase 3: Segmentazione Cumuli
- Input: DSM, DTM, ortofoto
- Output: label map raster (GeoTIFF) + poligoni vettoriali (GeoJSON)
- Step: nDSM = DSM − DTM → sogliatura (default 0.5 m) → morphological opening (rimuovi rumore) → closing (chiudi buchi) → connected components labeling → filtri multi-criterio
- Filtri macchinari/strutture:
  - Area < min_heap_area (50 m²) → escludi
  - Area > max_heap_area (50.000 m²) → flag review
  - Compattezza > 0.85 AND area < 500 m² → probabile macchinario
  - Std altezze < 0.2 m AND media altezze > 2 m → probabile struttura
- Fallback: watershed segmentation se cumuli erroneamente uniti (markers = massimi locali nDSM)
- Editing manuale: disegno nuovo poligono, modifica vertici, elimina, dividi (linea taglio), unisci (merge Shapely)

### Fase 4: Calcolo Volumetrico
- Input: nDSM, label map, quota base
- Formula: **V = Σ (nDSM(i,j)) × Δx × Δy** per pixel dove nDSM > soglia AND label == heap_id
- Deve essere vettorizzato con numpy (NO loop Python sui pixel)
- Target accuratezza: errore < 5% vs calcolo analitico a densità > 100 pts/m²

Metriche per cumulo:
| Metrica | Unità | Note |
|---------|-------|------|
| volume | m³ | sopra piano base |
| planimetric_area | m² | proiezione orizzontale |
| surface_area | m² | area 3D (approssimazione: Δx×Δy/cos(θ) per cella) |
| max_height | m | max(nDSM) nel cumulo |
| mean_height | m | mean(nDSM) nel cumulo |
| base_elevation | m s.l.m. | quota piano riferimento usata |
| centroid | E, N UTM | baricentro planimetrico |
| bbox | min_e, min_n, max_e, max_n | rettangolo minimo |

### Fase 5: Classificazione Materiale (VLM)
- Input: crop ortofoto per cumulo + lista categorie dall'operatore
- Runtime: inferenza locale diretta RTX 3090 via transformers+torch oppure llama-cpp-python (GGUF)
- Modelli: Qwen2.5-VL-7B (~14 GB VRAM), Qwen2.5-VL-14B (~28 GB, warning), Gemma-3-12B (~24 GB)
- Output: categoria + confidence + reasoning (JSON)
- Categorie: configurabili per progetto (es. "rottame ferroso", "ghisa", "scorie", "cascami", "RAEE")
- Override: l'operatore può SEMPRE sovrascrivere
- Fallback: workflow classificazione manuale rapida con hotkey numerici (1-9) mappati a categorie

## [SCHEMA] Database SQLite

```sql
CREATE TABLE projects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  location TEXT,
  crs TEXT DEFAULT 'EPSG:32632',
  notes TEXT,
  material_categories TEXT, -- JSON array stringhe
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE surveys (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  survey_date DATE NOT NULL,
  operator TEXT,
  las_path TEXT NOT NULL,
  tiff_path TEXT NOT NULL,
  processing_params TEXT, -- JSON ProcessingConfig
  processing_status TEXT DEFAULT 'pending', -- pending|processing|completed|error
  dsm_path TEXT,
  dtm_path TEXT,
  ndsm_path TEXT,
  label_map_path TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE heaps (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  survey_id INTEGER NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
  label TEXT,
  polygon TEXT NOT NULL, -- GeoJSON geometry
  volume REAL,
  planimetric_area REAL,
  surface_area REAL,
  max_height REAL,
  mean_height REAL,
  base_elevation REAL,
  centroid_e REAL,
  centroid_n REAL,
  bbox_min_e REAL,
  bbox_min_n REAL,
  bbox_max_e REAL,
  bbox_max_n REAL,
  material_category TEXT,
  material_confidence REAL,
  is_manually_confirmed INTEGER DEFAULT 0,
  is_excluded INTEGER DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE comparisons (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  survey_a_id INTEGER NOT NULL REFERENCES surveys(id),
  survey_b_id INTEGER NOT NULL REFERENCES surveys(id),
  results TEXT, -- JSON matching results
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

Driver: better-sqlite3 (sincrono, performante in Electron).
Storage: cartella locale configurabile. File originali referenziati per path (non copiati). Intermedi (DSM, DTM, nDSM, label_map) salvati come GeoTIFF in sotto-cartella rilievo.

## [UI] Interfaccia Utente

### Layout
3 pannelli ridimensionabili:
- Sidebar sinistra (250px default, collassabile): navigazione progetti → rilievi → cumuli
- Viewport centrale (flex-grow): mappa 2D / vista 3D (toggle switch)
- Pannello destro (300px default, collassabile): proprietà cumulo selezionato, parametri, editing

Header: logo + "Heap Analyzer", titolo progetto corrente, toggle 2D/3D, impostazioni.
Status bar: stato Python engine, memoria, stato processing.
Tema: scuro (grigio scuro sfondo, testo chiaro).

### Vista 2D (OpenLayers)
- Proiezione UTM nativa (EPSG:32632/33) via proj4 + ol/proj/proj4.register — NO Mercator
- Ortofoto: tile piramidali generati da Python, serviti localmente
- Overlay vettoriale: contorni cumuli colorati per categoria/ID, labels, hover highlight, click → selezione
- Overlay raster: heatmap nDSM (blu→giallo→rosso), opacità regolabile
- Editing: ol/interaction/Draw, Modify, Snap per poligoni
- Controlli: ScaleLine, coordinate cursore (E, N UTM)

### Vista 3D (Potree)
- Potree gestisce automaticamente: octree LOD, frustum culling, streaming nodi
- Colorazione: RGB originale, altezza nDSM, cumulo di appartenenza
- Navigazione: OrbitControls integrati Potree + preset (top, side, reset)
- Piano base: griglia semitrasparente alla quota base (mesh Three.js nella scena Potree)
- Sezioni trasversali: linea sulla mappa → profilo altezza (DSM vs DTM) in grafico 2D

## [EXPORT] Output e Report

### Report PDF
Struttura: copertina → indice → panoramica sito (mappa + riepilogo) → schede cumuli (1 pag/cumulo: crop ortofoto, metriche, categoria) → tabella riepilogativa → grafici (istogramma volumi, torta categorie) → parametri processing → sezione confronto temporale (se disponibile).
Layout: font serif titoli, sans-serif testo, colori sobri. Lingua: italiano.
Lib: reportlab o WeasyPrint.

### Report CSV
Una riga per cumulo. Colonne: ID, Volume_m3, Area_planimetrica_m2, Area_superficiale_m2, Altezza_max_m, Altezza_media_m, Quota_base_mslm, Centroide_E, Centroide_N, BBox_minE, BBox_minN, BBox_maxE, BBox_maxN, Categoria_materiale, Data_rilievo.
Separatore: punto e virgola. Encoding: UTF-8 con BOM. Decimali: punto.

### Export GIS
GeoJSON (.geojson) e Shapefile (.shp + .dbf + .shx + .prj).
Attributi: tutte le metriche. CRS dal progetto.
Shapefile: nomi colonna ≤ 10 char.
Lib: GeoPandas + Fiona.

## [COMPARISON] Confronto Temporale

### Matching spaziale
- Per ogni coppia cumuli (rilievo A, rilievo B): IoU poligoni con Shapely
- Matrice sovrapposizione → assegnamento greedy o Hungarian
- IoU > soglia → "Matchato" (calcola delta volume, area, altezza)
- Solo in A → "Rimosso"
- Solo in B → "Nuovo"

### Visualizzazione
- Delta nDSM raster: rosso = crescita, blu = decrescita
- Tabella comparativa per cumulo matchato
- Timeline: grafici andamento volume per cumulo nel tempo (recharts)
- Colori contorni: verde = nuovo, rosso = cresciuto, blu = diminuito, grigio = rimosso

## [VLM] Classificazione VLM — Dettagli Implementativi

Prompt template:
```
Sei un esperto di materiali siderurgici. Analizza questa immagine aerea di un cumulo 
di materiale in un'acciaieria. Classifica il materiale in UNA delle seguenti categorie: 
{categories_list}. 
Rispondi SOLO con un JSON: {"category": "<categoria>", "confidence": <0.0-1.0>, "reasoning": "<motivazione breve>"}
```

Crop ortofoto: bounding box poligono + 20% padding, max 1024×1024 px, maschera opzionale fuori poligono.
Modello caricato una volta, riusato per tutti i cumuli (no reload).
Confidence < 0.7 → warning "classificazione incerta".
Gestione: GPU assente → messaggio chiaro + solo classificazione manuale.

## [PERF] Requisiti Non Funzionali

| Requisito | Target |
|-----------|--------|
| Processing 2 ha (LAS 2GB + TIFF 1GB) | < 15 minuti |
| RAM durante processing | < 16 GB |
| File LAS fino a 5 GB | processing out-of-core |
| UI durante processing | MAI bloccata (subprocess separato) |
| Accuratezza volume | errore < 5% vs analitico (densità > 100 pts/m²) |
| Rendering 3D | > 30 FPS (Potree LOD automatico) |
| Usabilità | workflow completo senza assistenza dopo 30 min formazione |
| Installer | singolo .exe/.msi, < 2 GB (senza modelli VLM) |

## [RISK] Rischi e Mitigazioni

| Rischio | Mitigazione |
|---------|-------------|
| Terreno non piatto | DTM adattivo + override manuale SEMPRE disponibile |
| Cumuli erroneamente uniti | Watershed fallback + split manuale |
| Macchinari confusi con cumuli | Filtri multi-criterio + esclusione manuale |
| File LAS 5 GB | Out-of-core obbligatorio, chunked reading, decimazione opzionale |
| VLM inaccurato | Classificazione manuale rapida SEMPRE disponibile, override, test multi-modello |
| Performance 3D | Potree LOD/streaming nativo, point budget configurabile |

## [LIBS] Librerie Python

| Libreria | Versione | Uso |
|----------|----------|-----|
| laspy[lazrs] | ≥2.0 | LAS/LAZ read/write |
| rasterio | ≥1.3 | GeoTIFF read/write, CRS |
| numpy | ≥1.24 | raster ops, calcoli matriciali |
| scipy | ≥1.10 | IDW, morphological ops, ndimage |
| scikit-image | ≥0.21 | watershed, connected components |
| shapely | ≥2.0 | geometrie vettoriali |
| geopandas | ≥0.13 | export GIS |
| fiona | ≥0.9 | export Shapefile |
| matplotlib | ≥3.7 | grafici report |
| reportlab | - | PDF generation |
| click | - | CLI |
| pydantic | ≥2.0 | validazione config/output |
| transformers + torch | latest | inferenza VLM locale |
| llama-cpp-python | latest | alternativa VLM GGUF |

Binari esterni: PotreeConverter 2.x (conversione LAS → formato Potree octree).

## [CONFIG] Parametri Processing Default (Pydantic ProcessingConfig)

```python
dsm_resolution: float = 0.10      # metri/pixel
height_threshold: float = 0.5     # metri, soglia minima nDSM
min_heap_area: float = 50.0       # m², sotto = escluso
max_heap_area: float = 50000.0    # m², sopra = flag review
base_percentile: float = 5.0      # percentile per stima terreno
morpho_kernel_size: int = 50      # pixel (= 5m @ 0.10m/px)
```
