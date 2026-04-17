# PROMPT F3.S05 — Sezioni Trasversali (Cross Sections)

## CONTEXT

You are working on **Heap Analyzer**, an Electron + React + Python desktop app for volumetric analysis of LiDAR point cloud heaps in steelworks. The project is at `C:\Users\iflys\projects\Heap Analyzer`.

**Completed**: F0–F2, F3.S01 (polygon editing), F3.S02 (base elevation override), F3.S03 (PotreeConverter), F3.S04 (3D Potree viewer).  
**Current task**: F3.S05 — Cross section tool: draw line on 2D map → Python extracts height profile → display in chart.  
**This is the LAST task of F3.**

## AUTHORITATIVE REFERENCES

- `docs/SPEC.md` — Section [UI] Vista 3D: "Sezioni trasversali: linea sulla mappa → profilo altezza (DSM vs DTM) in grafico 2D".
- `docs/DEV-PLAN.md` — F3.S05: "interaction disegno linea su mappa 2D + estrazione profilo Python + grafico (recharts)".
- `docs/UX.md` — EVLOS design system.
- `CLAUDE.md` — Persistent rules.

## CRITICAL RULES (apply ALWAYS)

1. **IPC Protocol**: Python stdout = ONLY JSON Lines (`{"type": "progress|result|error|warning", ...}`). ZERO exceptions.
2. **Python**: type hints everywhere, Google-style docstrings, ruff formatting.
3. **TypeScript**: strict mode, explicit interfaces, ZERO `any` types.
4. **UI language**: Italian. Code language: English. Comments: English.
5. **Git**: commit format `F3.S05: {description}`. Tests MUST pass before commit.
6. **DO NOT** run `npm run dev` — already running in hot-reload.
7. **Python interpreter**: `py -3.11`.
8. **MCP**: Context7 MANDATORY before writing code with OpenLayers interactions or recharts.

## EXISTING CODEBASE CONTEXT

### Python Processing Modules
```
python-engine/src/heap_analyzer/processing/
├── dsm.py              # generate_dsm()
├── dtm.py              # estimate_dtm()
├── segmentation.py     # segment_heaps(), compute_ndsm()
├── volume.py           # compute_heap_metrics(), recompute_single_heap(), recompute_all_heaps()
├── ground_sampling.py  # sample_dsm_in_polygons()
└── polygon_ops.py      # split/merge operations
```

### Survey paths available after processing
```typescript
interface Survey {
  dsmPath: string | null;   // GeoTIFF DSM
  dtmPath: string | null;   // GeoTIFF DTM
  ndsmPath: string | null;  // GeoTIFF nDSM = DSM - DTM
  // ...
}
```

### MapView tools integration pattern (from F3.S01/S02)
Tools are integrated in `MapView.tsx` via the `editingStore`:
```typescript
// editingStore has:
activeTool: 'select' | 'draw' | 'modify' | 'split' | 'merge' | 'delete' | 'ground-select'
// Each tool is a separate component that renders OL interactions conditionally
```

### Editing Toolbar (frontend/src/components/map/EditingToolbar.tsx)
Currently has buttons for: Seleziona, Disegna, Modifica, Dividi, Unisci, Elimina, plus undo/redo.
The cross-section tool button must be added here.

### Preload API (window.api)
```typescript
api.python.execute(command, args)  // Execute Python CLI command → JSON Lines result
api.python.onProgress(callback)    // Listen to progress events
api.tiles.getBaseUrl()             // "http://127.0.0.1:3001"
```

### Express Server (port 3001)
- DSM/DTM GeoTIFF files are on the local filesystem (paths stored in survey record).
- Python can access them directly by path — no need to go through Express.

### Design System Highlights
- Card: `bg-card border border-border shadow-sm rounded`
- Muted text: `text-muted-foreground`
- Header table: `text-xs font-semibold uppercase tracking-wider`
- Primary button: `bg-primary text-primary-foreground`
- Font mono: `font-mono` (JetBrains Mono) — use for coordinates/numbers
- Icons: lucide-react, 20px default, strokeWidth 1.75

---

## STEP 1 — Python: cross_section.py

### Objective
Create `python-engine/src/heap_analyzer/processing/cross_section.py` that extracts elevation profiles from DSM and DTM along a line.

### 🏆 Best Practices
- Sample at sub-pixel resolution for smooth profiles (step = raster resolution / 2).
- Use rasterio windowed reading for efficiency.
- Return both DSM and DTM profiles so the chart can show both + the fill between them = volume.
- Include distance-along-line as X axis (in meters).
- Handle edge cases: line outside raster bounds, NaN/nodata pixels.

### Implementation

Create `python-engine/src/heap_analyzer/processing/cross_section.py`:

