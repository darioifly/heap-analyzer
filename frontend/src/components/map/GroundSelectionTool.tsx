import { useEffect, useRef, useCallback } from "react";
import type OlMap from "ol/Map";
import Draw from "ol/interaction/Draw";
import VectorSource from "ol/source/Vector";
import VectorLayer from "ol/layer/Vector";
import GeoJSON from "ol/format/GeoJSON";
import { Style, Stroke, Fill } from "ol/style";
import { toast } from "sonner";
import { useEditingStore } from "@/stores/editingStore";
import { useSurveyStore } from "@/stores/surveyStore";

const GROUND_STROKE_COLOR = "#22c55e";
const GROUND_FILL_COLOR = "rgba(34, 197, 94, 0.08)";

const groundStyle = new Style({
  stroke: new Stroke({
    color: GROUND_STROKE_COLOR,
    width: 2,
    lineDash: [8, 4],
  }),
  fill: new Fill({ color: GROUND_FILL_COLOR }),
});

const geoJSONFormat = new GeoJSON();

interface GroundSelectionToolProps {
  map: OlMap;
  surveyId: number;
}

export function GroundSelectionTool({
  map,
  surveyId,
}: GroundSelectionToolProps) {
  const drawRef = useRef<Draw | null>(null);
  const sourceRef = useRef<VectorSource | null>(null);
  const layerRef = useRef<VectorLayer | null>(null);
  const wasActiveRef = useRef(false);

  const activeTool = useEditingStore((s) => s.activeTool);
  const setSuggestedBase = useEditingStore(
    (s) => s.setSuggestedBaseElevation,
  );

  const survey = useSurveyStore((s) =>
    s.surveys.find((sv) => sv.id === surveyId),
  );

  const cleanup = useCallback(() => {
    if (drawRef.current) {
      map.removeInteraction(drawRef.current);
      drawRef.current = null;
    }
    if (layerRef.current) {
      map.removeLayer(layerRef.current);
      layerRef.current = null;
    }
    sourceRef.current = null;
  }, [map]);

  // Sample ground when deactivating with polygons
  const sampleAndSuggest = useCallback(async () => {
    const source = sourceRef.current;
    if (!source || source.getFeatures().length === 0) return;
    if (!survey) return;

    const features = source.getFeatures();
    const polygonsGeoJSON = features.map((f) => {
      const geom = f.getGeometry();
      if (!geom) return null;
      return JSON.parse(
        geoJSONFormat.writeGeometry(geom),
      ) as Record<string, unknown>;
    }).filter(Boolean) as Record<string, unknown>[];

    if (polygonsGeoJSON.length === 0) return;

    try {
      const result = await window.api.elevation.sampleGround({
        surveyId,
        polygonsGeoJSON,
      });

      if ("error" in result) {
        toast.error(`Errore campionamento: ${String((result as Record<string, unknown>).error)}`);
        return;
      }

      const mean = result.mean_elevation;
      const std = result.std_elevation;
      const numPixels = result.num_pixels;

      toast.info(
        `Quota stimata dal terreno: ${mean.toFixed(2)} m (σ = ${std.toFixed(3)} m, ${numPixels} pixel)`,
      );

      if (std > 0.15) {
        toast.warning(
          `Attenzione: alta variabilità nel terreno selezionato (σ = ${std.toFixed(2)} m). Valutare se le aree scelte sono realmente terreno.`,
        );
      }

      setSuggestedBase(mean);
    } catch (err) {
      toast.error(`Errore campionamento terreno: ${String(err)}`);
    }
  }, [surveyId, survey, setSuggestedBase]);

  useEffect(() => {
    const isActive = activeTool === "ground-select";

    if (isActive && !wasActiveRef.current) {
      // Activate: create source, layer, draw interaction
      const source = new VectorSource();
      sourceRef.current = source;

      const layer = new VectorLayer({
        source,
        style: groundStyle,
        zIndex: 200,
      });
      layerRef.current = layer;
      map.addLayer(layer);

      const draw = new Draw({
        source,
        type: "Polygon",
        style: groundStyle,
      });
      drawRef.current = draw;
      map.addInteraction(draw);
    } else if (!isActive && wasActiveRef.current) {
      // Deactivate: sample ground if polygons exist, then cleanup
      sampleAndSuggest().finally(() => {
        cleanup();
      });
    }

    wasActiveRef.current = isActive;

    return () => {
      // Component unmount cleanup
      if (drawRef.current) {
        map.removeInteraction(drawRef.current);
        drawRef.current = null;
      }
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
        layerRef.current = null;
      }
    };
  }, [activeTool, map, sampleAndSuggest, cleanup]);

  // No visible UI — this component manages OL interactions
  return null;
}
