/**
 * Cross-section line drawing tool.
 * When activeTool === 'cross-section', enables a 2-point LineString draw on the map.
 * On draw end, calls Python extraction and creates a new cross section.
 */

import { useEffect, useRef } from "react";
import { Draw } from "ol/interaction";
import { Style, Stroke, Circle, Fill } from "ol/style";
import GeoJSON from "ol/format/GeoJSON";
import type OlMap from "ol/Map";
import type { DrawEvent } from "ol/interaction/Draw";

import { useEditingStore } from "@/stores/editingStore";
import { useSurveyStore } from "@/stores/surveyStore";
import { useCrossSectionStore } from "@/stores/crossSectionStore";

const drawStyle = new Style({
  stroke: new Stroke({ color: "#f59e0b", width: 3, lineDash: [6, 4] }),
  image: new Circle({
    radius: 5,
    fill: new Fill({ color: "#f59e0b" }),
    stroke: new Stroke({ color: "#ffffff", width: 2 }),
  }),
});

interface CrossSectionDrawToolProps {
  map: OlMap | null;
}

export function CrossSectionDrawTool({ map }: CrossSectionDrawToolProps) {
  const activeTool = useEditingStore((s) => s.activeTool);
  const setTool = useEditingStore((s) => s.setTool);
  const selectedSurveyId = useSurveyStore((s) => s.selectedSurveyId);
  const createSection = useCrossSectionStore((s) => s.create);
  const drawRef = useRef<Draw | null>(null);

  useEffect(() => {
    if (!map || activeTool !== "cross-section") return;

    const draw = new Draw({
      type: "LineString",
      maxPoints: 2,
      style: drawStyle,
    });

    draw.on("drawend", (event: DrawEvent) => {
      const geojsonFmt = new GeoJSON();
      const geom = event.feature.getGeometry();
      if (!geom || !selectedSurveyId) return;

      const geojsonStr = geojsonFmt.writeGeometry(geom);

      // Fire-and-forget: create section in background
      createSection(selectedSurveyId, geojsonStr).catch((err) => {
        console.error("Cross section creation failed:", err);
      });

      // Return to select tool after drawing
      setTimeout(() => setTool("select"), 100);
    });

    map.addInteraction(draw);
    drawRef.current = draw;

    return () => {
      if (drawRef.current) {
        map.removeInteraction(drawRef.current);
        drawRef.current = null;
      }
    };
  }, [map, activeTool, selectedSurveyId, createSection, setTool]);

  return null;
}
