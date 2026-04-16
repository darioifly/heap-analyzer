import "ol/ol.css";
import { useEffect, useRef, useState, useCallback } from "react";
import OlMap from "ol/Map";
import View from "ol/View";
import TileLayer from "ol/layer/Tile";
import XYZ from "ol/source/XYZ";
import TileGrid from "ol/tilegrid/TileGrid";
import { defaults as defaultControls, ScaleLine } from "ol/control";
import { getUtmProjection } from "@/lib/projections";

interface TileMetadata {
  crs: string;
  bounds: [number, number, number, number];
  origin: [number, number];
  resolutions: number[];
  tileSize: number;
  min_zoom: number;
  max_zoom: number;
}

interface MapViewProps {
  surveyId: number;
  /** Called when the OL map instance is ready. Used by parent to add overlays. */
  onMapReady?: (map: OlMap) => void;
}

export function MapView({ surveyId, onMapReady }: MapViewProps) {
  const mapDivRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<OlMap | null>(null);
  const [coordinate, setCoordinate] = useState<[number, number] | null>(null);

  const handleMapReady = useCallback(
    (map: OlMap) => {
      onMapReady?.(map);
    },
    [onMapReady],
  );

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

      const source = new XYZ({
        projection,
        tileGrid,
        url: `${baseUrl}/tiles/${surveyId}/{z}/{x}/{y}.png`,
        wrapX: false,
      });

      const map = new OlMap({
        target: mapDivRef.current!,
        layers: [new TileLayer({ source })],
        view: new View({
          projection,
          center: [
            (extent[0] + extent[2]) / 2,
            (extent[1] + extent[3]) / 2,
          ],
          extent,
          resolution: metadata.resolutions[0],
          minResolution:
            metadata.resolutions[metadata.resolutions.length - 1],
          maxResolution: metadata.resolutions[0],
        }),
        controls: defaultControls().extend([
          new ScaleLine({ units: "metric" }),
        ]),
      });

      map.on("pointermove", (evt) => {
        setCoordinate(evt.coordinate as [number, number]);
      });

      map.getView().fit(extent, { padding: [20, 20, 20, 20] });
      mapRef.current = map;
      handleMapReady(map);
    })();

    return () => {
      cancelled = true;
      if (mapRef.current) {
        mapRef.current.setTarget(undefined);
        mapRef.current = null;
      }
    };
  }, [surveyId, handleMapReady]);

  return (
    <div className="relative h-full w-full">
      <div ref={mapDivRef} className="h-full w-full bg-evlos-900" />
      {coordinate && (
        <div className="absolute bottom-2 right-2 rounded bg-card/90 px-3 py-1.5 text-xs font-mono shadow-md backdrop-blur border border-border">
          E: {coordinate[0].toFixed(2)} m &middot; N:{" "}
          {coordinate[1].toFixed(2)} m
        </div>
      )}
    </div>
  );
}
