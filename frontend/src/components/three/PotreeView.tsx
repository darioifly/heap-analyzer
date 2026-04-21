/**
 * 3D point cloud viewer using potree-core + Three.js.
 *
 * Library: potree-core@2.0.15 — npm-native Potree 2.0 loader.
 * Returns PointCloudOctree (extends Object3D) that drops into a Three.js scene.
 *
 * Z-up convention for UTM geographic data.
 */

import { useEffect, useRef, useState, useCallback } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { Potree, PointCloudOctree, PointColorType, PointSizeType, PointShape } from "potree-core";

import { useUiStore } from "@/stores/uiStore";
import { useHeapStore } from "@/stores/heapStore";
import { useSurveyStore } from "@/stores/surveyStore";
import { useCrossSectionStore } from "@/stores/crossSectionStore";
import { Toolbar3D } from "./Toolbar3D";
import { applyCameraPreset, centerOnHeap, type BoundingBox3D } from "./cameraPresets";
import type { Heap } from "@/types";

// Heap material color palette (same as 2D HeapOverlay)
const CATEGORY_COLORS: Record<string, number> = {
  "Rottame ferroso": 0xb45309,
  Ghisa: 0x6575a0,
  Scorie: 0x6b7280,
  Cascami: 0x92400e,
  RAEE: 0x059669,
};
const HEAP_PALETTE = [0x6575a0, 0xb45309, 0x059669, 0x92400e, 0x6b7280, 0x7c3aed, 0xdc2626, 0x0891b2];

function getHeapColor(heap: Heap, index: number): number {
  if (heap.materialCategory && CATEGORY_COLORS[heap.materialCategory]) {
    return CATEGORY_COLORS[heap.materialCategory];
  }
  return HEAP_PALETTE[index % HEAP_PALETTE.length];
}

interface PotreeViewProps {
  surveyId: number;
}

