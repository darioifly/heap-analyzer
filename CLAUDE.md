# CLAUDE.md — Heap Analyzer

## Authoritative References
- `docs/SPEC.md` — Technical specs (WINS on conflicts)
- `docs/DEV-PLAN.md` — Development plan (48 tasks)

## Rules (apply ALWAYS)

### IPC Protocol
- Python stdout = ONLY JSON Lines (one line = one JSON object with `"type"` field)
- Python stderr = logs/debug (any format)
- ZERO exceptions. No print(), no logging to stdout. EVER.
- Types: "progress", "result", "error", "warning"

### Code Conventions
- Python: type hints everywhere, Google-style docstrings, ruff formatting
- TypeScript: strict mode, explicit interfaces, ZERO `any` types
- UI language: Italian. Code language (vars, functions, classes): English.
- Comments: English
- Large files: ALWAYS chunked/tiled processing

### Git
- Branch: main only
- Commit format: `F{X}.S{YY}: {short description}`
- Tests MUST pass BEFORE commit
- Always: `git add -A && git commit -m "..." && git push origin main`

### MCP Plugin Usage
- **Context7**: MANDATORY before writing code with laspy, rasterio, scipy.ndimage, shapely 2.x, scikit-image, openlayers, potree, better-sqlite3, electron IPC
- **Sequential Thinking**: MANDATORY for F1.S04, F1.S05, F1.S06, F6.S01. Recommended for algorithms > 3 steps
- **Memory**: Save at END of each task, read at START of each session

### Testing
- pytest (Python), vitest (frontend), Playwright (visual)
- Synthetic datasets = gold standard for validation
- Volume accuracy target: error < 5% vs analytical

### Python Interpreter
- Always use Python 3.11: `C:\Users\iflys\AppData\Local\Programs\Python\Python311\python.exe`
- Or via: `py -3.11`

### Commands
```
npm run dev          # DO NOT RUN — already running in hot-reload
npm run test         # vitest + pytest
npm run test:visual  # Playwright screenshot
npm run lint         # eslint + ruff
cd python-engine && pip install -e .
heap-analyzer process --las X --tiff Y --output Z
heap-analyzer generate-test-data --output ./test-data
```
