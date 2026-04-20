# Performance Targets — Heap Analyzer

> **Stato:** definito in SPEC.md, misurato sinteticamente in F7.S04. Una
> misurazione su dataset reale (2 ha, 8M punti) **non è ancora stata eseguita**
> perché il dataset di riferimento non è disponibile al team di sviluppo.

## Target SPEC (da `docs/SPEC.md` §[PERF])

| Requisito | Target | Verifica |
|-----------|--------|----------|
| Pipeline end-to-end (2 ha, LAS 2 GB + TIFF 1 GB) | **< 15 minuti** | `scripts/benchmark.py` su dataset reale |
| Picco RAM durante processing | **< 16 GB** | campionato da benchmark via psutil |
| Accuratezza volume (densità ≥ 100 pts/m²) | **< 5% vs analitico** | già validato in F1.S06 su sintetico |
| Rendering 3D (Potree) | **> 30 FPS sostenuti** a 2M punti | misura in browser (F8) |
| Blocco UI | main thread < **50 ms** | processing in subprocess già garantisce |
| Out-of-core LAS | fino a **5 GB** | `LasReader.iter_chunks()` (F1.S01) |
| Installer | **< 2 GB** senza modelli VLM | misura in F8 |

## Come eseguire il benchmark

### Prerequisiti

- Python 3.11 con `heap-analyzer` installato (`pip install -e .`)
- `psutil` (già dichiarato in `pyproject.toml`) per campionare la RAM
- Un dataset LAS + GeoTIFF valido (reale o sintetico)

### Smoke test su dataset sintetico

```
cd python-engine

# 1) Genera il dataset sintetico (4 cumuli geometrici, 200x200 m, volumi noti)
py -3.11 -m heap_analyzer generate-test-data --output ./synth

# 2) Esegui il benchmark
py -3.11 scripts/benchmark.py \
  --las ./synth/test.las \
  --tiff ./synth/test.tif \
  --output ./bench-output \
  --label synthetic-smoke
```

L'output contiene:

- `bench-output/dsm.tif`, `dtm.tif`, `ndsm.tif`, `label_map.tif`
- `bench-output/results.json`
- `bench-output/benchmark-<timestamp>.json` → report performance

### Esecuzione su dataset reale (2 ha)

```
py -3.11 scripts/benchmark.py \
  --las /path/to/real_site.las \
  --tiff /path/to/real_site.tif \
  --output ./bench-real \
  --label site-2ha-2026Q2
```

Il processo è single-threaded lato Python (le librerie numpy/scipy possono
sfruttare BLAS multi-thread). Evitare di eseguirlo in parallelo ad altre
applicazioni RAM-intensive per ottenere una misura pulita.

## Schema del report JSON

```json
{
  "meta": {
    "timestamp": "ISO-8601 UTC",
    "label": "etichetta dataset",
    "dataset_las": "path",
    "dataset_tiff": "path",
    "cpu": "stringa CPU",
    "python": "3.11.x",
    "os": "Windows 11 ..."
  },
  "stages": [
    {"name": "dsm",          "duration_s": 12.3},
    {"name": "dtm",          "duration_s": 4.1},
    {"name": "ndsm",         "duration_s": 2.2},
    {"name": "segmentation", "duration_s": 8.5},
    {"name": "volume",       "duration_s": 6.8},
    {"name": "tiles",        "duration_s": 25.1},
    {"name": "heatmap",      "duration_s": 1.4}
  ],
  "total_duration_s": 60.4,
  "peak_ram_mb": 4096.0,
  "heap_count": 4,
  "warnings": []
}
```

## Baseline attuale (sintetico)

> **Riferimento sintetico, non rappresentativo dei target SPEC 2 ha.**
> Il dataset sintetico ha ~1/10 dei punti e ~1/100 della superficie di un
> rilievo reale 2 ha. Non è valido per affermare che i target SPEC sono
> raggiunti.

La tabella seguente verrà popolata la prima volta che `scripts/benchmark.py`
viene eseguito sul dataset sintetico (vedi §"Smoke test"). Il tempo totale
atteso è < 60 s su hardware 2025-class — l'indicazione serve a rilevare
regressioni gravi, non a validare i target SPEC.

| Stage | Duration (s) | Note |
|-------|--------------|------|
| dsm | — | generazione DSM da nuvola sintetica (~100k punti) |
| dtm | — | stima terreno via morphological opening |
| ndsm | — | sottrazione DSM − DTM |
| segmentation | — | etichettatura componenti connesse + filtri |
| volume | — | sommatoria vettorizzata nDSM × cell_area |
| tiles | — | generazione piramide XYZ (zoom max auto) |
| heatmap | — | PNG colormap nDSM |
| **Totale** | **—** | |
| Picco RAM (MB) | — | |

## Come rilevare regressioni

1. Eseguire il benchmark su **stesso hardware, stessi file** prima e dopo una
   modifica significativa della pipeline.
2. Confrontare il nuovo `benchmark-*.json` con il precedente. Una regressione
   > 20% su un singolo stage giustifica un'analisi; > 50% va trattata come
   bug.
3. Non committare i file `benchmark-*.json`: sono artefatti locali (già
   esclusi via `.gitignore` se posti sotto `bench-*/`).

## Rendering 3D e UI

Il benchmark Python **non** misura il rendering 3D. La verifica dei target
"> 30 FPS" e "UI non bloccata" si fa:

- **3D:** aprire la vista Potree su un dataset ≥ 2M punti, guardare il
  `stats` panel integrato (Potree mostra FPS).
- **UI:** durante un processing lungo (es. 2 ha), verificare che pannelli,
  mappa 2D e pulsanti rimangano reattivi — il processing gira in subprocess
  Python separato, quindi per costruzione non blocca il main thread Electron.
