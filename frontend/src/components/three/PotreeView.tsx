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

        if (cancelled) return;

        const octree = await potree.loadPointCloud(metadataUrl, potreeBaseUrl);

        if (cancelled) {
          octree.dispose();
          return;
        }

        // Configure material
        octree.material.size = 1.5;
        octree.material.pointSizeType = PointSizeType.ADAPTIVE;
        octree.material.shape = PointShape.CIRCLE;
        octree.material.pointColorType = PointColorType.RGB;

        scene.add(octree);
        octreeRef.current = octree;

        // Extract bounds
        const bb = octree.boundingBox;
        const bounds: BoundingBox3D = {
          min: [bb.min.x, bb.min.y, bb.min.z],
          max: [bb.max.x, bb.max.y, bb.max.z],
        };
        boundsRef.current = bounds;

        // Default camera position
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

  // ——— 4. Color mode ———
  useEffect(() => {
    const octree = octreeRef.current;
    if (!octree) return;

    switch (colorMode) {
      case "rgb":
        octree.material.pointColorType = PointColorType.RGB;
        break;
      case "elevation":
        octree.material.pointColorType = PointColorType.HEIGHT;
        if (boundsRef.current) {
          octree.material.heightMin = boundsRef.current.min[2];
          octree.material.heightMax = boundsRef.current.max[2];
        }
        break;
      case "heap":
        // Heap mode: show RGB but with highlighted overlays
        octree.material.pointColorType = PointColorType.RGB;
        break;
    }
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

      const depth = Math.max(heap.maxHeight, 0.5);
      const geom = new THREE.ExtrudeGeometry(shape, {
        depth,
        bevelEnabled: false,
      });

      const color = getHeapColor(heap, idx);
      const isSelected = selectedHeapId === heap.id;
      const mat = new THREE.MeshBasicMaterial({
        color,
        transparent: true,
        opacity: isSelected ? 0.5 : 0.25,
        side: THREE.DoubleSide,
        depthWrite: false,
      });

      const mesh = new THREE.Mesh(geom, mat);
      mesh.position.z = heap.baseElevation;
      mesh.userData = { heapId: heap.id };

      group.add(mesh);

      // Wireframe for selected
      if (isSelected) {
        const wireGeom = new THREE.EdgesGeometry(geom);
        const wireMat = new THREE.LineBasicMaterial({ color: 0xffffff, linewidth: 2 });
        const wire = new THREE.LineSegments(wireGeom, wireMat);
        wire.position.z = heap.baseElevation;
        wire.userData = { heapId: heap.id };
        group.add(wire);
      }
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

  // ——— 9. Resize observer ———
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
