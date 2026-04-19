/**
 * Floating panel for cross-section profile display.
 * Anchored to bottom of viewport. Shows chart, stats, band-width slider.
 */

import { useState } from "react";
import { X, ChevronDown, Trash2 } from "lucide-react";
import { useCrossSectionStore, type CrossSectionFull } from "@/stores/crossSectionStore";
import { CrossSectionChart } from "./CrossSectionChart";

export function CrossSectionPanel() {
  const panelOpen = useCrossSectionStore((s) => s.panelOpen);
  const setPanelOpen = useCrossSectionStore((s) => s.setPanelOpen);
  const sections = useCrossSectionStore((s) => s.sections);
  const selectedId = useCrossSectionStore((s) => s.selectedId);
  const selectSection = useCrossSectionStore((s) => s.select);
  const getFull = useCrossSectionStore((s) => s.getFull);
  const updateBandWidth = useCrossSectionStore((s) => s.updateBandWidth);
  const updateLabel = useCrossSectionStore((s) => s.updateLabel);
  const removeSection = useCrossSectionStore((s) => s.remove);

  const [editingLabel, setEditingLabel] = useState(false);
  const [labelValue, setLabelValue] = useState("");

  if (!panelOpen || sections.length === 0) return null;

  const selected = selectedId != null ? sections.find((s) => s.id === selectedId) : null;
  const full: CrossSectionFull | undefined = selectedId != null ? getFull(selectedId) : undefined;

  const sectionArea = selected?.sectionArea ?? 0;
  const bandWidth = selected?.bandWidth ?? 1.0;
  const volume = sectionArea * bandWidth;

  const handleLabelSubmit = () => {
    if (selectedId != null && labelValue.trim()) {
      updateLabel(selectedId, labelValue.trim());
    }
    setEditingLabel(false);
  };

  return (
    <div className="absolute bottom-0 left-0 right-0 z-40 bg-evlos-900/95 backdrop-blur-sm border-t border-evlos-700"
      style={{ height: 280 }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-evlos-700">
        <div className="flex items-center gap-3">
          {/* Section selector */}
          <div className="flex items-center gap-1">
            <span className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">
              Sezione:
            </span>
            <div className="relative">
              <select
                value={selectedId ?? ""}
                onChange={(e) => {
                  const id = Number(e.target.value);
                  if (id) selectSection(id);
                }}
                className="bg-evlos-800 text-evlos-200 text-xs border border-evlos-600 rounded px-2 py-1 pr-6 appearance-none cursor-pointer"
              >
                {sections.map((sec, idx) => (
                  <option key={sec.id} value={sec.id}>
                    {sec.label || `Sezione ${idx + 1}`}
                  </option>
                ))}
              </select>
              <ChevronDown
                size={12}
                className="absolute right-1.5 top-1/2 -translate-y-1/2 text-evlos-400 pointer-events-none"
              />
            </div>
          </div>

          {/* Rename */}
          {selected && !editingLabel && (
            <button
              onClick={() => {
                setLabelValue(selected.label || "");
                setEditingLabel(true);
              }}
              className="text-xs text-evlos-400 hover:text-evlos-200"
            >
              rinomina
            </button>
          )}
          {editingLabel && (
            <input
              autoFocus
              value={labelValue}
              onChange={(e) => setLabelValue(e.target.value)}
              onBlur={handleLabelSubmit}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleLabelSubmit();
                if (e.key === "Escape") setEditingLabel(false);
              }}
              className="bg-evlos-800 text-evlos-200 text-xs border border-evlos-600 rounded px-2 py-0.5 w-32"
            />
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Delete */}
          {selectedId != null && (
            <button
              onClick={() => removeSection(selectedId)}
              className="text-evlos-400 hover:text-danger"
              title="Elimina sezione"
            >
              <Trash2 size={14} strokeWidth={1.75} />
            </button>
          )}
          {/* Close */}
          <button
            onClick={() => setPanelOpen(false)}
            className="text-evlos-400 hover:text-evlos-100"
          >
            <X size={14} strokeWidth={1.75} />
          </button>
        </div>
      </div>

      {/* Chart area */}
      <div className="flex-1" style={{ height: 180 }}>
        {full ? (
          <CrossSectionChart profile={full.profile} />
        ) : (
          <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
            {selectedId != null ? "Caricamento profilo…" : "Seleziona una sezione"}
          </div>
        )}
      </div>

      {/* Stats bar */}
      <div className="flex items-center justify-between px-4 py-1.5 border-t border-evlos-700 text-xs font-mono text-evlos-300">
        <div className="flex items-center gap-4">
          <span>L: {(selected?.length ?? 0).toFixed(1)} m</span>
          <span>H max: {(selected?.maxHeight ?? 0).toFixed(2)} m</span>
          <span>Area: {sectionArea.toFixed(1)} m²</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-evlos-400">Corridoio:</span>
          <input
            type="range"
            min={0.1}
            max={10}
            step={0.1}
            value={bandWidth}
            onChange={(e) => {
              if (selectedId != null) updateBandWidth(selectedId, Number(e.target.value));
            }}
            className="w-20 h-1 accent-primary"
          />
          <span className="w-12 text-right">{bandWidth.toFixed(1)} m</span>
          <span className="text-evlos-200">
            Volume: {volume.toFixed(1)} m³
          </span>
        </div>
      </div>
    </div>
  );
}