export function PotreeView({ surveyId }: PotreeViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const potreeRef = useRef<Potree | null>(null);
  const octreeRef = useRef<PointCloudOctree | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const boundsRef = useRef<BoundingBox3D | null>(null);
  const basePlaneRef = useRef<THREE.Mesh | null>(null);
  const heapOverlayGroupRef = useRef<THREE.Group | null>(null);

  const survey = useSurveyStore((s) => s.surveys.find((sv) => sv.id === surveyId));
  const heaps = useHeapStore((s) => s.heaps);
  const selectedHeapId = useHeapStore((s) => s.selectedHeapId);
  const selectHeap = useHeapStore((s) => s.select);

  const selectedSectionId = useCrossSectionStore((s) => s.selectedId);
  const sectionSections = useCrossSectionStore((s) => s.sections);
  const sectionPlaneRef = useRef<THREE.Group | null>(null);

  const colorMode = useUiStore((s) => s.colorMode);
  const showBasePlane = useUiStore((s) => s.showBasePlane);
  const showHeapOverlay3D = useUiStore((s) => s.showHeapOverlay3D);
  const pointBudget = useUiStore((s) => s.pointBudget);
  const cameraPreset = useUiStore((s) => s.cameraPreset);
  const clearCameraPreset = useUiStore((s) => s.clearCameraPreset);
  const centerOnSelectionRequested = useUiStore((s) => s.centerOnSelectionRequested);

  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [visiblePoints, setVisiblePoints] = useState(0);
  // Real UTM Z range parsed from metadata.json → position attribute.
  // pcoGeometry.tightBoundingBox from potree-core is actually the cubic
  // AABB (same 328 m on every axis), so it is useless for a meaningful
  // elevation gradient — we need the actual point-attribute Z min/max.
  const pointZRangeRef = useRef<{ min: number; max: number } | null>(null);

  // ——— 1. Scene setup (runs once per mount) ———
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x101824); // evlos-900

    const aspect = container.clientWidth / container.clientHeight;
    const camera = new THREE.PerspectiveCamera(60, aspect, 0.1, 50000);
    camera.up.set(0, 0, 1); // Z-up for UTM
    camera.position.set(100, -100, 100);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;

    // Lights
    scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const dirLight = new THREE.DirectionalLight(0xffffff, 0.4);
    dirLight.position.set(50, 50, 100);
    scene.add(dirLight);

    const potree = new Potree();

    sceneRef.current = scene;
    cameraRef.current = camera;
    rendererRef.current = renderer;
    controlsRef.current = controls;
    potreeRef.current = potree;

    // Animation loop
    const animate = () => {
      animationFrameRef.current = requestAnimationFrame(animate);
      controls.update();
      if (octreeRef.current && potreeRef.current) {
        potreeRef.current.updatePointClouds([octreeRef.current], camera, renderer);
        setVisiblePoints(octreeRef.current.numVisiblePoints);
      }
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
      controls.dispose();

      // Dispose point cloud
      if (octreeRef.current) {
        octreeRef.current.dispose();
        scene.remove(octreeRef.current);
        octreeRef.current = null;
      }

      // Dispose base plane
      if (basePlaneRef.current) {
        basePlaneRef.current.geometry.dispose();
        (basePlaneRef.current.material as THREE.Material).dispose();
        scene.remove(basePlaneRef.current);
        basePlaneRef.current = null;
      }

      // Dispose heap overlays
      if (heapOverlayGroupRef.current) {
        disposeGroup(heapOverlayGroupRef.current);
        scene.remove(heapOverlayGroupRef.current);
        heapOverlayGroupRef.current = null;
      }

      // Dispose section plane
      if (sectionPlaneRef.current) {
        disposeGroup(sectionPlaneRef.current);
        scene.remove(sectionPlaneRef.current);
        sectionPlaneRef.current = null;
      }

      // Dispose all remaining scene objects
      scene.traverse((obj) => {
        const mesh = obj as THREE.Mesh;
        if (mesh.geometry) mesh.geometry.dispose();
        if (mesh.material) {
          const mat = mesh.material;
          if (Array.isArray(mat)) mat.forEach((m) => m.dispose());
          else mat.dispose();
        }
      });

      renderer.dispose();
      if (renderer.domElement.parentNode === container) {
        container.removeChild(renderer.domElement);
      }
    };
  }, []);

  // ——— 2. Load point cloud when survey changes ———
  useEffect(() => {
    const scene = sceneRef.current;
    const potree = potreeRef.current;
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (!scene || !potree || !camera || !controls) return;

    let cancelled = false;
    setLoadError(null);
    setIsLoading(true);

    // Remove previous octree
    if (octreeRef.current) {
      octreeRef.current.dispose();
      scene.remove(octreeRef.current);
      octreeRef.current = null;
    }

    (async () => {
      try {
        const baseUrl = await window.api.tiles.getBaseUrl();
        const status = await window.api.potree.getStatus({ surveyId });
        if (!status.available) {
          setLoadError("Dati Potree non disponibili per questo rilievo.");
          setIsLoading(false);
          return;
        }

        const metadataUrl = `${baseUrl}/potree/${surveyId}/metadata.json`;
        const potreeBaseUrl = `${baseUrl}/potree/${surveyId}/`;

        // Diagnostic: verify metadata.json is reachable before handing off to
        // potree-core. Without this, a silent fallback (e.g. Vite dev server
        // returning index.html for an unknown path) surfaces as an opaque
        // 'Unexpected token <' JSON parse error from inside potree-core.
        console.log("[PotreeView] baseUrl =", baseUrl);
        console.log("[PotreeView] metadataUrl =", metadataUrl);
        try {
          const probe = await fetch(metadataUrl, { method: "GET" });
          const contentType = probe.headers.get("content-type") ?? "";
          if (!probe.ok) {
            throw new Error(
              `metadata.json HTTP ${probe.status} at ${metadataUrl}`,
            );
          }
          if (!contentType.includes("json") && !contentType.includes("text")) {
            // application/json or application/octet-stream; both readable as JSON.
          }
          const text = await probe.text();
          if (!text.trim().startsWith("{")) {
            throw new Error(
              `metadata.json returned non-JSON content (first 80 chars: ${text.slice(0, 80).replace(/\s+/g, " ")}) — baseUrl=${baseUrl}`,
            );
          }
          // Pull the real point Z range from the position attribute so the
          // elevation color ramp actually spans the points.
          try {
            const meta = JSON.parse(text) as {
              attributes?: Array<{
                name: string;
                min?: number[];
                max?: number[];
              }>;
            };
            const pos = meta.attributes?.find((a) => a.name === "position");
            if (pos?.min && pos?.max && pos.min.length >= 3 && pos.max.length >= 3) {
              pointZRangeRef.current = {
                min: pos.min[2],
                max: pos.max[2],
              };
              console.log(
                "[PotreeView] point Z range (from metadata):",
                pos.min[2], "→", pos.max[2],
              );
            }
          } catch {
            // metadata parse error is non-fatal; elevation mode will fall
            // back to the bounding box.
          }
        } catch (probeErr) {
          throw new Error(
            probeErr instanceof Error ? probeErr.message : String(probeErr),
          );
        }

        if (cancelled) return;

        // potree-core concatenates these as `baseUrl + fileName`, NOT using
        // the first arg as an absolute URL. Passing `metadataUrl` (absolute)
        // as the first arg caused doubled-URL 404s like
        //   GET .../potree/12/http://127.0.0.1:3001/potree/12/metadata.json
        const octree = await potree.loadPointCloud("metadata.json", potreeBaseUrl);

        if (cancelled) {
          octree.dispose();
          return;
        }

        // Configure material
        octree.material.size = 1.5;
        octree.material.pointSizeType = PointSizeType.ADAPTIVE;
        octree.material.shape = PointShape.CIRCLE;
        octree.material.pointColorType = PointColorType.RGB;

        // Bypass potree-core's sRGB/linear conversion — its shader swaps
        // the fromLinear/toLinear conditions so with the default
        // inputColorEncoding=SRGB + outputColorEncoding=LINEAR every rgba
        // channel goes through fromLinear(x) (a linear→sRGB transform)
        // even though the data is ALREADY sRGB. That amplifies mid-tones
        // toward 1.0 and an entire scrap-yard cloud looks chalk white.
        // Setting both encodings to LINEAR (0) skips both #if blocks.
        /* eslint-disable @typescript-eslint/no-explicit-any */
        const matObj = octree.material as unknown as {
          inputColorEncoding?: number;
          outputColorEncoding?: number;
          needsUpdate?: boolean;
        };
        matObj.inputColorEncoding = 0; // ColorEncoding.LINEAR
        matObj.outputColorEncoding = 0; // ColorEncoding.LINEAR
        matObj.needsUpdate = true;
        /* eslint-enable @typescript-eslint/no-explicit-any */

        scene.add(octree);
        octreeRef.current = octree;

        // Diagnostic: log the material state so we can see what shader
        // defines are actually active and whether the rgba attribute wired
        // up. For 16-bit RGB LAS, potree-core's worker normalises to uint8
        // and the shader (with newFormat=true) does `vColor = rgba`. If
        // points render white, either (a) newFormat is false and the
        // attribute name mismatches, or (b) some uniform is pinning the
        // colour.
        /* eslint-disable @typescript-eslint/no-explicit-any */
        const mat = octree.material as unknown as Record<string, unknown>;
        console.log(
          "[PotreeView] material.newFormat:",
          mat.newFormat,
          "pointColorType:",
          mat.pointColorType,
        );
        console.log(
          "[PotreeView] material keys:",
          Object.keys(mat).filter((k) => !k.startsWith("_")).slice(0, 30),
        );
        // Log a couple of nodes' geometry attributes once they load.
        setTimeout(() => {
          const geomNodes = (octree as unknown as { visibleNodes?: Array<{ geometryNode?: { geometry?: { attributes?: Record<string, unknown> } } }> }).visibleNodes ?? [];
          console.log("[PotreeView] visibleNodes.length:", geomNodes.length);
          const first = geomNodes[0]?.geometryNode?.geometry?.attributes ?? {};
          console.log("[PotreeView] first node attribute names:", Object.keys(first));
          const rgba = (first as Record<string, unknown>)["rgba"] as
            | { array?: Uint8Array; itemSize?: number; normalized?: boolean }
            | undefined;
          if (rgba?.array) {
            const a = rgba.array;
            console.log(
              "[PotreeView] rgba sample (first 8 values):",
              Array.from(a.slice(0, 8)),
              "itemSize:",
              rgba.itemSize,
              "normalized:",
              rgba.normalized,
            );
          } else {
            console.warn(
              "[PotreeView] rgba attribute MISSING on first node — here are the attributes:",
              first,
            );
          }
        }, 2000);
        /* eslint-enable @typescript-eslint/no-explicit-any */

        const bbLocal = octree.boundingBox;
        octree.updateMatrixWorld(true);
        const worldOffset = new THREE.Vector3().setFromMatrixPosition(
          octree.matrixWorld,
        );
        // Diagnostic dump — log a lot so we can see which property actually
        // carries the UTM offset in this potree-core version.
        /* eslint-disable @typescript-eslint/no-explicit-any */
        const oct = octree as unknown as Record<string, any>;
        console.log("[PotreeView] octree.position:", octree.position);
        console.log("[PotreeView] octree.matrixWorld pos:", worldOffset);
        console.log("[PotreeView] octree.boundingBox local:", bbLocal.min, bbLocal.max);
        console.log("[PotreeView] octree.pcoGeometry?.offset:", oct.pcoGeometry?.offset);
        console.log("[PotreeView] octree.pcoGeometry?.scale:", oct.pcoGeometry?.scale);
        console.log("[PotreeView] octree.pcoGeometry?.boundingBox:", oct.pcoGeometry?.boundingBox);
        console.log("[PotreeView] octree.pcoGeometry?.tightBoundingBox:", oct.pcoGeometry?.tightBoundingBox);
        /* eslint-enable @typescript-eslint/no-explicit-any */

        // Compose bounds in whatever frame the cloud ACTUALLY renders in.
        // Prefer the pcoGeometry.boundingBox (absolute/world) if present —
        // that's the UTM bbox from metadata.json. Fall back to the local
        // bbox + matrixWorld offset.
        const pcoGeom = (octree as unknown as { pcoGeometry?: { boundingBox?: THREE.Box3; offset?: THREE.Vector3 } }).pcoGeometry;
        let bounds: BoundingBox3D;
        if (pcoGeom?.boundingBox && pcoGeom.boundingBox.min.x > 1000) {
          // Looks like a world/UTM bbox.
          bounds = {
            min: [pcoGeom.boundingBox.min.x, pcoGeom.boundingBox.min.y, pcoGeom.boundingBox.min.z],
            max: [pcoGeom.boundingBox.max.x, pcoGeom.boundingBox.max.y, pcoGeom.boundingBox.max.z],
          };
        } else if (pcoGeom?.offset) {
          bounds = {
            min: [bbLocal.min.x + pcoGeom.offset.x, bbLocal.min.y + pcoGeom.offset.y, bbLocal.min.z + pcoGeom.offset.z],
            max: [bbLocal.max.x + pcoGeom.offset.x, bbLocal.max.y + pcoGeom.offset.y, bbLocal.max.z + pcoGeom.offset.z],
          };
        } else {
          bounds = {
            min: [bbLocal.min.x + worldOffset.x, bbLocal.min.y + worldOffset.y, bbLocal.min.z + worldOffset.z],
            max: [bbLocal.max.x + worldOffset.x, bbLocal.max.y + worldOffset.y, bbLocal.max.z + worldOffset.z],
          };
        }
        boundsRef.current = bounds;
        console.log("[PotreeView] bounds used for camera:", bounds);

        applyCameraPreset("orbit", camera, controls, bounds);

        setIsLoading(false);
      } catch (err: unknown) {
        if (!cancelled) {
          setLoadError(err instanceof Error ? err.message : String(err));
          setIsLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [surveyId]);

  // ——— 3. Point budget ———
  useEffect(() => {
    if (potreeRef.current) {
      potreeRef.current.pointBudget = pointBudget;
    }
  }, [pointBudget]);

  // Original rgba buffers per node, keyed by node.name. We keep a copy so
  // switching from elevation/heap back to RGB restores the photographed
  // colours. With Potree 2.0 (newFormat=true) the shader does
  // `vColor = rgba` unconditionally — the color_type_* shader defines are
  // ignored — so the only way to re-colour the cloud is to overwrite the
  // rgba attribute on the CPU side.
  const originalRgbaRef = useRef<Map<string, Uint8Array>>(new Map());

  const applyCpuColorMode = useCallback(() => {
    const octree = octreeRef.current;
    if (!octree) return;
    /* eslint-disable @typescript-eslint/no-explicit-any */
    const visibleNodes =
      (octree as unknown as { visibleNodes?: Array<any> }).visibleNodes ?? [];
    /* eslint-enable @typescript-eslint/no-explicit-any */
    const zRange = pointZRangeRef.current;
    // For elevation coloring prefer the survey's base-elevation as zMin.
    // With a known flat concrete basement (e.g. 215.911 m for Acciaieria)
    // the cloud's absolute Z min (208 m, where fence posts and below-
    // grade walls live) is uninteresting and compresses all the heap-top
    // colours into the upper 30% of the viridis ramp. Using the base
    // elevation clamps ground to t=0 (purple) and spreads heap heights
    // (0..~23 m above ground) over the full gradient.
    const zMinRaw = zRange?.min ?? 0;
    const zMax = zRange?.max ?? 100;
    const zMin = survey?.baseElevation ?? zMinRaw;
    const zSpan = Math.max(zMax - zMin, 0.01);

    let nodesUpdated = 0;
    for (const vn of visibleNodes) {
      const node = vn.geometryNode ?? vn.node ?? vn;
      const geom = node?.geometry;
      if (!geom?.attributes?.rgba || !geom?.attributes?.position) continue;
      const rgba = geom.attributes.rgba;
      const pos = geom.attributes.position;
      const rgbaArr = rgba.array as Uint8Array;
      const posArr = pos.array as Float32Array;
      const count = rgbaArr.length / 4;
      const nodeKey: string = node.name ?? String(node.id ?? Math.random());

      // Cache the original (photographed) rgba on first sight.
      if (!originalRgbaRef.current.has(nodeKey)) {
        originalRgbaRef.current.set(nodeKey, new Uint8Array(rgbaArr));
      }
      const original = originalRgbaRef.current.get(nodeKey)!;

      if (colorMode === "rgb" || colorMode === "heap") {
        // Restore originals. (Heap colouring is handled by the 3D cage
        // overlays, not by recolouring points — that would require
        // point-in-polygon tests against every visible heap.)
        rgbaArr.set(original);
      } else if (colorMode === "elevation") {
        // Turbo-style 5-stop gradient. Turbo is perceptually uniform AND
        // vivid across the full range — unlike viridis, the low end is a
        // bright blue instead of a saturated purple, so the ground plane
        // doesn't collapse into one dominant colour when the camera looks
        // straight down at a mostly-flat site.
        //
        // Stops (from Google's turbo colour map):
        //   0.00  (48, 18, 59)    deep blue
        //   0.25  ( 75, 175, 225) cyan
        //   0.50  (117, 221, 108) green
        //   0.75  (249, 210,  62) orange-yellow
        //   1.00  (140, 40,  40)  dark red
        const stops = [
          [48, 18, 59],
          [75, 175, 225],
          [117, 221, 108],
          [249, 210, 62],
          [140, 40, 40],
        ];
        for (let i = 0; i < count; i++) {
          const z = posArr[i * 3 + 2];
          const t = Math.max(0, Math.min(1, (z - zMin) / zSpan));
          const scaled = t * (stops.length - 1);
          const lo = Math.floor(scaled);
          const hi = Math.min(stops.length - 1, lo + 1);
          const u = scaled - lo;
          const c0 = stops[lo];
          const c1 = stops[hi];
          rgbaArr[i * 4 + 0] = c0[0] * (1 - u) + c1[0] * u;
          rgbaArr[i * 4 + 1] = c0[1] * (1 - u) + c1[1] * u;
          rgbaArr[i * 4 + 2] = c0[2] * (1 - u) + c1[2] * u;
          // rgbaArr[i * 4 + 3] stays 0 — shader discards alpha anyway.
        }
      }
      rgba.needsUpdate = true;
      nodesUpdated++;
    }
    if (nodesUpdated > 0) {
      console.log(
        "[PotreeView] applied CPU color mode",
        colorMode,
        "to",
        nodesUpdated,
        "visible nodes (zMin=",
        zMin.toFixed(2),
        "zMax=",
        zMax.toFixed(2),
        ")",
      );
    }
  }, [colorMode, survey?.baseElevation]);

  // Re-apply on color-mode change + every time the set of visible nodes
  // grows (new nodes loaded during pan/zoom would otherwise render in
  // whatever colour came out of the decoder, not the requested mode).
  useEffect(() => {
    applyCpuColorMode();
    const id = setInterval(applyCpuColorMode, 500);
    return () => clearInterval(id);
  }, [applyCpuColorMode]);

  // ——— 4. Color mode ———
  useEffect(() => {
    const octree = octreeRef.current;
    if (!octree) return;

    console.log("[PotreeView] color mode →", colorMode);
    switch (colorMode) {
      case "rgb":
        octree.material.pointColorType = PointColorType.RGB;
        break;
      case "elevation": {
        octree.material.pointColorType = PointColorType.HEIGHT;
        // pcoGeometry.tightBoundingBox is the CUBIC AABB (0..328 on every
        // axis) — useless for an elevation ramp. We read the real Z range
        // directly from metadata.json's position attribute during load.
        const real = pointZRangeRef.current;
        const zMin = real?.min ?? boundsRef.current?.min[2] ?? 0;
        const zMax = real?.max ?? boundsRef.current?.max[2] ?? 100;
        octree.material.heightMin = zMin;
        octree.material.heightMax = zMax;
        console.log(
          "[PotreeView] elevation range:",
          zMin, "→", zMax,
          "source:", real ? "metadata.position" : "bounds fallback",
        );
        break;
      }
      case "heap":
        octree.material.pointColorType = PointColorType.RGB;
        break;
    }
    // Force shader recompile — setting pointColorType alone is not always
    // enough to trigger the #define refresh in potree-core.
    octree.material.needsUpdate = true;
  }, [colorMode]);

  // ——— 5. Base plane ———
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;

    // Remove existing
    if (basePlaneRef.current) {
      scene.remove(basePlaneRef.current);
      basePlaneRef.current.geometry.dispose();
      (basePlaneRef.current.material as THREE.Material).dispose();
      basePlaneRef.current = null;
    }

    if (!showBasePlane || !boundsRef.current || !survey) return;

    const bounds = boundsRef.current;
    const baseZ = survey.baseElevation ?? bounds.min[2];
    const sizeX = (bounds.max[0] - bounds.min[0]) * 1.2;
    const sizeY = (bounds.max[1] - bounds.min[1]) * 1.2;
    const centerX = (bounds.min[0] + bounds.max[0]) / 2;
    const centerY = (bounds.min[1] + bounds.max[1]) / 2;

    const geom = new THREE.PlaneGeometry(sizeX, sizeY, 20, 20);
    const mat = new THREE.MeshBasicMaterial({
      color: 0x6575a0, // evlos-500
      transparent: true,
      opacity: 0.15,
      wireframe: true,
      side: THREE.DoubleSide,
    });
    const plane = new THREE.Mesh(geom, mat);
    plane.position.set(centerX, centerY, baseZ);
    scene.add(plane);
    basePlaneRef.current = plane;
  }, [showBasePlane, survey?.baseElevation, survey?.id, isLoading]);

  // ——— 6. Heap overlays (extruded prisms) ———
  const updateHeapOverlays = useCallback(() => {
    const scene = sceneRef.current;
    if (!scene) return;

    // Remove old group
    if (heapOverlayGroupRef.current) {
      disposeGroup(heapOverlayGroupRef.current);
      scene.remove(heapOverlayGroupRef.current);
      heapOverlayGroupRef.current = null;
    }

    if (!showHeapOverlay3D || heaps.length === 0) return;

    const group = new THREE.Group();

    heaps.forEach((heap, idx) => {
      if (!heap.polygon?.coordinates?.[0]) return;
      const ring = heap.polygon.coordinates[0];
      if (ring.length < 3) return;

      const shape = new THREE.Shape();
      shape.moveTo(ring[0][0], ring[0][1]);
      for (let i = 1; i < ring.length; i++) {
        shape.lineTo(ring[i][0], ring[i][1]);
      }
      shape.closePath();

      const color = getHeapColor(heap, idx);
      const isSelected = selectedHeapId === heap.id;
      const depth = Math.max(heap.maxHeight, 0.5);

      // Low-opacity prism so operators see both the heap envelope AND the
      // point-cloud morphology through it. Keeping the solid extrusion is
      // important — without it the 3D view is hard to read — but the fill
      // is kept faint (8%) so peaks poke out clearly. Depth-write is off
      // so the cloud always draws on top.
      const geom = new THREE.ExtrudeGeometry(shape, {
        depth,
        bevelEnabled: false,
      });
      const mat = new THREE.MeshBasicMaterial({
        color,
        transparent: true,
        opacity: isSelected ? 0.22 : 0.08,
        side: THREE.DoubleSide,
        depthWrite: false,
      });
      const mesh = new THREE.Mesh(geom, mat);
      mesh.position.z = heap.baseElevation;
      mesh.userData = { heapId: heap.id };
      group.add(mesh);

      // Cage wireframe (edges only — no filled triangles) so the heap's
      // boundary is always readable even when the fill fades into the
      // cloud. Selected heap gets a brighter, thicker cage.
      const edgeGeom = new THREE.EdgesGeometry(geom);
      const edgeMat = new THREE.LineBasicMaterial({
        color: isSelected ? 0xffffff : color,
        transparent: !isSelected,
        opacity: isSelected ? 1 : 0.7,
      });
      const edges = new THREE.LineSegments(edgeGeom, edgeMat);
      edges.position.z = heap.baseElevation;
      edges.userData = { heapId: heap.id };
      group.add(edges);
    });

    scene.add(group);
    heapOverlayGroupRef.current = group;
  }, [heaps, selectedHeapId, showHeapOverlay3D]);

  useEffect(() => {
    if (!isLoading) updateHeapOverlays();
  }, [updateHeapOverlays, isLoading]);

  // ——— 7. Camera presets ———
  useEffect(() => {
    if (!cameraPreset || !cameraRef.current || !controlsRef.current || !boundsRef.current)
      return;
    applyCameraPreset(cameraPreset, cameraRef.current, controlsRef.current, boundsRef.current);
    clearCameraPreset();
  }, [cameraPreset, clearCameraPreset]);

  // ——— 8. Center on selection ———
  const lastCenterRef = useRef(0);
  useEffect(() => {
    if (centerOnSelectionRequested === lastCenterRef.current) return;
    lastCenterRef.current = centerOnSelectionRequested;

    if (!selectedHeapId || !cameraRef.current || !controlsRef.current) return;
    const heap = heaps.find((h) => h.id === selectedHeapId);
    if (heap) {
      centerOnHeap(cameraRef.current, controlsRef.current, heap);
    }
  }, [centerOnSelectionRequested, selectedHeapId, heaps]);

  // ——— 9. 3D section plane for selected cross section ———
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;

    // Remove old plane
    if (sectionPlaneRef.current) {
      disposeGroup(sectionPlaneRef.current);
      scene.remove(sectionPlaneRef.current);
      sectionPlaneRef.current = null;
    }

    if (!selectedSectionId || !boundsRef.current || isLoading) return;

    const section = sectionSections.find((s) => s.id === selectedSectionId);
    if (!section) return;

    try {
      const geom = JSON.parse(section.lineGeoJSON);
      const coords = geom.coordinates as number[][];
      if (!coords || coords.length < 2) return;

      const [x1, y1] = coords[0];
      const [x2, y2] = coords[coords.length - 1];
      const lineLen = Math.hypot(x2 - x1, y2 - y1);
      if (lineLen < 0.1) return;

      const bounds = boundsRef.current;
      const baseZ = survey?.baseElevation ?? bounds.min[2];
      const topZ = bounds.max[2] + 2;
      const planeHeight = topZ - baseZ;

      // Build a vertical rectangle along the line
      const cx = (x1 + x2) / 2;
      const cy = (y1 + y2) / 2;
      const bearing = Math.atan2(y2 - y1, x2 - x1);

      const planeGeom = new THREE.PlaneGeometry(lineLen, planeHeight);
      const planeMat = new THREE.MeshBasicMaterial({
        color: 0xf59e0b,
        transparent: true,
        opacity: 0.2,
        side: THREE.DoubleSide,
        depthWrite: false,
      });
      const planeMesh = new THREE.Mesh(planeGeom, planeMat);

      // PlaneGeometry faces +Z by default. We want it vertical along the line.
      // Rotate to stand upright: 90° around X axis
      planeMesh.rotation.x = Math.PI / 2;
      // Rotate to align with line bearing
      planeMesh.rotation.z = bearing;
      // Position at center of line, at mid height
      planeMesh.position.set(cx, cy, baseZ + planeHeight / 2);

      // Outline
      const outlineGeom = new THREE.EdgesGeometry(planeGeom);
      const outlineMat = new THREE.LineBasicMaterial({ color: 0xf59e0b });
      const outline = new THREE.LineSegments(outlineGeom, outlineMat);
      outline.rotation.x = Math.PI / 2;
      outline.rotation.z = bearing;
      outline.position.set(cx, cy, baseZ + planeHeight / 2);

      const group = new THREE.Group();
      group.add(planeMesh);
      group.add(outline);
      scene.add(group);
      sectionPlaneRef.current = group;
    } catch {
      // Invalid GeoJSON, skip
    }
  }, [selectedSectionId, sectionSections, isLoading, survey?.baseElevation]);

  // ——— 10. Resize observer ———
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const ro = new ResizeObserver(() => {
      const r = rendererRef.current;
      const c = cameraRef.current;
      if (r && c) {
        r.setSize(container.clientWidth, container.clientHeight);
        c.aspect = container.clientWidth / container.clientHeight;
        c.updateProjectionMatrix();
      }
    });
    ro.observe(container);
    return () => ro.disconnect();
  }, []);

  // ——— 10. 3D → 2D picking (click on heap overlay) ———
  useEffect(() => {
    const canvas = rendererRef.current?.domElement;
    if (!canvas) return;

    const handler = (e: MouseEvent) => {
      const camera = cameraRef.current;
      const scene = sceneRef.current;
      if (!camera || !scene || !heapOverlayGroupRef.current) return;

      const rect = canvas.getBoundingClientRect();
      const ndc = new THREE.Vector2(
        ((e.clientX - rect.left) / rect.width) * 2 - 1,
        -((e.clientY - rect.top) / rect.height) * 2 + 1,
      );
      const raycaster = new THREE.Raycaster();
      raycaster.setFromCamera(ndc, camera);

      const overlays = heapOverlayGroupRef.current.children.filter(
        (c) => c.userData.heapId != null,
      );
      const hits = raycaster.intersectObjects(overlays, false);
      if (hits.length > 0) {
        const heapId = hits[0].object.userData.heapId as number;
        selectHeap(heapId);
      }
    };

    canvas.addEventListener("click", handler);
    return () => canvas.removeEventListener("click", handler);
  }, [selectHeap]);

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="absolute inset-0" />

      {/* Loading overlay */}
      {isLoading && !loadError && (
        <div className="absolute inset-0 flex items-center justify-center bg-[#101824]/80 backdrop-blur-sm z-40">
          <div className="flex items-center gap-3">
            <div className="animate-spin h-5 w-5 border-2 border-primary border-t-transparent rounded-full" />
            <span className="text-sm text-evlos-200">
              Caricamento nuvola di punti…
            </span>
          </div>
        </div>
      )}

      {/* Error overlay */}
      {loadError && (
        <div className="absolute inset-0 flex items-center justify-center bg-[#101824]/80 z-40">
          <div className="bg-danger/10 border border-danger text-danger p-4 rounded-lg max-w-md">
            <p className="font-medium">Errore caricamento 3D</p>
            <p className="text-sm mt-1">{loadError}</p>
          </div>
        </div>
      )}

      {/* Toolbar */}
      {!isLoading && !loadError && <Toolbar3D />}

      {/* Status bar — bottom-left */}
      {!isLoading && !loadError && (
        <div className="absolute bottom-2 left-2 z-50 bg-evlos-800/90 backdrop-blur-sm rounded px-3 py-1 border border-evlos-700">
          <span className="font-mono text-xs text-evlos-200">
            {visiblePoints.toLocaleString("it-IT")} punti visualizzati
          </span>
        </div>
      )}
    </div>
  );
}

/** Dispose all geometries/materials in a group, then clear. */
function disposeGroup(group: THREE.Group): void {
  group.traverse((obj) => {
    const mesh = obj as THREE.Mesh;
    if (mesh.geometry) mesh.geometry.dispose();
    if (mesh.material) {
      const mat = mesh.material;
      if (Array.isArray(mat)) mat.forEach((m) => m.dispose());
      else mat.dispose();
    }
  });
  group.clear();
}
