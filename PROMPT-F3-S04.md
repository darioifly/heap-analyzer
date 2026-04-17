# PROMPT F3.S04 — Vista 3D Potree con @pnext/three-loader

## CONTEXT

You are working on **Heap Analyzer**, an Electron + React + Python desktop app for volumetric analysis of LiDAR point cloud heaps in steelworks. The project is at `C:\Users\iflys\projects\Heap Analyzer`.

**Completed**: F0–F2 (full pipeline + 2D UI), F3.S01 (polygon editing), F3.S02 (base elevation override), F3.S03 (PotreeConverter integration).  
**Current task**: F3.S04 — 3D point cloud viewer using `@pnext/three-loader` + Three.js in React.  
**Prerequisite**: F3.S03 must be complete. Potree files served at `http://127.0.0.1:3001/potree/{surveyId}/metadata.json`.

## AUTHORITATIVE REFERENCES

- `docs/SPEC.md` — Section [UI] Vista 3D (Potree): 3 color modes, navigation, base plane, point budget 2M, >30 FPS.
- `docs/DEV-PLAN.md` — F3.S04 task definition.
- `docs/UX.md` — EVLOS design system (dark mode, evlos colors, Space Grotesk font).
- `CLAUDE.md` — Persistent rules.

## CRITICAL RULES (apply ALWAYS)

1. **IPC Protocol**: Python stdout = ONLY JSON Lines. ZERO exceptions.
2. **TypeScript**: strict mode, explicit interfaces, ZERO `any` types.
3. **UI language**: Italian. Code language: English. Comments: English.
4. **Git**: commit format `F3.S04: {description}`. Tests MUST pass before commit.
5. **DO NOT** run `npm run dev` — already running in hot-reload.
6. **MCP**: Context7 MANDATORY before writing code with @pnext/three-loader, Three.js, or Potree.

## EXISTING CODEBASE CONTEXT

### uiStore (frontend/src/stores/uiStore.ts)
```typescript
// Already has:
viewMode: "2d" | "3d"   // default "2d"
setViewMode: (mode: "2d" | "3d") => void
```

### HeaderBar (frontend/src/components/layout/HeaderBar.tsx)
Currently has: logo left, project name center, export + theme toggle + settings right.
**No 2D/3D toggle exists yet** — must be added.

### Viewport (frontend/src/components/layout/Viewport.tsx or MainLayout.tsx)
The central viewport renders `<MapView>` when viewMode === "2d".
Must conditionally render `<PotreeView>` when viewMode === "3d".

### Express Tile Server (port 3001)
Routes already serving (from F3.S03):
- `/potree/:surveyId/*` — static Potree files
- `http://127.0.0.1:3001/potree/{surveyId}/metadata.json`

### Survey Interface
```typescript
interface Survey {
  // ... all existing fields ...
  potreePath: string | null;  // Added in F3.S03
}
```

### Preload API (window.api)
```typescript
api.potree.getStatus({ surveyId })  // → { available: boolean, potreePath?, metadata? }
api.tiles.getBaseUrl()               // → "http://127.0.0.1:3001"
```

### HeapStore
```typescript
useHeapStore: { heaps: Heap[], selectedHeapId: number | null }
```

### Heap interface (relevant fields for 3D coloring)
```typescript
interface Heap {
  id: number;
  polygon: Polygon;  // GeoJSON
  baseElevation: number;
  maxHeight: number;
  meanHeight: number;
  materialCategory: string | null;
  centroidE: number;
  centroidN: number;
}
```

