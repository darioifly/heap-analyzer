# Heap Analyzer

**Analisi volumetrica di cumuli di materiali da nuvole di punti LiDAR**

Applicazione desktop Windows per l'analisi automatica di cumuli di materiali (rottami ferrosi, scorie, ecc.) in acciaierie e impianti siderurgici, a partire da rilievi drone con nuvola di punti LAS e ortofoto GeoTIFF.

## Stack Tecnologico

| Layer | Tecnologia |
|-------|-----------|
| Desktop app | Electron + TypeScript |
| UI | React + TypeScript + Vite |
| Processing | Python 3.11+ subprocess |
| Database | SQLite via better-sqlite3 |
| Vista 3D | Potree + Three.js |
| Vista 2D | OpenLayers |
| IPC | JSON Lines (stdout) |

## Prerequisiti

- Windows 10/11 64-bit
- Node.js ≥ 20
- Python 3.11+
- NVIDIA GPU (opzionale, per classificazione VLM)

## Setup

```bash
# Installa dipendenze Node
npm install

# Installa dipendenze Python
cd python-engine && pip install -e ".[dev]"

# Avvia in modalità sviluppo (frontend + electron separati)
npm run dev
```

## Struttura Progetto

```
heap-analyzer/
├── electron/          # Electron main process (TypeScript)
├── frontend/          # React app (TypeScript + Vite)
├── python-engine/     # Motore di elaborazione (Python 3.11+)
├── tests/playwright/  # Test visivi automatici
└── docs/              # Specifiche tecniche e piano di sviluppo
```

## Test

```bash
npm run test           # Unit tests (vitest + pytest)
npm run test:visual    # Screenshot tests (Playwright)
npm run lint           # ESLint + ruff
npm run typecheck      # TypeScript + mypy
```

## Licenza

Proprietario — ifly.it
