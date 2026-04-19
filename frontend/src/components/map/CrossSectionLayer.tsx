/**
 * Renders all cross-section lines on the map as a VectorLayer.
 * Selected section has bolder stroke. Click to select.
 */

import { useEffect, useRef } from "react";
import Feature from "ol/Feature";
import VectorLayer from "ol/layer/Vector";
import VectorSource from "ol/source/Vector";
import GeoJSON from "ol/format/GeoJSON";
import { Style, Stroke, Circle, Fill } from "ol/style";
import Select from "ol/interaction/Select";
import { click } from "ol/events/condition";
import type OlMap from "ol/Map";
import type { FeatureLike } from "ol/Feature";

import { useCrossSectionStore } from "@/stores/crossSectionStore";

interface CrossSectionLayerProps {
  map: OlMap | null;
}

export function CrossSectionLayer({ map }: CrossSectionLayerProps) {
  const sections = useCrossSectionStore((s) => s.sections);
  const selectedId = useCrossSectionStore((s) => s.selectedId);
  const selectSection = useCrossSectionStore((s) => s.select);
  const getColor = useCrossSectionStore((s) => s.getColor);

  const layerRef = useRef<VectorLayer | null>(null);
  const selectRef = useRef<Select | null>(null);

  useEffect(() => {
    if (!map) return;

    const geojsonFmt = new GeoJSON();
    const features = sections
      .map((sec) => {
        try {
          const geom = geojsonFmt.readGeometry(sec.lineGeoJSON);
          const feature = new Feature({ geometry: geom, sectionId: sec.id });
          feature.setId(sec.id);
          return feature;
        } catch {
          return null;
        }
      })
      .filter(Boolean) as Feature[];

    const source = new VectorSource({ features });

    const layer = new VectorLayer({
      source,
      style: (feature: FeatureLike) => {
        const id = feature.getId() as number;
        const isSelected = id === selectedId;
        const color = getColor(id);
        return new Style({
          stroke: new Stroke({
            color,
            width: isSelected ? 4 : 2,
            lineDash: isSelected ? undefined : [6, 4],
          }),
          image: new Circle({
            radius: isSelected ? 5 : 3,
            fill: new Fill({ color }),
            stroke: new Stroke({ color: "#ffffff", width: 1.5 }),
          }),
        });
      },
      zIndex: 50,
    });

    map.addLayer(layer);
    layerRef.current = layer;

    // Click selection
    const selectInteraction = new Select({
      condition: click,
      layers: [layer],
      style: null,
    });
    selectInteraction.on("select", (e) => {
      const selected = e.selected[0];
      if (selected) {
        const sectionId = selected.getId() as number;
        selectSection(sectionId);
      }
      selectInteraction.getFeatures().clear();
    });
    map.addInteraction(selectInteraction);
    selectRef.current = selectInteraction;

    return () => {
      if (layerRef.current) map.removeLayer(layerRef.current);
      if (selectRef.current) map.removeInteraction(selectRef.current);
    };
  }, [map, sections, selectedId, selectSection, getColor]);

  return null;
}
