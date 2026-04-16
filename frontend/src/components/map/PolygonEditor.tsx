import { useEffect, useRef, useCallback } from "react";
import type OlMap from "ol/Map";
import type VectorSource from "ol/source/Vector";
import type Feature from "ol/Feature";
import type MapBrowserEvent from "ol/MapBrowserEvent";
import Draw from "ol/interaction/Draw";
import Modify from "ol/interaction/Modify";
import Snap from "ol/interaction/Snap";
import GeoJSON from "ol/format/GeoJSON";
import Overlay from "ol/Overlay";
import { Style, Stroke, Fill } from "ol/style";
import { toast } from "sonner";
import { useEditingStore } from "@/stores/editingStore";
import { useHeapStore } from "@/stores/heapStore";
import type { Heap } from "@/types";

/** evlos-500 = #495A82 */
const EDITING_STROKE_COLOR = "#495A82";
const EDITING_FILL_COLOR = "rgba(73, 90, 130, 0.12)";

const editingStyle = new Style({
  stroke: new Stroke({
    color: EDITING_STROKE_COLOR,
    width: 3,
    lineDash: [5, 3],
  }),
  fill: new Fill({ color: EDITING_FILL_COLOR }),
});

const geoJSONFormat = new GeoJSON();

interface HistoryEntry {
  op: "create" | "modify" | "delete" | "split" | "merge";
  timestamp: number;
  before: Heap[];
  after: Heap[];
  surveyId: number;
}

type PushHistory = (entry: HistoryEntry) => void;

interface PolygonEditorProps {
  map: OlMap;
  source: VectorSource;
  surveyId: number;
}

