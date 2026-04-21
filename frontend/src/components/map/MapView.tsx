import "ol/ol.css";
import { useEffect, useRef, useState } from "react";
import OlMap from "ol/Map";
import View from "ol/View";
import TileLayer from "ol/layer/Tile";
import XYZ from "ol/source/XYZ";
import VectorLayer from "ol/layer/Vector";
import VectorSource from "ol/source/Vector";
import Feature from "ol/Feature";
import { Polygon } from "ol/geom";
import { Style, Fill, Stroke, Text } from "ol/style";
import Select from "ol/interaction/Select";
import { click, pointerMove } from "ol/events/condition";
import TileGrid from "ol/tilegrid/TileGrid";
import { defaults as defaultControls, ScaleLine } from "ol/control";
import type { FeatureLike } from "ol/Feature";
import { getUtmProjection } from "@/lib/projections";
import { useHeapStore } from "@/stores/heapStore";
import { useEditingStore } from "@/stores/editingStore";
import { useMapStore } from "@/stores/mapStore";
import { EditingToolbar } from "./EditingToolbar";
import { PolygonEditor } from "./PolygonEditor";
import { GroundSelectionTool } from "./GroundSelectionTool";
import { EditingActions } from "./EditingActions";
import { CrossSectionDrawTool } from "./CrossSectionDrawTool";
import { CrossSectionLayer } from "./CrossSectionLayer";
import { useEditingShortcuts } from "@/hooks/useEditingShortcuts";
import { useCrossSectionStore } from "@/stores/crossSectionStore";

interface TileMetadata {
  crs: string;
  bounds: [number, number, number, number];
  origin: [number, number];
  resolutions: number[];
  tileSize: number;
  min_zoom: number;
  max_zoom: number;
}

const CATEGORY_COLORS: Record<string, string> = {
  "Rottame ferroso": "#B45309",
  Ghisa: "#6575A0",
  Scorie: "#6B7280",
  Cascami: "#92400E",
  RAEE: "#059669",
};
const DEFAULT_COLOR = "#6575A0";

function getColor(category: string | null): string {
  return (category && CATEGORY_COLORS[category]) || DEFAULT_COLOR;
}

function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

interface MapViewProps {
  surveyId: number;
}