```python
"""Cross-section profile extraction from DSM/DTM rasters."""

from __future__ import annotations

import numpy as np
import rasterio
from pydantic import BaseModel


class CrossSectionPoint(BaseModel):
    """Single point along the cross-section profile."""
    distance_m: float         # Distance from line start (meters)
    easting: float            # UTM easting
    northing: float           # UTM northing
    dsm_elevation: float | None   # DSM Z (None if nodata)
    dtm_elevation: float | None   # DTM Z (None if nodata)
    ndsm_height: float | None     # nDSM = DSM - DTM (None if either nodata)


class CrossSectionResult(BaseModel):
    """Complete cross-section profile."""
    points: list[CrossSectionPoint]
    line_length_m: float
    num_samples: int
    max_dsm: float
    min_dsm: float
    max_ndsm: float
    volume_under_section_m2: float  # Area between DSM and DTM curves (2D cross-section area)


def extract_cross_section(
    dsm_path: str,
    dtm_path: str,
    line_coords: list[tuple[float, float]],
    num_samples: int | None = None,
) -> CrossSectionResult:
    """Extract elevation profile along a line from DSM and DTM rasters.

    Args:
        dsm_path: Path to DSM GeoTIFF.
        dtm_path: Path to DTM GeoTIFF.
        line_coords: List of (easting, northing) coordinate pairs defining the line.
            Minimum 2 points. Can be a polyline with multiple segments.
        num_samples: Number of sample points. If None, auto-calculated
            from line length and raster resolution (2x oversampling).

    Returns:
        CrossSectionResult with elevation profiles.
    """
    # Compute total line length and parametric positions
    segments = []
    total_length = 0.0
    for i in range(len(line_coords) - 1):
        x0, y0 = line_coords[i]
        x1, y1 = line_coords[i + 1]
        seg_len = np.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2)
        segments.append((x0, y0, x1, y1, seg_len))
        total_length += seg_len

    if total_length == 0:
        return CrossSectionResult(
            points=[], line_length_m=0, num_samples=0,
            max_dsm=0, min_dsm=0, max_ndsm=0, volume_under_section_m2=0,
        )

    # Determine sample count from raster resolution
    with rasterio.open(dsm_path) as dsm_ds:
        pixel_size = abs(dsm_ds.res[0])  # meters per pixel

    if num_samples is None:
        # 2x oversampling relative to pixel size
        num_samples = max(int(total_length / (pixel_size / 2)), 10)

    # Generate sample points along the line
    sample_distances = np.linspace(0, total_length, num_samples)
    sample_coords: list[tuple[float, float, float]] = []  # (e, n, dist)

    seg_idx = 0
    seg_start_dist = 0.0
    for dist in sample_distances:
        # Find which segment this distance falls in
        while seg_idx < len(segments) - 1:
            seg_end_dist = seg_start_dist + segments[seg_idx][4]
            if dist <= seg_end_dist:
                break
            seg_start_dist = seg_end_dist
            seg_idx += 1

        x0, y0, x1, y1, seg_len = segments[seg_idx]
        if seg_len > 0:
            t = (dist - seg_start_dist) / seg_len
            t = max(0.0, min(1.0, t))
        else:
            t = 0.0

        e = x0 + t * (x1 - x0)
        n = y0 + t * (y1 - y0)
        sample_coords.append((e, n, float(dist)))

    # Sample DSM and DTM values
    eastings = [c[0] for c in sample_coords]
    northings = [c[1] for c in sample_coords]

    dsm_values = _sample_raster(dsm_path, eastings, northings)
    dtm_values = _sample_raster(dtm_path, eastings, northings)

    # Build result points
    points: list[CrossSectionPoint] = []
    valid_dsm = []
    valid_ndsm = []

    for i, (e, n, dist) in enumerate(sample_coords):
        dsm_z = dsm_values[i] if not np.isnan(dsm_values[i]) else None
        dtm_z = dtm_values[i] if not np.isnan(dtm_values[i]) else None
        ndsm_z = (dsm_z - dtm_z) if (dsm_z is not None and dtm_z is not None) else None

        points.append(CrossSectionPoint(
            distance_m=round(dist, 3),
            easting=round(e, 3),
            northing=round(n, 3),
            dsm_elevation=round(dsm_z, 3) if dsm_z is not None else None,
            dtm_elevation=round(dtm_z, 3) if dtm_z is not None else None,
            ndsm_height=round(ndsm_z, 3) if ndsm_z is not None else None,
        ))

        if dsm_z is not None:
            valid_dsm.append(dsm_z)
        if ndsm_z is not None:
            valid_ndsm.append(ndsm_z)

    # Compute cross-section area (trapezoidal integration of nDSM along distance)
    volume_2d = 0.0
    for i in range(len(points) - 1):
        h0 = points[i].ndsm_height
        h1 = points[i + 1].ndsm_height
        if h0 is not None and h1 is not None and h0 > 0 and h1 > 0:
            dx = points[i + 1].distance_m - points[i].distance_m
            volume_2d += (h0 + h1) / 2.0 * dx

    return CrossSectionResult(
        points=points,
        line_length_m=round(total_length, 3),
        num_samples=num_samples,
        max_dsm=round(max(valid_dsm), 3) if valid_dsm else 0,
        min_dsm=round(min(valid_dsm), 3) if valid_dsm else 0,
        max_ndsm=round(max(valid_ndsm), 3) if valid_ndsm else 0,
        volume_under_section_m2=round(volume_2d, 3),
    )


def _sample_raster(raster_path: str, eastings: list[float], northings: list[float]) -> np.ndarray:
    """Sample raster values at given coordinates.

    Args:
        raster_path: Path to GeoTIFF.
        eastings: List of easting coordinates.
        northings: List of northing coordinates.

    Returns:
        Array of sampled values. NaN for nodata or out-of-bounds.
    """
    values = np.full(len(eastings), np.nan)

    with rasterio.open(raster_path) as ds:
        nodata = ds.nodata
        for i, (e, n) in enumerate(zip(eastings, northings)):
            try:
                row, col = ds.index(e, n)
                if 0 <= row < ds.height and 0 <= col < ds.width:
                    val = ds.read(1, window=rasterio.windows.Window(col, row, 1, 1))[0, 0]
                    if nodata is not None and val == nodata:
                        continue
                    values[i] = float(val)
            except (IndexError, ValueError):
                continue

    return values
```