export function PolygonEditor({ map, source, surveyId }: PolygonEditorProps) {
  const drawRef = useRef<Draw | null>(null);
  const modifyRef = useRef<Modify | null>(null);
  const snapRef = useRef<Snap | null>(null);
  const overlayRef = useRef<Overlay | null>(null);
  const overlayElRef = useRef<HTMLDivElement | null>(null);
  const beforeSnapshotRef = useRef<Map<number, Feature> | null>(null);
  const moveHandlerRef = useRef<((e: MapBrowserEvent<PointerEvent>) => void) | null>(null);

  const activeTool = useEditingStore((s) => s.activeTool);
  const pushHistory = useEditingStore((s) => s.pushHistory) as PushHistory;
  const loadBySurvey = useHeapStore((s) => s.loadBySurvey);

  const refreshHeaps = useCallback(async () => {
    await loadBySurvey(surveyId);
  }, [loadBySurvey, surveyId]);

  const getHeapSnapshot = useCallback(
    (heapIds: number[]): Heap[] => {
      const heaps = useHeapStore.getState().heaps;
      return heaps.filter((h) => heapIds.includes(h.id));
    },
    [],
  );

  // Clean up all interactions
  const removeAllInteractions = useCallback(() => {
    if (drawRef.current) {
      map.removeInteraction(drawRef.current);
      drawRef.current = null;
    }
    if (modifyRef.current) {
      // Clean up pointermove listener
      if (moveHandlerRef.current) {
        map.un("pointermove" as "singleclick", moveHandlerRef.current as never);
        moveHandlerRef.current = null;
      }
      map.removeInteraction(modifyRef.current);
      modifyRef.current = null;
    }
    if (snapRef.current) {
      map.removeInteraction(snapRef.current);
      snapRef.current = null;
    }
    if (overlayRef.current) {
      map.removeOverlay(overlayRef.current);
      overlayRef.current = null;
    }
  }, [map]);

  // Set up cursor based on tool
  useEffect(() => {
    const viewport = map.getViewport();
    if (activeTool === "draw" || activeTool === "split") {
      viewport.style.cursor = "crosshair";
    } else if (activeTool === "delete") {
      viewport.style.cursor = "not-allowed";
    } else {
      viewport.style.cursor = "";
    }
    return () => {
      viewport.style.cursor = "";
    };
  }, [map, activeTool]);

  // Main effect: manage OL interactions based on activeTool
  useEffect(() => {
    removeAllInteractions();

    if (activeTool === "draw") {
      setupDraw(map, source, surveyId, pushHistory, refreshHeaps, drawRef, snapRef);
    } else if (activeTool === "modify") {
      setupModify(
        map, source, surveyId, pushHistory, refreshHeaps, getHeapSnapshot,
        modifyRef, snapRef, beforeSnapshotRef, overlayRef, overlayElRef, moveHandlerRef,
      );
    } else if (activeTool === "split") {
      setupSplit(map, source, surveyId, pushHistory, refreshHeaps, getHeapSnapshot, drawRef, snapRef);
    }

    return () => {
      removeAllInteractions();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTool, map, source, surveyId]);

  return null;
}

// ---------------------------------------------------------------------------
// Draw interaction
// ---------------------------------------------------------------------------

function setupDraw(
  map: OlMap,
  source: VectorSource,
  surveyId: number,
  pushHistory: PushHistory,
  refreshHeaps: () => Promise<void>,
  drawRef: React.MutableRefObject<Draw | null>,
  snapRef: React.MutableRefObject<Snap | null>,
): void {
  const draw = new Draw({
    source,
    type: "Polygon",
    style: editingStyle,
  });

  draw.on("drawend", async (evt) => {
    const feature = evt.feature;
    const geojson = JSON.parse(
      geoJSONFormat.writeFeature(feature, {
        featureProjection: map.getView().getProjection(),
        dataProjection: map.getView().getProjection(),
      }),
    ) as { geometry: Record<string, unknown> };
    const polygonGeoJSON = geojson.geometry;

    // Remove the drawn feature from source (will be re-added after DB insert)
    setTimeout(() => source.removeFeature(feature), 0);

    try {
      const result = await window.api.editing.createHeap({
        surveyId,
        polygonGeoJSON,
      });
      const volume = (result.volume as number) ?? 0;
      toast.success(
        `Nuovo cumulo creato — volume: ${volume.toFixed(2)} m³`,
        { className: "font-mono" },
      );

      await refreshHeaps();

      pushHistory({
        op: "create",
        timestamp: Date.now(),
        before: [],
        after: [result as unknown as Heap],
        surveyId,
      });
    } catch (err) {
      toast.error(`Errore: ${err instanceof Error ? err.message : String(err)}`, {
        duration: 6000,
      });
    }

    useEditingStore.getState().setTool("select");
  });

  map.addInteraction(draw);
  drawRef.current = draw;

  // Snap AFTER draw
  const snap = new Snap({ source, pixelTolerance: 10 });
  map.addInteraction(snap);
  snapRef.current = snap;
}

// ---------------------------------------------------------------------------
// Modify interaction
// ---------------------------------------------------------------------------

function setupModify(
  map: OlMap,
  source: VectorSource,
  surveyId: number,
  pushHistory: PushHistory,
  refreshHeaps: () => Promise<void>,
  getHeapSnapshot: (ids: number[]) => Heap[],
  modifyRef: React.MutableRefObject<Modify | null>,
  snapRef: React.MutableRefObject<Snap | null>,
  beforeSnapshotRef: React.MutableRefObject<Map<number, Feature> | null>,
  overlayRef: React.MutableRefObject<Overlay | null>,
  overlayElRef: React.MutableRefObject<HTMLDivElement | null>,
  moveHandlerRef: React.MutableRefObject<((e: MapBrowserEvent<PointerEvent>) => void) | null>,
): void {
  const modify = new Modify({ source });

  // UTM coordinate tooltip
  let tooltipEl = overlayElRef.current;
  if (!tooltipEl) {
    tooltipEl = document.createElement("div");
    tooltipEl.className =
      "font-mono text-xs bg-evlos-900/90 text-evlos-50 px-2 py-1 rounded pointer-events-none";
    overlayElRef.current = tooltipEl;
  }
  const overlay = new Overlay({
    element: tooltipEl,
    positioning: "bottom-left",
    offset: [10, -10],
  });
  map.addOverlay(overlay);
  overlayRef.current = overlay;

  // Show coords on pointermove during modify
  const moveHandler = (e: MapBrowserEvent<PointerEvent>) => {
    const coord = e.coordinate;
    tooltipEl!.innerHTML = `E: ${coord[0].toFixed(2)}<br>N: ${coord[1].toFixed(2)}`;
    overlay.setPosition(coord);
  };
  map.on("pointermove" as "singleclick", moveHandler as never);
  moveHandlerRef.current = moveHandler;

  modify.on("modifystart", (evt) => {
    // Capture before snapshot
    const featureMap = new Map<number, Feature>();
    for (const f of evt.features.getArray()) {
      const id = f.getId() as number;
      if (id != null) {
        featureMap.set(id, f.clone());
      }
    }
    beforeSnapshotRef.current = featureMap;
  });

  modify.on("modifyend", async (evt) => {
    const beforeMap = beforeSnapshotRef.current;
    if (!beforeMap) return;

    const modifiedIds: number[] = [];
    for (const f of evt.features.getArray()) {
      const id = f.getId() as number;
      if (id != null) modifiedIds.push(id);
    }

    const beforeHeaps = getHeapSnapshot(modifiedIds);

    // Recompute each modified feature
    for (const f of evt.features.getArray()) {
      const heapId = f.getId() as number;
      if (heapId == null) continue;

      const geojson = JSON.parse(
        geoJSONFormat.writeFeature(f, {
          featureProjection: map.getView().getProjection(),
          dataProjection: map.getView().getProjection(),
        }),
      ) as { geometry: Record<string, unknown> };

      try {
        const result = await window.api.editing.recomputeHeap({
          heapId,
          polygonGeoJSON: geojson.geometry,
          surveyId,
        });

        const oldVol = beforeHeaps.find((h) => h.id === heapId)?.volume ?? 0;
        const newVol = (result.volume as number) ?? 0;
        const delta = newVol - oldVol;
        const sign = delta >= 0 ? "+" : "";
        toast.success(
          `Cumulo aggiornato — Δvolume: ${sign}${delta.toFixed(2)} m³`,
          { className: "font-mono" },
        );
      } catch (err) {
        toast.error(
          `Errore: ${err instanceof Error ? err.message : String(err)}`,
          { duration: 6000 },
        );
      }
    }

    await refreshHeaps();
    const afterHeaps = getHeapSnapshot(modifiedIds);

    pushHistory({
      op: "modify",
      timestamp: Date.now(),
      before: beforeHeaps,
      after: afterHeaps,
      surveyId,
    });

    beforeSnapshotRef.current = null;
  });

  map.addInteraction(modify);
  modifyRef.current = modify;

  // Snap AFTER modify
  const snap = new Snap({ source, pixelTolerance: 10 });
  map.addInteraction(snap);
  snapRef.current = snap;
}

// ---------------------------------------------------------------------------
// Split interaction (draw a LineString)
// ---------------------------------------------------------------------------

function setupSplit(
  map: OlMap,
  source: VectorSource,
  surveyId: number,
  pushHistory: PushHistory,
  refreshHeaps: () => Promise<void>,
  getHeapSnapshot: (ids: number[]) => Heap[],
  drawRef: React.MutableRefObject<Draw | null>,
  snapRef: React.MutableRefObject<Snap | null>,
): void {
  const draw = new Draw({
    type: "LineString",
    style: new Style({
      stroke: new Stroke({
        color: "#EF4444",
        width: 2,
        lineDash: [8, 4],
      }),
    }),
  });

  draw.on("drawend", async (evt) => {
    const lineFeature = evt.feature;
    const lineGeojson = JSON.parse(
      geoJSONFormat.writeFeature(lineFeature, {
        featureProjection: map.getView().getProjection(),
        dataProjection: map.getView().getProjection(),
      }),
    ) as { geometry: { coordinates: number[][] } };

    const lineCoords = lineGeojson.geometry.coordinates;

    // Use midpoint of line to find the intersected heap
    const midX =
      (lineCoords[0][0] + lineCoords[lineCoords.length - 1][0]) / 2;
    const midY =
      (lineCoords[0][1] + lineCoords[lineCoords.length - 1][1]) / 2;

    // Find heap feature at midpoint
    const pixel = map.getPixelFromCoordinate([midX, midY]);
    const features = map.getFeaturesAtPixel(pixel, {
      layerFilter: (layer) => layer.getSource() === source,
    });

    const targetFeature = features?.[0];
    const heapId = targetFeature?.getId() as number | undefined;

    if (!heapId) {
      toast.error("Nessun cumulo trovato sotto la linea di taglio", {
        duration: 4000,
      });
      useEditingStore.getState().setTool("select");
      return;
    }

    const beforeHeaps = getHeapSnapshot([heapId]);

    try {
      const newHeaps = await window.api.editing.splitHeap({
        heapId,
        lineGeoJSON: lineGeojson.geometry as unknown as Record<string, unknown>,
        surveyId,
      });

      const volumes = (newHeaps as unknown as Array<{ volume: number }>).map(
        (h) => h.volume?.toFixed(1) ?? "?",
      );
      toast.success(
        `Cumulo diviso in ${newHeaps.length} parti (${volumes.join(" m³ + ")} m³)`,
        { className: "font-mono" },
      );

      await refreshHeaps();

      pushHistory({
        op: "split",
        timestamp: Date.now(),
        before: beforeHeaps,
        after: newHeaps as unknown as Heap[],
        surveyId,
      });
    } catch (err) {
      toast.error(
        `Errore: ${err instanceof Error ? err.message : String(err)}`,
        { duration: 6000 },
      );
    }

    useEditingStore.getState().setTool("select");
  });

  map.addInteraction(draw);
  drawRef.current = draw;

  const snap = new Snap({ source, pixelTolerance: 10 });
  map.addInteraction(snap);
  snapRef.current = snap;
}
