/**
 * 3D viewer floating toolbar.
 * Color mode, camera presets, base plane toggle, heap overlay toggle, point budget.
 */

import { ArrowUp, ArrowRight, RotateCcw, Crosshair, Grid3X3, Layers, Thermometer } from "lucide-react";
import { useUiStore } from "@/stores/uiStore";
import { useHeapStore } from "@/stores/heapStore";
import type { ColorMode } from "@/stores/uiStore";

const COLOR_MODE_LABELS: Record<ColorMode, string> = {
  rgb: "RGB originale",
  elevation: "Altezza nDSM",
  heap: "Cumuli",
};

export function Toolbar3D() {
  const colorMode = useUiStore((s) => s.colorMode);
  const setColorMode = useUiStore((s) => s.setColorMode);
  const showBasePlane = useUiStore((s) => s.showBasePlane);
  const toggleBasePlane = useUiStore((s) => s.toggleBasePlane);
  const showHeapOverlay3D = useUiStore((s) => s.showHeapOverlay3D);
  const toggleHeapOverlay3D = useUiStore((s) => s.toggleHeapOverlay3D);
  const showNdsmHeatmap3D = useUiStore((s) => s.showNdsmHeatmap3D);
  const toggleNdsmHeatmap3D = useUiStore((s) => s.toggleNdsmHeatmap3D);
  const pointBudget = useUiStore((s) => s.pointBudget);
  const setPointBudget = useUiStore((s) => s.setPointBudget);
  const applyCameraPreset = useUiStore((s) => s.applyCameraPreset);
  const requestCenterOnSelection = useUiStore((s) => s.requestCenterOnSelection);
  const selectedHeapId = useHeapStore((s) => s.selectedHeapId);

  return (
    <div className="absolute top-4 left-4 z-50 flex flex-col gap-2 w-48">
      {/* Color mode */}
      <div className="bg-evlos-800/90 backdrop-blur-sm rounded-lg border border-evlos-700 p-2">
        <p className="text-xs text-muted-foreground font-semibold uppercase tracking-wider mb-1.5">
          Colorazione
        </p>
        <div className="flex flex-col gap-0.5">
          {(["rgb", "elevation", "heap"] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => setColorMode(mode)}
              className={`text-left text-xs px-2 py-1 rounded transition-colors ${
                colorMode === mode
                  ? "bg-primary text-primary-foreground"
                  : "text-evlos-200 hover:bg-evlos-700"
              }`}
            >
              {COLOR_MODE_LABELS[mode]}
            </button>
          ))}
        </div>
      </div>

      {/* Toggles */}
      <div className="bg-evlos-800/90 backdrop-blur-sm rounded-lg border border-evlos-700 p-2">
        <div className="flex flex-col gap-0.5">
          <button
            onClick={toggleBasePlane}
            className={`flex items-center gap-2 text-xs px-2 py-1 rounded transition-colors ${
              showBasePlane
                ? "bg-evlos-700 text-evlos-100"
                : "text-evlos-400 hover:text-evlos-200"
            }`}
          >
            <Grid3X3 size={14} strokeWidth={1.75} />
            Piano base
          </button>
          <button
            onClick={toggleHeapOverlay3D}
            className={`flex items-center gap-2 text-xs px-2 py-1 rounded transition-colors ${
              showHeapOverlay3D
                ? "bg-evlos-700 text-evlos-100"
                : "text-evlos-400 hover:text-evlos-200"
            }`}
          >
            <Layers size={14} strokeWidth={1.75} />
            Cumuli
          </button>
          <button
            onClick={toggleNdsmHeatmap3D}
            className={`flex items-center gap-2 text-xs px-2 py-1 rounded transition-colors ${
              showNdsmHeatmap3D
                ? "bg-evlos-700 text-evlos-100"
                : "text-evlos-400 hover:text-evlos-200"
            }`}
            title="Sovrapponi heatmap altezza (nDSM) sul piano base"
          >
            <Thermometer size={14} strokeWidth={1.75} />
            Heatmap nDSM
          </button>
        </div>
      </div>

      {/* Camera presets */}
      <div className="bg-evlos-800/90 backdrop-blur-sm rounded-lg border border-evlos-700 p-2">
        <p className="text-xs text-muted-foreground font-semibold uppercase tracking-wider mb-1.5">
          Vista
        </p>
        <div className="flex flex-col gap-0.5">
          <button
            onClick={() => applyCameraPreset("top")}
            className="flex items-center gap-2 text-xs px-2 py-1 rounded text-evlos-200 hover:bg-evlos-700"
          >
            <ArrowUp size={14} strokeWidth={1.75} />
            Dall&apos;alto
          </button>
          <button
            onClick={() => applyCameraPreset("side")}
            className="flex items-center gap-2 text-xs px-2 py-1 rounded text-evlos-200 hover:bg-evlos-700"
          >
            <ArrowRight size={14} strokeWidth={1.75} />
            Laterale
          </button>
          <button
            onClick={() => applyCameraPreset("orbit")}
            className="flex items-center gap-2 text-xs px-2 py-1 rounded text-evlos-200 hover:bg-evlos-700"
          >
            <RotateCcw size={14} strokeWidth={1.75} />
            Reset
          </button>
          <button
            onClick={requestCenterOnSelection}
            disabled={selectedHeapId == null}
            className={`flex items-center gap-2 text-xs px-2 py-1 rounded ${
              selectedHeapId != null
                ? "text-evlos-200 hover:bg-evlos-700"
                : "text-evlos-600 cursor-not-allowed"
            }`}
            title={selectedHeapId == null ? "Seleziona un cumulo" : "Centra sulla selezione"}
          >
            <Crosshair size={14} strokeWidth={1.75} />
            Centra
          </button>
        </div>
      </div>

      {/* Point budget */}
      <div className="bg-evlos-800/90 backdrop-blur-sm rounded-lg border border-evlos-700 p-2">
        <p className="text-xs text-muted-foreground font-semibold uppercase tracking-wider mb-1.5">
          Punti: {(pointBudget / 1_000_000).toFixed(1)}M
        </p>
        <input
          type="range"
          min={200_000}
          max={5_000_000}
          step={100_000}
          value={pointBudget}
          onChange={(e) => setPointBudget(Number(e.target.value))}
          className="w-full h-1.5 accent-primary"
        />
      </div>
    </div>
  );
}