export function MapView({ surveyId }: MapViewProps) {
  const mapDivRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<OlMap | null>(null);
  const heapSourceRef = useRef<VectorSource>(new VectorSource());
  const heapLayerRef = useRef<VectorLayer | null>(null);
  const selectRef = useRef<Select | null>(null);
  const hoverRef = useRef<Select | null>(null);
  const [coordinate, setCoordinate] = useState<[number, number] | null>(null);
  const [mapReady, setMapReady] = useState(false);

  const heaps = useHeapStore((s) => s.heaps);
  const selectedHeapId = useHeapStore((s) => s.selectedHeapId);
  const selectHeap = useHeapStore((s) => s.select);
  const loadBySurvey = useHeapStore((s) => s.loadBySurvey);
  const activeTool = useEditingStore((s) => s.activeTool);
  const mergeSelection = useEditingStore((s) => s.mergeSelection);
  const toggleMergeSelection = useEditingStore(
    (s) => s.toggleMergeSelection,
  );

  const heapsVisible = useMapStore((s) => s.heapsVisible);
  const heapsOpacity = useMapStore((s) => s.heapsOpacity);
  const labelsVisible = useMapStore((s) => s.labelsVisible);

  // Enable keyboard shortcuts
  useEditingShortcuts(mapReady);

  const loadCrossSections = useCrossSectionStore((s) => s.loadForSurvey);

  // Load heaps and cross sections on mount and when surveyId changes
  useEffect(() => {
    loadBySurvey(surveyId);
    loadCrossSections(surveyId);
  }, [surveyId, loadBySurvey, loadCrossSections]);

  // Create map
  useEffect(() => {
    if (!mapDivRef.current) return;
    let cancelled = false;

    (async () => {
      const rawMeta = await window.api.tiles.getMetadata(surveyId);
      if (!rawMeta || cancelled) return;
      const metadata = rawMeta as unknown as TileMetadata;

      const baseUrl = await window.api.tiles.getBaseUrl();
      if (cancelled) return;

      const projection = getUtmProjection(metadata.crs);
      const extent = metadata.bounds as [number, number, number, number];
      projection.setExtent(extent);

      const tileGrid = new TileGrid({
        origin: metadata.origin,
        resolutions: metadata.resolutions,
        tileSize: metadata.tileSize,
      });

      const tileSource = new XYZ({
        projection,
        tileGrid,
        url: `${baseUrl}/tiles/${surveyId}/{z}/{x}/{y}.png`,
        wrapX: false,
      });

      // Zoom/pan configuration:
      // - no `extent` on View — free panning; outside the ortho bounds the
      //   operator sees the black background but the view no longer bounces
      //   back to center.
      // - `resolutions` array SNAPS zoom to the tile-grid levels (plus a few
      //   extra coarse levels for context). Without this, OL zooms to
      //   arbitrary intermediate resolutions and the tile layer gets scaled
      //   by OL while the vector polygons render at the exact view resolution
      //   — result: polygons appeared to drift off their heaps between
      //   consecutive tile zooms (e.g. between the 20 m and 5 m scale-line
      //   levels).
      const coarsestRes = metadata.resolutions[0];
      const viewResolutions = [
        coarsestRes * 8,
        coarsestRes * 4,
        coarsestRes * 2,
        ...metadata.resolutions,
      ];
      const map = new OlMap({
        target: mapDivRef.current!,
        layers: [new TileLayer({ source: tileSource })],
        view: new View({
          projection,
          center: [
            (extent[0] + extent[2]) / 2,
            (extent[1] + extent[3]) / 2,
          ],
          resolutions: viewResolutions,
          resolution: coarsestRes,
          constrainResolution: true,
        }),
        controls: defaultControls().extend([
          new ScaleLine({ units: "metric" }),
        ]),
      });

      map.on("pointermove", (evt) => {
        setCoordinate(evt.coordinate as [number, number]);
      });

      map.getView().fit(extent, { padding: [20, 20, 20, 20] });

      // Create heap vector layer
      const heapSource = heapSourceRef.current;
      const heapLayer = new VectorLayer({
        source: heapSource,
        visible: true,
      });
      map.addLayer(heapLayer);
      heapLayerRef.current = heapLayer;

      mapRef.current = map;
      setMapReady(true);
    })();

    return () => {
      cancelled = true;
      setMapReady(false);
      if (mapRef.current) {
        mapRef.current.setTarget(undefined);
        mapRef.current = null;
      }
    };
  }, [surveyId]);

  // Sync heaps to vector source
  useEffect(() => {
    const source = heapSourceRef.current;
    source.clear();

    for (const heap of heaps) {
      const coords = heap.polygon?.coordinates;
      const geom = coords ? new Polygon(coords) : undefined;
      const feature = new Feature({
        geometry: geom,
        heapId: heap.id,
        label: heap.label,
        category: heap.materialCategory,
        volume: heap.volume,
        isManuallyConfirmed: heap.isManuallyConfirmed,
      });
      feature.setId(heap.id);
      source.addFeature(feature);
    }
  }, [heaps]);

  // Style function reacting to selection state
  useEffect(() => {
    const layer = heapLayerRef.current;
    if (!layer) return;

    layer.setStyle((feature: FeatureLike): Style => {
      const props = feature.getProperties();
      const color = getColor(props.category);
      const isSelected = feature.getId() === selectedHeapId;
      const isMergeSelected = mergeSelection.includes(
        feature.getId() as number,
      );
      const strokeWidth = isSelected || isMergeSelected ? 3 : 2;
      const fillAlpha = isSelected ? 0.35 : isMergeSelected ? 0.3 : 0.25;
      const strokeColor = isSelected
        ? "#F9FAFB"
        : isMergeSelected
          ? "#F59E0B"
          : color;

      return new Style({
        stroke: new Stroke({
          color: strokeColor,
          width: strokeWidth,
          lineDash: isMergeSelected ? [5, 3] : undefined,
        }),
        fill: new Fill({ color: hexToRgba(color, fillAlpha) }),
        text: labelsVisible
          ? new Text({
              text: props.label || `#${feature.getId()}`,
              font: '13px "JetBrains Mono", monospace',
              fill: new Fill({ color: "#FFFFFF" }),
              stroke: new Stroke({ color: "#000000", width: 3 }),
            })
          : undefined,
      });
    });

    layer.setVisible(heapsVisible);
    layer.setOpacity(heapsOpacity);
    layer.changed();
  }, [
    selectedHeapId,
    mergeSelection,
    heapsVisible,
    heapsOpacity,
    labelsVisible,
  ]);

  // Select/hover interactions — only when in select/delete/merge mode
  useEffect(() => {
    const map = mapRef.current;
    const layer = heapLayerRef.current;
    if (!map || !layer) return;

    // Remove old interactions
    if (selectRef.current) {
      map.removeInteraction(selectRef.current);
      selectRef.current = null;
    }
    if (hoverRef.current) {
      map.removeInteraction(hoverRef.current);
      hoverRef.current = null;
    }

    const needsSelect =
      activeTool === "select" ||
      activeTool === "delete" ||
      activeTool === "merge";

    if (!needsSelect) return;

    const selectInteraction = new Select({
      condition: click,
      layers: [layer],
      style: null, // Use layer style
    });
    selectInteraction.on("select", (e) => {
      const selected = e.selected[0];
      const heapId = selected
        ? (selected.getId() as number)
        : null;

      if (activeTool === "merge" && heapId != null) {
        toggleMergeSelection(heapId);
        selectInteraction.getFeatures().clear();
      } else {
        selectHeap(heapId);
      }
    });
    map.addInteraction(selectInteraction);
    selectRef.current = selectInteraction;

    // Hover
    const hoverInteraction = new Select({
      condition: pointerMove,
      layers: [layer],
      style: (feature: FeatureLike) => {
        const props = feature.getProperties();
        const color = getColor(props.category);
        return new Style({
          stroke: new Stroke({ color, width: 2.5 }),
          fill: new Fill({ color: hexToRgba(color, 0.3) }),
          text: labelsVisible
            ? new Text({
                text: props.label || `#${feature.getId()}`,
                font: '13px "JetBrains Mono", monospace',
                fill: new Fill({ color: "#FFFFFF" }),
                stroke: new Stroke({ color: "#000000", width: 3 }),
              })
            : undefined,
        });
      },
    });
    map.addInteraction(hoverInteraction);
    hoverRef.current = hoverInteraction;

    return () => {
      if (selectRef.current) {
        map.removeInteraction(selectRef.current);
        selectRef.current = null;
      }
      if (hoverRef.current) {
        map.removeInteraction(hoverRef.current);
        hoverRef.current = null;
      }
    };
  }, [
    mapReady,
    activeTool,
    selectHeap,
    toggleMergeSelection,
    labelsVisible,
  ]);

  return (
    <div className="relative h-full w-full">
      <div ref={mapDivRef} className="h-full w-full bg-evlos-900" />

      {/* Editing toolbar */}
      {mapReady && (
        <div className="absolute top-4 left-4 z-10">
          <EditingToolbar
            disabled={!mapReady}
            mergeDisabled={mergeSelection.length < 2}
          />
        </div>
      )}

      {/* OL editing interactions */}
      {mapReady && mapRef.current && (
        <PolygonEditor
          map={mapRef.current}
          source={heapSourceRef.current}
          surveyId={surveyId}
        />
      )}

      {/* Ground selection tool (F3.S02) */}
      {mapReady && mapRef.current && (
        <GroundSelectionTool
          map={mapRef.current}
          surveyId={surveyId}
        />
      )}

      {/* Cross-section tools */}
      {mapReady && mapRef.current && (
        <CrossSectionDrawTool map={mapRef.current} />
      )}
      {mapReady && mapRef.current && (
        <CrossSectionLayer map={mapRef.current} />
      )}

      {/* Delete dialog + merge handler */}
      {mapReady && <EditingActions surveyId={surveyId} />}

      {/* UTM coordinates display */}
      {coordinate && (
        <div className="absolute bottom-2 right-2 rounded bg-card/90 px-3 py-1.5 text-xs font-mono shadow-md backdrop-blur border border-border">
          E: {coordinate[0].toFixed(2)} m &middot; N:{" "}
          {coordinate[1].toFixed(2)} m
        </div>
      )}
    </div>
  );
}
