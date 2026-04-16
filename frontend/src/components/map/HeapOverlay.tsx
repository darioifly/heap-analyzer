import { useEffect, useRef } from "react";
import type OlMap from "ol/Map";
import Feature from "ol/Feature";
import { Polygon } from "ol/geom";
import VectorLayer from "ol/layer/Vector";
import VectorSource from "ol/source/Vector";
import { Style, Fill, Stroke, Text } from "ol/style";
import Select from "ol/interaction/Select";
import { click, pointerMove } from "ol/events/condition";
import type { FeatureLike } from "ol/Feature";
import type { Heap } from "@/types";
import { useMapStore } from "@/stores/mapStore";

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

interface HeapOverlayProps {
  map: OlMap;
  heaps: Heap[];
  selectedHeapId: number | null;
  onSelect: (heapId: number | null) => void;
}

export function HeapOverlay({
  map,
  heaps,
  selectedHeapId,
  onSelect,
}: HeapOverlayProps) {
  const layerRef = useRef<VectorLayer | null>(null);
  const selectRef = useRef<Select | null>(null);
  const hoverRef = useRef<Select | null>(null);
  const visible = useMapStore((s) => s.heapsVisible);
  const opacity = useMapStore((s) => s.heapsOpacity);
  const labelsVisible = useMapStore((s) => s.labelsVisible);

  useEffect(() => {
    const features = heaps.map((heap) => {
      const coords = heap.polygon?.coordinates;
      const geom = coords ? new Polygon(coords) : undefined;
      const feature = new Feature({
        geometry: geom,
        heapId: heap.id,
        label: heap.label,
        category: heap.materialCategory,
        volume: heap.volume,
      });
      feature.setId(heap.id);
      return feature;
    });

    const source = new VectorSource({ features });

    const styleFunction = (
      feature: FeatureLike,
    ): Style => {
      const props = feature.getProperties();
      const color = getColor(props.category);
      const isSelected = feature.getId() === selectedHeapId;
      const strokeWidth = isSelected ? 3 : 2;
      const fillAlpha = isSelected ? 0.35 : 0.25;
      const strokeColor = isSelected ? "#F9FAFB" : color;

      return new Style({
        stroke: new Stroke({ color: strokeColor, width: strokeWidth }),
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
    };

    const layer = new VectorLayer({
      source,
      style: styleFunction,
      visible,
      opacity,
    });

    map.addLayer(layer);
    layerRef.current = layer;

    // Click selection
    const selectInteraction = new Select({
      condition: click,
      layers: [layer],
    });
    selectInteraction.on("select", (e) => {
      const selected = e.selected[0];
      onSelect(selected ? (selected.getId() as number) : null);
    });
    map.addInteraction(selectInteraction);
    selectRef.current = selectInteraction;

    // Hover highlight
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
      if (layerRef.current) map.removeLayer(layerRef.current);
      if (selectRef.current) map.removeInteraction(selectRef.current);
      if (hoverRef.current) map.removeInteraction(hoverRef.current);
    };
  }, [map, heaps, selectedHeapId, onSelect, visible, opacity, labelsVisible]);

  // Reactively update visibility/opacity
  useEffect(() => {
    if (layerRef.current) {
      layerRef.current.setVisible(visible);
      layerRef.current.setOpacity(opacity);
    }
  }, [visible, opacity]);

  return null;
}