### 🏆 Performance Note
The `_sample_raster` function reads one pixel at a time — acceptable for profiles (typically 200-2000 points). For much longer lines, consider reading a windowed strip and interpolating. But for typical heap cross-sections (50-300m), this is fine.

---

## STEP 2 — CLI Command: cross-section

### Objective
Add `cross-section` Click command to `cli.py`.

### Implementation

In `python-engine/src/heap_analyzer/cli.py`:

```python
@main.command("cross-section")
@click.option("--dsm", required=True, type=click.Path(exists=True), help="DSM GeoTIFF path")
@click.option("--dtm", required=True, type=click.Path(exists=True), help="DTM GeoTIFF path")
@click.option("--line", "line_json", required=True, type=str,
              help="Line coordinates as JSON: [[e1,n1],[e2,n2],...]")
@click.option("--num-samples", default=None, type=int, help="Number of sample points (auto if not set)")
def cross_section_cmd(dsm: str, dtm: str, line_json: str, num_samples: int | None) -> None:
    """Extract cross-section elevation profile along a line."""
    import json as json_mod
    from heap_analyzer.processing.cross_section import extract_cross_section

    line_coords = json_mod.loads(line_json)
    # Convert to list of tuples
    coords = [(pt[0], pt[1]) for pt in line_coords]

    _emit({"type": "progress", "phase": "cross_section", "percent": 0, "message": "Calcolo sezione..."})

    result = extract_cross_section(
        dsm_path=dsm,
        dtm_path=dtm,
        line_coords=coords,
        num_samples=num_samples,
    )

    _emit({
        "type": "result",
        "data": {
            "points": [p.model_dump() for p in result.points],
            "line_length_m": result.line_length_m,
            "num_samples": result.num_samples,
            "max_dsm": result.max_dsm,
            "min_dsm": result.min_dsm,
            "max_ndsm": result.max_ndsm,
            "volume_under_section_m2": result.volume_under_section_m2,
        },
    })
```

---

## STEP 3 — Electron IPC Handler

### Objective
Add IPC handler for cross-section extraction.

### Implementation

In `electron/src/ipc/handlers.ts` (or a new `cross-section-handlers.ts`):

```typescript
ipcMain.handle('crossSection:extract', async (
  _event,
  { surveyId, lineCoords }: { surveyId: number; lineCoords: number[][] },
) => {
  const survey = dbService.getSurvey(surveyId);
  if (!survey) throw new Error(`Survey ${surveyId} not found`);
  if (!survey.dsm_path || !survey.dtm_path) {
    throw new Error('Survey has no DSM/DTM data — run processing first');
  }

  const result = await executePython('cross-section', [
    '--dsm', survey.dsm_path,
    '--dtm', survey.dtm_path,
    '--line', JSON.stringify(lineCoords),
  ]);

  return result.data;
});
```

Add to `preload.ts`:
```typescript
crossSection: {
  extract: (params: { surveyId: number; lineCoords: number[][] }) =>
    ipcRenderer.invoke('crossSection:extract', params),
},
```

---

## STEP 4 — Install Recharts

### Objective
Install recharts for the cross-section chart.

### Implementation