### Design System (EVLOS)
- Dark mode default: `bg-evlos-900` (#101824), cards `bg-evlos-800` (#1D283C)
- Primary: `evlos-400` (#6575A0) in dark mode
- Border: `border-border` (#3B4967 dark)
- Font: Space Grotesk
- Icons: lucide-react, 20px, stroke-width 1.75
- Border radius: 0.5rem

---

## STEP 1 — Install Dependencies

### Objective
Install `@pnext/three-loader` and `three` (+ types) in the frontend workspace.

### Context7 Query (MANDATORY)
Look up `@pnext/three-loader` — installation, PointCloudOctree loading, API usage with Three.js.

### Implementation

```bash
cd frontend && npm install @pnext/three-loader three && npm install -D @types/three
```

Verify in `frontend/package.json` that both are listed.

### 🏆 Best Practice
Use `@pnext/three-loader` (NOT the legacy Potree viewer) — it's npm-native, works with standard Three.js Scene/Renderer, and integrates cleanly with React lifecycle.

---

## STEP 2 — PotreeView Component

### Objective
Create `frontend/src/components/three/PotreeView.tsx` — main 3D viewer component.

### 🏆 Best Practices
- Own canvas/renderer lifecycle: mount → init Three.js + load point cloud → animate → cleanup on unmount.
- ResizeObserver for responsive canvas sizing.
- Point budget 2M default (configurable).
- Dispose all GPU resources on unmount to prevent memory leaks.

### Implementation

Create `frontend/src/components/three/PotreeView.tsx`:

```typescript
/**
 * 3D point cloud viewer using @pnext/three-loader + Three.js.
 * Loads Potree 2.0 octree data served by the local Express tile server.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import * as THREE from 'three';
import { PointCloudOctree, Potree } from '@pnext/three-loader';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';

// Store imports
import { useHeapStore } from '../../stores/heapStore';
import { useSurveyStore } from '../../stores/surveyStore';

// Types
type ColorMode = 'rgb' | 'height' | 'heap';

interface PotreeViewProps {
  surveyId: number;
}

const POINT_BUDGET = 2_000_000;
const DEFAULT_POINT_SIZE = 1.5;

export function PotreeView({ surveyId }: PotreeViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const potreeRef = useRef<Potree | null>(null);
  const pointCloudRef = useRef<PointCloudOctree | null>(null);
  const animationFrameRef = useRef<number>(0);
  const basePlaneRef = useRef<THREE.Mesh | null>(null);

  const [colorMode, setColorMode] = useState<ColorMode>('rgb');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pointCount, setPointCount] = useState(0);

  const heaps = useHeapStore((s) => s.heaps);
  const selectedHeapId = useHeapStore((s) => s.selectedHeapId);

  // Initialize Three.js scene
  const initScene = useCallback(() => {
    if (!containerRef.current) return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = container.clientHeight;

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setClearColor(0x101824); // evlos-900
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Scene
    const scene = new THREE.Scene();
    sceneRef.current = scene;

    // Camera
    const camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 10000);
    camera.position.set(0, 0, 200);
    cameraRef.current = camera;

    // Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.1;
    controls.screenSpacePanning = true;
    controlsRef.current = controls;

    // Ambient light
    scene.add(new THREE.AmbientLight(0xffffff, 0.8));

    // Potree
    potreeRef.current = new Potree();
    potreeRef.current.pointBudget = POINT_BUDGET;

    return { renderer, scene, camera, controls };
  }, []);

  // Load point cloud
  const loadPointCloud = useCallback(async () => {
    if (!potreeRef.current || !sceneRef.current || !cameraRef.current || !controlsRef.current) return;

    setIsLoading(true);
    setError(null);

    try {
      const baseUrl = await window.api.tiles.getBaseUrl();
      const metadataUrl = `${baseUrl}/potree/${surveyId}/metadata.json`;

      const pointCloud = await potreeRef.current.loadPointCloud(
        metadataUrl,
        (url: string) => `${baseUrl}/potree/${surveyId}/${url}`,
      );

      sceneRef.current.add(pointCloud);
      pointCloudRef.current = pointCloud;

      // Set point appearance
      pointCloud.material.size = DEFAULT_POINT_SIZE;
      pointCloud.material.pointSizeType = 1; // adaptive

      // Fit camera to point cloud bounds
      const bbox = pointCloud.boundingBox;
      if (bbox) {
        const center = new THREE.Vector3();
        bbox.getCenter(center);
        const size = new THREE.Vector3();
        bbox.getSize(size);
        const maxDim = Math.max(size.x, size.y, size.z);

        cameraRef.current.position.set(
          center.x,
          center.y - maxDim * 0.8,
          center.z + maxDim * 0.6,
        );
        controlsRef.current.target.copy(center);
        controlsRef.current.update();

        // Add base plane
        addBasePlane(center, size);
      }

      setIsLoading(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Errore caricamento nuvola di punti');
      setIsLoading(false);
    }
  }, [surveyId]);

  // Add semi-transparent base plane grid
  const addBasePlane = useCallback((center: THREE.Vector3, size: THREE.Vector3) => {
    if (!sceneRef.current) return;

    // Remove old plane
    if (basePlaneRef.current) {
      sceneRef.current.remove(basePlaneRef.current);
      basePlaneRef.current.geometry.dispose();
      (basePlaneRef.current.material as THREE.Material).dispose();
    }

    // Determine base elevation from heaps
    const baseElevation = heaps.length > 0
      ? Math.min(...heaps.map((h) => h.baseElevation))
      : center.z - size.z / 2;

    const planeGeom = new THREE.PlaneGeometry(size.x * 1.5, size.y * 1.5, 20, 20);
    const planeMat = new THREE.MeshBasicMaterial({
      color: 0x6575a0, // evlos-400
      transparent: true,
      opacity: 0.15,
      wireframe: true,
      side: THREE.DoubleSide,
    });
    const plane = new THREE.Mesh(planeGeom, planeMat);
    plane.position.set(center.x, center.y, baseElevation);
    sceneRef.current.add(plane);
    basePlaneRef.current = plane;
  }, [heaps]);

  // Apply color mode to point cloud material
  useEffect(() => {
    if (!pointCloudRef.current) return;
    const material = pointCloudRef.current.material;

    switch (colorMode) {
      case 'rgb':
        // Use original RGB colors from point cloud
        material.pointColorType = 0; // RGB
        break;
      case 'height':
        // Color by elevation (Z) — blue→yellow→red
        material.pointColorType = 3; // Height / classification gradient
        // Configure gradient: you may need to set material.gradient or heightRange
        break;
      case 'heap':
        // Color by heap membership — requires custom attribute or overlay
        // Fallback to RGB if custom coloring not easily supported
        material.pointColorType = 0;
        break;
    }
  }, [colorMode]);

  // Animation loop
  const animate = useCallback(() => {
    animationFrameRef.current = requestAnimationFrame(animate);

    if (!rendererRef.current || !sceneRef.current || !cameraRef.current || !controlsRef.current || !potreeRef.current) return;

    controlsRef.current.update();
    potreeRef.current.updatePointClouds(
      [pointCloudRef.current].filter(Boolean) as PointCloudOctree[],
      cameraRef.current,
      rendererRef.current,
    );

    // Track visible points for UI
    if (pointCloudRef.current) {
      setPointCount(pointCloudRef.current.numVisiblePoints || 0);
    }

    rendererRef.current.render(sceneRef.current, cameraRef.current);
  }, []);

  // Handle resize
  useEffect(() => {
    if (!containerRef.current) return;

    const observer = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      if (rendererRef.current && cameraRef.current) {
        rendererRef.current.setSize(width, height);
        cameraRef.current.aspect = width / height;
        cameraRef.current.updateProjectionMatrix();
      }
    });

    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // Init + load + animate lifecycle
  useEffect(() => {
    initScene();
    loadPointCloud();
    animate();

    return () => {
      // Cleanup
      cancelAnimationFrame(animationFrameRef.current);
      if (pointCloudRef.current) {
        pointCloudRef.current.dispose();
      }
      if (basePlaneRef.current) {
        basePlaneRef.current.geometry.dispose();
        (basePlaneRef.current.material as THREE.Material).dispose();
      }
      if (rendererRef.current) {
        rendererRef.current.dispose();
        rendererRef.current.domElement.remove();
      }
      if (controlsRef.current) {
        controlsRef.current.dispose();
      }
    };
  }, [initScene, loadPointCloud, animate]);

  // Camera preset handlers
  const setCameraPreset = (preset: 'top' | 'side' | 'reset') => {
    if (!cameraRef.current || !controlsRef.current || !pointCloudRef.current) return;

    const bbox = pointCloudRef.current.boundingBox;
    if (!bbox) return;

    const center = new THREE.Vector3();
    bbox.getCenter(center);
    const size = new THREE.Vector3();
    bbox.getSize(size);
    const maxDim = Math.max(size.x, size.y, size.z);

    switch (preset) {
      case 'top':
        cameraRef.current.position.set(center.x, center.y, center.z + maxDim * 1.2);
        cameraRef.current.up.set(0, 1, 0);
        break;
      case 'side':
        cameraRef.current.position.set(center.x, center.y - maxDim * 1.2, center.z);
        cameraRef.current.up.set(0, 0, 1);
        break;
      case 'reset':
        cameraRef.current.position.set(
          center.x, center.y - maxDim * 0.8, center.z + maxDim * 0.6,
        );
        cameraRef.current.up.set(0, 0, 1);
        break;
    }
    controlsRef.current.target.copy(center);
    controlsRef.current.update();
  };

  return (
    <div className="relative h-full w-full">
      {/* 3D Canvas Container */}
      <div ref={containerRef} className="h-full w-full" />

      {/* Controls Overlay — top-right */}
      <div className="absolute top-4 right-4 flex flex-col gap-2">
        {/* Color Mode Selector */}
        <div className="rounded bg-evlos-800/90 border border-border p-2 flex flex-col gap-1">
          <span className="text-xs text-muted-foreground font-semibold uppercase tracking-wider mb-1">
            Colorazione
          </span>
          {(['rgb', 'height', 'heap'] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => setColorMode(mode)}
              className={`text-xs px-2 py-1 rounded text-left ${
                colorMode === mode
                  ? 'bg-primary text-primary-foreground'
                  : 'text-foreground hover:bg-evlos-700'
              }`}
            >
              {mode === 'rgb' ? 'RGB originale' : mode === 'height' ? 'Altezza nDSM' : 'Cumulo'}
            </button>
          ))}
        </div>

        {/* Camera Presets */}
        <div className="rounded bg-evlos-800/90 border border-border p-2 flex flex-col gap-1">
          <span className="text-xs text-muted-foreground font-semibold uppercase tracking-wider mb-1">
            Vista
          </span>
          <button onClick={() => setCameraPreset('top')} className="text-xs px-2 py-1 rounded text-left text-foreground hover:bg-evlos-700">
            Dall'alto
          </button>
          <button onClick={() => setCameraPreset('side')} className="text-xs px-2 py-1 rounded text-left text-foreground hover:bg-evlos-700">
            Laterale
          </button>
          <button onClick={() => setCameraPreset('reset')} className="text-xs px-2 py-1 rounded text-left text-foreground hover:bg-evlos-700">
            Reset
          </button>
        </div>
      </div>

      {/* Status Bar — bottom-left */}
      <div className="absolute bottom-4 left-4 rounded bg-evlos-800/90 border border-border px-3 py-1.5 text-xs text-muted-foreground font-mono">
        {isLoading ? 'Caricamento nuvola di punti...' : `${pointCount.toLocaleString('it-IT')} punti visualizzati`}
      </div>

      {/* Loading Overlay */}
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-evlos-900/80">
          <div className="text-center">
            <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">Caricamento nuvola di punti...</p>
          </div>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-evlos-900/80">
          <div className="text-center max-w-md">
            <p className="text-danger-400 text-sm mb-2">Errore vista 3D</p>
            <p className="text-muted-foreground text-xs">{error}</p>
          </div>
        </div>
      )}
    </div>
  );
}
```

### 🏆 Important Notes for Implementation
- The exact `@pnext/three-loader` API may differ — **USE Context7** to look up the correct import paths, `Potree` class constructor, `loadPointCloud()` signature, and material property names.
- The `pointColorType` values are illustrative — check actual API for height-based coloring.
- `OrbitControls` import path may vary by Three.js version — check `three/examples/jsm/controls/OrbitControls.js`.

---

## STEP 3 — Potree Unavailable Fallback Component

### Objective
When Potree data is not available (PotreeConverter wasn't installed, or conversion wasn't run), show a graceful message instead of crashing.

### Implementation

Create `frontend/src/components/three/PotreeUnavailable.tsx`:

```typescript
import { Box } from 'lucide-react'; // or Cuboid icon

interface PotreeUnavailableProps {
  reason: string;
}

export function PotreeUnavailable({ reason }: PotreeUnavailableProps) {
  return (
    <div className="h-full w-full flex items-center justify-center bg-evlos-900">
      <div className="text-center max-w-md">
        <Box className="h-12 w-12 text-muted-foreground mx-auto mb-4" strokeWidth={1.5} />
        <h3 className="text-lg font-medium text-foreground mb-2">
          Vista 3D non disponibile
        </h3>
        <p className="text-sm text-muted-foreground mb-4">{reason}</p>
        <p className="text-xs text-muted-foreground">
          Per abilitare la vista 3D, assicurati che PotreeConverter sia installato
          nella cartella tools/PotreeConverter/ e che la conversione sia stata eseguita.
        </p>
      </div>
    </div>
  );
}
```

---

## STEP 4 — 2D/3D Toggle in HeaderBar

### Objective
Add a toggle button in the HeaderBar to switch between 2D map view and 3D Potree view.

### 🏆 Best Practice
- Only enable 3D toggle when Potree data is available for the selected survey.
- Use clear icons: `Map` (2D) and `Box` (3D) from lucide-react.
- Follow EVLOS design: header items are always white text on evlos-700/800 background.

### Implementation

In `frontend/src/components/layout/HeaderBar.tsx`, add:

```typescript
import { Map, Box } from 'lucide-react';
import { useUiStore } from '../../stores/uiStore';

// Inside HeaderBar component:
const viewMode = useUiStore((s) => s.viewMode);
const setViewMode = useUiStore((s) => s.setViewMode);
const [potreeAvailable, setPotreeAvailable] = useState(false);

// Check Potree availability when survey changes
useEffect(() => {
  if (!selectedSurveyId) {
    setPotreeAvailable(false);
    return;
  }
  window.api.potree.getStatus({ surveyId: selectedSurveyId })
    .then((status) => setPotreeAvailable(status.available))
    .catch(() => setPotreeAvailable(false));
}, [selectedSurveyId]);

// In the JSX, add toggle button group (right section, before theme toggle):
<div className="flex items-center bg-evlos-600/50 rounded p-0.5">
  <button
    onClick={() => setViewMode('2d')}
    className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors ${
      viewMode === '2d'
        ? 'bg-white/20 text-white'
        : 'text-white/60 hover:text-white/80'
    }`}
  >
    <Map size={14} strokeWidth={1.75} />
    2D
  </button>
  <button
    onClick={() => potreeAvailable && setViewMode('3d')}
    disabled={!potreeAvailable}
    className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors ${
      viewMode === '3d'
        ? 'bg-white/20 text-white'
        : potreeAvailable
          ? 'text-white/60 hover:text-white/80'
          : 'text-white/30 cursor-not-allowed'
    }`}
    title={potreeAvailable ? 'Vista 3D' : 'Vista 3D non disponibile — conversione Potree necessaria'}
  >
    <Box size={14} strokeWidth={1.75} />
    3D
  </button>
</div>
```

---

## STEP 5 — Viewport Conditional Rendering

### Objective
The central Viewport area must render `<MapView>` in 2D mode and `<PotreeView>` (or `<PotreeUnavailable>`) in 3D mode.

### Implementation

In the component that renders the viewport (likely `frontend/src/components/layout/MainLayout.tsx` or `Viewport.tsx`):

```typescript
import { useUiStore } from '../../stores/uiStore';
import { MapView } from '../map/MapView';
import { PotreeView } from '../three/PotreeView';
import { PotreeUnavailable } from '../three/PotreeUnavailable';

// Inside component:
const viewMode = useUiStore((s) => s.viewMode);

// In render:
{viewMode === '2d' ? (
  <MapView surveyId={selectedSurveyId} />
) : (
  potreeAvailable ? (
    <PotreeView surveyId={selectedSurveyId} />
  ) : (
    <PotreeUnavailable reason="Conversione Potree non eseguita per questo rilievo." />
  )
)}
```

### 🏆 Best Practice
When switching from 3D back to 2D, the MapView should restore its previous state (center, zoom). Consider keeping both mounted but hiding one with CSS `display: none` if the state restoration is complex. However, for memory efficiency, prefer unmount/remount since Potree uses significant GPU memory.

---

## STEP 6 — "Converti per 3D" Button

### Objective
Add a button in the UI (e.g., survey panel or right sidebar) to trigger Potree conversion on demand.

### Implementation

Create a small component or add to the existing survey actions area:

```typescript
// Button to trigger Potree conversion — shows when Potree data not available
<Button
  variant="outline"
  size="sm"
  onClick={async () => {
    setConverting(true);
    try {
      await window.api.potree.convert({ surveyId: selectedSurveyId });
      setPotreeAvailable(true);
      toast.success('Conversione 3D completata');
    } catch (err) {
      toast.error('Errore conversione 3D');
    } finally {
      setConverting(false);
    }
  }}
  disabled={converting}
>
  {converting ? (
    <><Loader2 className="animate-spin mr-1" size={14} /> Conversione...</>
  ) : (
    <><Box size={14} className="mr-1" /> Converti per 3D</>
  )}
</Button>
```

This button should appear:
- In the survey info area (when a survey is selected but has no Potree data)
- OR in the 3D unavailable fallback screen

---

## STEP 7 — Tests

### Objective
Write vitest tests for the new components and integration.

### Implementation

Create `frontend/src/components/three/__tests__/PotreeView.test.tsx`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';

// Note: Testing WebGL components in jsdom is limited.
// Focus on: component mounts without crash, fallback renders correctly.

describe('PotreeUnavailable', () => {
  it('renders unavailable message', () => {
    // Import and render PotreeUnavailable
    // Assert "Vista 3D non disponibile" text present
    // Assert reason text present
  });
});

describe('PotreeView', () => {
  it('renders container div', () => {
    // Mock window.api.tiles.getBaseUrl
    // Mock window.api.potree.getStatus
    // Render PotreeView
    // Assert container exists (WebGL may not work in jsdom)
  });
});
```

Also test the toggle logic:

```typescript
describe('ViewMode Toggle', () => {
  it('uiStore toggles between 2d and 3d', () => {
    const { setViewMode } = useUiStore.getState();
    expect(useUiStore.getState().viewMode).toBe('2d');
    setViewMode('3d');
    expect(useUiStore.getState().viewMode).toBe('3d');
    setViewMode('2d');
    expect(useUiStore.getState().viewMode).toBe('2d');
  });
});
```

### 🏆 Best Practice
WebGL/Three.js components cannot be fully tested in jsdom. Focus on:
1. Component mounting/unmounting without errors
2. Fallback rendering
3. Store state management
4. IPC call correctness (mocked)

Leave visual verification to the manual E2E test below.

---

## STEP 8 — Verify & Commit

### Run ALL tests
```bash
cd "python-engine" && py -3.11 -m pytest -x -v
npm run test
```

### Manual E2E Verification (CRITICAL)

Prerequisite: Have a processed survey with Potree data available (run `export-pointcloud` on the synthetic test data if needed).

a. Open the app. Verify the 2D/3D toggle appears in the HeaderBar.
b. With no survey selected, verify 3D toggle is disabled (grayed out).
c. Select a survey that has been processed. If Potree data exists, 3D toggle should be enabled.
d. If no Potree data: click "Converti per 3D" button. Wait for completion toast.
e. Click "3D" toggle. Verify:
   - Loading spinner appears briefly
   - Point cloud renders in 3D
   - Points have correct RGB colors
   - Background is dark (evlos-900)
f. Test camera controls:
   - Mouse drag: orbit around point cloud
   - Scroll: zoom in/out
   - Click "Dall'alto": top-down view
   - Click "Laterale": side view
   - Click "Reset": back to default perspective
g. Test color modes:
   - Click "RGB originale": original point colors
   - Click "Altezza nDSM": height-based gradient (blue→yellow→red)
   - Click "Cumulo": colored by heap membership
h. Verify base plane: semi-transparent grid visible at base elevation
i. Check bottom-left status: shows point count (e.g., "1.234.567 punti visualizzati")
j. Click "2D" toggle. Verify map view restores correctly.
k. Toggle back to 3D. Verify point cloud reloads.
l. If Potree data is NOT available for a survey:
   - Click 3D toggle (should be disabled) OR
   - Verify "Vista 3D non disponibile" message shown
m. Performance: verify smooth navigation (>30 FPS target). No visible lag on orbit/zoom.

### Commit
```bash
git add -A && git commit -m "F3.S04: 3D Potree viewer with @pnext/three-loader + 2D/3D toggle + camera presets + color modes" && git push origin main
```

---

## REPORT BACK

After completing all steps, report:

1. **npm packages installed**: @pnext/three-loader version, three version
2. **New components**: list all new .tsx files created
3. **HeaderBar changes**: 2D/3D toggle added?
4. **Viewport routing**: conditional rendering works?
5. **Color modes**: which modes work? Any limitations?
6. **Camera presets**: top, side, reset all working?
7. **Base plane**: visible at correct elevation?
8. **Fallback**: PotreeUnavailable renders when no data?
9. **Performance**: estimated FPS during navigation
10. **Test results**: new tests count, all passing?
11. **Total test count**: Python + vitest
12. **Known issues / limitations**

## BEST PRACTICES APPLIED

- 🏆 `@pnext/three-loader` — npm-native Potree integration (no legacy viewer embedding)
- 🏆 Proper Three.js lifecycle management (init → animate → dispose on unmount)
- 🏆 ResizeObserver for responsive canvas
- 🏆 GPU resource cleanup on component unmount (renderer.dispose(), geometry.dispose(), material.dispose())
- 🏆 Point budget 2M — prevents GPU memory exhaustion
- 🏆 Graceful fallback when Potree data unavailable
- 🏆 EVLOS design system colors in 3D scene (evlos-900 background, evlos-400 base plane)
- 🏆 Italian UI labels (Colorazione, Dall'alto, Laterale, Reset)
- 🏆 OrbitControls with damping for smooth navigation
- 🏆 Disabled 3D toggle when data unavailable (tooltip explains why)
- 🏆 Context7 used for @pnext/three-loader API verification