```bash
cd frontend && npm install recharts
```

### Context7 Query (MANDATORY)
Look up recharts AreaChart, XAxis, YAxis, Tooltip, ResponsiveContainer — API and customization.

---

## STEP 5 — CrossSectionChart Component

### Objective
Create a floating panel with a recharts AreaChart showing DSM + DTM elevation profiles vs distance.

### 🏆 Best Practices
- AreaChart with two areas: DSM (solid fill, top) and DTM (dashed line, bottom).
- The fill BETWEEN DSM and DTM represents the heap material = cross-section volume area.
- Color: DSM area fill = evlos-400 with opacity, DTM line = muted-foreground.
- Axes: X = distance (m), Y = elevation (m s.l.m.).
- Tooltip: show DSM, DTM, nDSM at cursor position.
- Responsive: adapts to panel width.
- Closeable panel with minimize option.
- Display summary metrics: line length, max nDSM height, cross-section area.

### Implementation

Create `frontend/src/components/charts/CrossSectionChart.tsx`:

```typescript
/**
 * Cross-section elevation profile chart.
 * Shows DSM and DTM profiles along a line, with fill for heap material.
 */

import { X, Minimize2, Maximize2 } from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts';

interface CrossSectionPoint {
  distance_m: number;
  dsm_elevation: number | null;
  dtm_elevation: number | null;
  ndsm_height: number | null;
  easting: number;
  northing: number;
}

interface CrossSectionData {
  points: CrossSectionPoint[];
  line_length_m: number;
  num_samples: number;
  max_dsm: number;
  min_dsm: number;
  max_ndsm: number;
  volume_under_section_m2: number;
}

interface CrossSectionChartProps {
  data: CrossSectionData;
  onClose: () => void;
}

export function CrossSectionChart({ data, onClose }: CrossSectionChartProps) {
  const [minimized, setMinimized] = useState(false);

  // Prepare chart data — filter out null values for display
  const chartData = data.points.map((p) => ({
    distance: p.distance_m,
    dsm: p.dsm_elevation,
    dtm: p.dtm_elevation,
    ndsm: p.ndsm_height,
    easting: p.easting,
    northing: p.northing,
  }));

  return (
    <div className="absolute bottom-4 left-4 right-4 z-50 rounded bg-card border border-border shadow-lg">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border">
        <h3 className="text-sm font-semibold text-foreground">
          Sezione trasversale
        </h3>
        <div className="flex items-center gap-3">
          {/* Summary metrics */}
          <span className="text-xs text-muted-foreground font-mono">
            L: {data.line_length_m.toFixed(1)} m
          </span>
          <span className="text-xs text-muted-foreground font-mono">
            H max: {data.max_ndsm.toFixed(2)} m
          </span>
          <span className="text-xs text-muted-foreground font-mono">
            A: {data.volume_under_section_m2.toFixed(1)} m²
          </span>

          {/* Controls */}
          <button onClick={() => setMinimized(!minimized)} className="text-muted-foreground hover:text-foreground">
            {minimized ? <Maximize2 size={14} /> : <Minimize2 size={14} />}
          </button>
          <button onClick={onClose} className="text-muted-foreground hover:text-danger-400">
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Chart */}
      {!minimized && (
        <div className="px-4 py-3" style={{ height: 220 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis
                dataKey="distance"
                tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }}
                tickFormatter={(v: number) => `${v.toFixed(0)} m`}
                label={{
                  value: 'Distanza (m)',
                  position: 'insideBottom',
                  offset: -2,
                  style: { fontSize: 10, fill: 'var(--muted-foreground)' },
                }}
              />
              <YAxis
                tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }}
                tickFormatter={(v: number) => `${v.toFixed(1)}`}
                label={{
                  value: 'Quota (m)',
                  angle: -90,
                  position: 'insideLeft',
                  style: { fontSize: 10, fill: 'var(--muted-foreground)' },
                }}
                domain={['auto', 'auto']}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--card))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '0.5rem',
                  fontSize: 11,
                }}
                formatter={(value: number, name: string) => {
                  const labels: Record<string, string> = {
                    dsm: 'DSM',
                    dtm: 'DTM',
                    ndsm: 'nDSM',
                  };
                  return [value != null ? `${value.toFixed(2)} m` : '—', labels[name] || name];
                }}
                labelFormatter={(dist: number) => `Distanza: ${dist.toFixed(1)} m`}
              />

              {/* DTM area — dashed bottom reference */}
              <Area
                type="monotone"
                dataKey="dtm"
                stroke="#6B7280"
                strokeDasharray="4 4"
                fill="none"
                strokeWidth={1.5}
                dot={false}
                name="dtm"
              />

              {/* DSM area — solid with fill */}
              <Area
                type="monotone"
                dataKey="dsm"
                stroke="#6575A0"
                fill="#6575A0"
                fillOpacity={0.3}
                strokeWidth={2}
                dot={false}
                name="dsm"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
```

### 🏆 Design Notes
- The chart sits at the bottom of the viewport as a floating overlay (similar to Google Earth cross-section panel).
- Colors match EVLOS: evlos-400 (#6575A0) for DSM, gray for DTM.
- Metrics in the header use `font-mono` for alignment.
- The fill between DSM and DTM curves visually represents the heap cross-section area.

---

## STEP 6 — CrossSectionTool Component (OL Interaction)

### Objective
Create `frontend/src/components/map/CrossSectionTool.tsx` — an OpenLayers Draw interaction for drawing a line on the 2D map.

### Context7 Query (MANDATORY)
Look up OpenLayers `ol/interaction/Draw` with `type: 'LineString'`, draw events, getting coordinates from features.

### 🏆 Best Practice
- Draw mode: LineString (2 points = single line segment).
- After the user finishes drawing (drawend event), extract coordinates, call Python via IPC, show chart.
- Visual: line rendered in bright color (evlos-400 or danger-400) with circles at endpoints.
- The drawn line should remain visible on the map while the chart is open.

### Implementation

Create `frontend/src/components/map/CrossSectionTool.tsx`:

```typescript
/**
 * Cross-section line drawing tool.
 * Draws a line on the map, extracts profile via Python, opens CrossSectionChart.
 */

import { useEffect, useRef, useState } from 'react';
import { Draw } from 'ol/interaction';
import VectorSource from 'ol/source/Vector';
import VectorLayer from 'ol/layer/Vector';
import { Style, Stroke, Circle, Fill } from 'ol/style';
import type OlMap from 'ol/Map';
import type { DrawEvent } from 'ol/interaction/Draw';

import { CrossSectionChart } from '../charts/CrossSectionChart';
import { useEditingStore } from '../../stores/editingStore';
import { useSurveyStore } from '../../stores/surveyStore';

interface CrossSectionToolProps {
  map: OlMap | null;
}

// Line style: bright evlos-400 with endpoint circles
const lineStyle = new Style({
  stroke: new Stroke({ color: '#6575A0', width: 3 }),
  image: new Circle({
    radius: 5,
    fill: new Fill({ color: '#6575A0' }),
    stroke: new Stroke({ color: '#ffffff', width: 2 }),
  }),
});

export function CrossSectionTool({ map }: CrossSectionToolProps) {
  const activeTool = useEditingStore((s) => s.activeTool);
  const selectedSurveyId = useSurveyStore((s) => s.selectedSurveyId);

  const [chartData, setChartData] = useState<CrossSectionData | null>(null);
  const [isExtracting, setIsExtracting] = useState(false);

  const sourceRef = useRef(new VectorSource());
  const layerRef = useRef<VectorLayer | null>(null);
  const drawRef = useRef<Draw | null>(null);

  // Add vector layer for the cross-section line
  useEffect(() => {
    if (!map) return;

    const layer = new VectorLayer({
      source: sourceRef.current,
      style: lineStyle,
      zIndex: 100,
    });
    map.addLayer(layer);
    layerRef.current = layer;

    return () => {
      map.removeLayer(layer);
    };
  }, [map]);

  // Activate/deactivate draw interaction
  useEffect(() => {
    if (!map) return;

    const isActive = activeTool === 'cross-section';

    if (isActive) {
      // Clear previous line
      sourceRef.current.clear();
      setChartData(null);

      const draw = new Draw({
        source: sourceRef.current,
        type: 'LineString',
        maxPoints: 2, // Simple line segment (2 clicks)
        style: lineStyle,
      });

      draw.on('drawend', async (event: DrawEvent) => {
        const coords = event.feature.getGeometry()?.getCoordinates();
        if (!coords || coords.length < 2 || !selectedSurveyId) return;

        // coords are in map projection (UTM) = [[e1,n1], [e2,n2]]
        setIsExtracting(true);
        try {
          const result = await window.api.crossSection.extract({
            surveyId: selectedSurveyId,
            lineCoords: coords as number[][],
          });
          setChartData(result);
        } catch (err) {
          console.error('Cross-section extraction failed:', err);
          // Show toast error
        } finally {
          setIsExtracting(false);
        }
      });

      map.addInteraction(draw);
      drawRef.current = draw;
    }

    return () => {
      if (drawRef.current) {
        map.removeInteraction(drawRef.current);
        drawRef.current = null;
      }
    };
  }, [map, activeTool, selectedSurveyId]);

  // Handle chart close
  const handleCloseChart = () => {
    setChartData(null);
    sourceRef.current.clear();
  };

  return (
    <>
      {/* Loading indicator */}
      {isExtracting && (
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 rounded bg-card border border-border shadow-lg px-4 py-3 flex items-center gap-2">
          <div className="animate-spin h-4 w-4 border-2 border-primary border-t-transparent rounded-full" />
          <span className="text-sm text-muted-foreground">Calcolo sezione...</span>
        </div>
      )}

      {/* Chart overlay */}
      {chartData && (
        <CrossSectionChart data={chartData} onClose={handleCloseChart} />
      )}
    </>
  );
}
```

---

## STEP 7 — Add Tool to EditingStore + Toolbar

### Objective
Add 'cross-section' as a new tool type in editingStore and add a button to EditingToolbar.

### Implementation

In `frontend/src/stores/editingStore.ts`, update the tool type:
```typescript
type EditingTool = 'select' | 'draw' | 'modify' | 'split' | 'merge' | 'delete' | 'ground-select' | 'cross-section';
```

In `frontend/src/components/map/EditingToolbar.tsx`, add the cross-section button:
```typescript
import { Ruler } from 'lucide-react'; // or ScanLine, ScissorsLineDashed

// Add to the toolbar (after the editing tools, possibly in a separate "analysis" section):
<button
  onClick={() => setActiveTool('cross-section')}
  className={`... ${activeTool === 'cross-section' ? 'bg-primary text-primary-foreground' : '...'}`}
  title="Sezione trasversale (S)"
>
  <Ruler size={18} strokeWidth={1.75} />
</button>
```

Add keyboard shortcut **S** for cross-section in the shortcuts handler:
```typescript
case 'KeyS':
  setActiveTool('cross-section');
  break;
```

---

## STEP 8 — Mount CrossSectionTool in MapView

### Objective
Add `<CrossSectionTool map={map} />` to `MapView.tsx`.

### Implementation

In `frontend/src/components/map/MapView.tsx`:
```typescript
import { CrossSectionTool } from './CrossSectionTool';

// Inside the JSX, alongside other tool components:
<CrossSectionTool map={mapRef.current} />
```

---

## STEP 9 — Optional: 3D Cross-Section Plane

### Objective (OPTIONAL — implement only if time allows)
In the Potree 3D view, show a semi-transparent vertical plane along the cross-section line.

### Implementation Sketch
If PotreeView is mounted and a cross-section is active:
1. Create a Three.js PlaneGeometry oriented vertically along the cross-section line.
2. Material: semi-transparent evlos-400 with `opacity: 0.3`.
3. Add to the Three.js scene when chartData is available.
4. Remove when chart is closed.

This is a nice-to-have. If it adds too much complexity, skip it and note in the report.

---

## STEP 10 — Tests

### Objective
Test Python cross-section extraction + CLI + frontend component.

### Python Tests

Create `python-engine/src/heap_analyzer/tests/test_cross_section.py`:

```python
"""Tests for cross-section profile extraction."""

import json
import math
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds

from heap_analyzer.processing.cross_section import (
    CrossSectionResult,
    extract_cross_section,
)


@pytest.fixture
def synthetic_rasters(tmp_path: Path) -> tuple[str, str]:
    """Create synthetic DSM and DTM rasters for testing.

    Creates a 100x100m area with:
    - DTM: flat at 100.0 m
    - DSM: flat at 100.0 m with a cone heap centered at (50, 50),
      radius 20m, height 5m
    """
    size = 100  # meters
    res = 0.5   # m/pixel
    nx = ny = int(size / res)

    # Coordinates: origin at (500000, 4500000) UTM
    origin_e, origin_n = 500000.0, 4500000.0
    transform = from_bounds(
        origin_e, origin_n, origin_e + size, origin_n + size, nx, ny,
    )

    # DTM: flat
    dtm_data = np.full((ny, nx), 100.0, dtype=np.float32)

    # DSM: flat + cone at center
    dsm_data = np.full((ny, nx), 100.0, dtype=np.float32)
    center_px = nx // 2
    center_py = ny // 2
    cone_radius_px = int(20 / res)
    cone_height = 5.0

    for row in range(ny):
        for col in range(nx):
            dist = math.sqrt((col - center_px) ** 2 + (row - center_py) ** 2)
            if dist < cone_radius_px:
                h = cone_height * (1.0 - dist / cone_radius_px)
                dsm_data[row, col] = 100.0 + h

    profile = {
        'driver': 'GTiff', 'dtype': 'float32', 'width': nx, 'height': ny,
        'count': 1, 'crs': 'EPSG:32632', 'transform': transform,
    }

    dsm_path = str(tmp_path / "dsm.tif")
    dtm_path = str(tmp_path / "dtm.tif")

    with rasterio.open(dsm_path, 'w', **profile) as ds:
        ds.write(dsm_data, 1)
    with rasterio.open(dtm_path, 'w', **profile) as ds:
        ds.write(dtm_data, 1)

    return dsm_path, dtm_path


class TestCrossSection:
    """Tests for cross-section extraction."""

    def test_basic_profile(self, synthetic_rasters: tuple[str, str]) -> None:
        """Extract profile across the cone center — should show peak."""
        dsm_path, dtm_path = synthetic_rasters

        # Line from west to east through center (y=50m from origin)
        line = [
            (500000.0, 4500050.0),  # west edge, center y
            (500100.0, 4500050.0),  # east edge, center y
        ]

        result = extract_cross_section(dsm_path, dtm_path, line)

        assert result.line_length_m == pytest.approx(100.0, abs=0.1)
        assert result.num_samples >= 10
        assert len(result.points) == result.num_samples

        # Max nDSM should be near cone peak (5m)
        assert result.max_ndsm == pytest.approx(5.0, abs=0.5)

        # Points at edges should have nDSM ≈ 0 (flat terrain)
        assert result.points[0].ndsm_height is not None
        assert result.points[0].ndsm_height < 0.5

        # Point near center should have nDSM ≈ 5
        mid_idx = len(result.points) // 2
        assert result.points[mid_idx].ndsm_height is not None
        assert result.points[mid_idx].ndsm_height > 3.0

    def test_cross_section_area_positive(self, synthetic_rasters: tuple[str, str]) -> None:
        """Cross-section area should be positive through the cone."""
        dsm_path, dtm_path = synthetic_rasters
        line = [(500000.0, 4500050.0), (500100.0, 4500050.0)]
        result = extract_cross_section(dsm_path, dtm_path, line)
        assert result.volume_under_section_m2 > 0

    def test_profile_outside_heap(self, synthetic_rasters: tuple[str, str]) -> None:
        """Profile far from the heap should be flat (nDSM ≈ 0)."""
        dsm_path, dtm_path = synthetic_rasters
        # Line at y=10m — far from cone center at y=50m
        line = [(500000.0, 4500010.0), (500100.0, 4500010.0)]
        result = extract_cross_section(dsm_path, dtm_path, line)
        assert result.max_ndsm < 0.5  # no heap here

    def test_zero_length_line(self, synthetic_rasters: tuple[str, str]) -> None:
        """Zero-length line returns empty result."""
        dsm_path, dtm_path = synthetic_rasters
        line = [(500050.0, 4500050.0), (500050.0, 4500050.0)]
        result = extract_cross_section(dsm_path, dtm_path, line)
        assert result.line_length_m == 0
        assert len(result.points) == 0

    def test_num_samples_override(self, synthetic_rasters: tuple[str, str]) -> None:
        """num_samples parameter controls output length."""
        dsm_path, dtm_path = synthetic_rasters
        line = [(500000.0, 4500050.0), (500100.0, 4500050.0)]
        result = extract_cross_section(dsm_path, dtm_path, line, num_samples=50)
        assert result.num_samples == 50
        assert len(result.points) == 50

    def test_all_points_have_coordinates(self, synthetic_rasters: tuple[str, str]) -> None:
        """Every point should have valid easting/northing."""
        dsm_path, dtm_path = synthetic_rasters
        line = [(500000.0, 4500050.0), (500100.0, 4500050.0)]
        result = extract_cross_section(dsm_path, dtm_path, line, num_samples=20)
        for p in result.points:
            assert 500000.0 <= p.easting <= 500100.0
            assert 4500049.0 <= p.northing <= 4500051.0

    def test_dsm_dtm_consistency(self, synthetic_rasters: tuple[str, str]) -> None:
        """nDSM should equal DSM - DTM at every point."""
        dsm_path, dtm_path = synthetic_rasters
        line = [(500000.0, 4500050.0), (500100.0, 4500050.0)]
        result = extract_cross_section(dsm_path, dtm_path, line, num_samples=30)
        for p in result.points:
            if p.dsm_elevation is not None and p.dtm_elevation is not None:
                expected_ndsm = p.dsm_elevation - p.dtm_elevation
                assert p.ndsm_height == pytest.approx(expected_ndsm, abs=0.001)


class TestCLICrossSection:
    """Test CLI cross-section command."""

    def test_cli_emits_json_lines(self, synthetic_rasters: tuple[str, str]) -> None:
        """CLI outputs only valid JSON Lines."""
        import subprocess
        dsm_path, dtm_path = synthetic_rasters
        line = json.dumps([[500020.0, 4500050.0], [500080.0, 4500050.0]])

        result = subprocess.run(
            ["py", "-3.11", "-m", "heap_analyzer.cli", "cross-section",
             "--dsm", dsm_path, "--dtm", dtm_path, "--line", line],
            capture_output=True, text=True,
        )

        for line_str in result.stdout.strip().split("\n"):
            if line_str.strip():
                parsed = json.loads(line_str)
                assert "type" in parsed

    def test_cli_result_has_points(self, synthetic_rasters: tuple[str, str]) -> None:
        """CLI result contains points array."""
        import subprocess
        dsm_path, dtm_path = synthetic_rasters
        line = json.dumps([[500020.0, 4500050.0], [500080.0, 4500050.0]])

        result = subprocess.run(
            ["py", "-3.11", "-m", "heap_analyzer.cli", "cross-section",
             "--dsm", dsm_path, "--dtm", dtm_path, "--line", line],
            capture_output=True, text=True,
        )

        # Find the result line
        for line_str in result.stdout.strip().split("\n"):
            parsed = json.loads(line_str)
            if parsed["type"] == "result":
                assert "points" in parsed["data"]
                assert len(parsed["data"]["points"]) > 0
                break
        else:
            pytest.fail("No result message found in CLI output")
```

### Test Execution
```bash
cd "python-engine" && py -3.11 -m pytest src/heap_analyzer/tests/test_cross_section.py -v
```

---

## STEP 11 — IPC Stdout Hygiene Check

### 🏆 Best Practice (CRITICAL)
```bash
cd "python-engine" && grep -rn "^[^#]*print(" src/heap_analyzer/ --include="*.py" | grep -v "stderr" | grep -v "test_" | grep -v "__pycache__"
```
Any match = BUG. Fix immediately.

---

## STEP 12 — Verify & Commit

### Run ALL tests
```bash
cd "python-engine" && py -3.11 -m pytest -x -v
npm run test
```

### Manual E2E Verification (CRITICAL)

Prerequisite: A processed survey (with DSM and DTM files available).

a. Open the app. Select a processed survey.
b. Verify EditingToolbar shows the cross-section tool button (Ruler icon).
c. Click the cross-section button (or press **S**).
d. On the map, click two points to draw a line across a heap.
e. Verify loading indicator appears: "Calcolo sezione..."
f. Verify the chart panel appears at the bottom of the viewport:
   - X axis: distance in meters
   - Y axis: elevation in meters (m s.l.m.)
   - Blue/evlos line = DSM profile
   - Gray dashed line = DTM profile
   - Shaded area between DSM and DTM = heap cross-section
g. Verify header metrics: L (line length), H max (max nDSM), A (cross-section area in m²).
h. Hover over the chart: tooltip shows DSM, DTM, nDSM values at cursor position.
i. Click minimize (−) icon: chart collapses to header only.
j. Click maximize (+) icon: chart expands again.
k. Click close (×): chart disappears, line removed from map.
l. Draw another line outside any heap: chart should show flat profile (nDSM ≈ 0).
m. Switch to a different tool (e.g., Select): cross-section interaction deactivates.
n. Try drawing a very short line (< 1m): should still work without errors.
o. Try drawing over the edge of the raster: points outside should show null gracefully.

### Commit
```bash
git add -A && git commit -m "F3.S05: cross-section tool with line draw + Python profile extraction + recharts chart panel" && git push origin main
```

---

## REPORT BACK

After completing all steps, report:

1. **New Python module**: `cross_section.py` — functions, lines of code
2. **New CLI command**: `cross-section` — arguments
3. **New IPC channel**: `crossSection:extract`
4. **New frontend components**: list all new .tsx files
5. **Recharts**: version installed, chart features
6. **Toolbar**: cross-section button added? Keyboard shortcut?
7. **Chart features**: minimize, close, tooltip, metrics header?
8. **Test results**: new tests count (Python + vitest), all passing?
9. **Total test count**: Python + vitest (cumulative)
10. **Numerical validation**: max nDSM on synthetic cone matches expected (≈5m)?
11. **3D plane** (optional): implemented or skipped?
12. **IPC hygiene**: any print() found? Fixed?
13. **Known issues / limitations**

## BEST PRACTICES APPLIED

- 🏆 Sub-pixel sampling (2x raster resolution) for smooth profiles
- 🏆 Pydantic models for structured input/output
- 🏆 Trapezoidal integration for cross-section area
- 🏆 Both DSM + DTM profiles shown (not just nDSM) — clearer for the operator
- 🏆 JSON Lines protocol strictly respected
- 🏆 Graceful null handling for nodata/out-of-bounds pixels
- 🏆 Floating chart panel with minimize/close (doesn't block map interaction)
- 🏆 EVLOS design colors in chart (evlos-400 for DSM, gray for DTM)
- 🏆 Keyboard shortcut (S) for quick activation
- 🏆 Recharts responsive chart adapts to panel width
- 🏆 Numerical validation against synthetic cone with known geometry
- 🏆 Context7 used for OpenLayers Draw + Recharts API
