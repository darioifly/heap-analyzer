import { useState, useEffect, useCallback } from "react";
import { RefreshCw, MapPin, ChevronDown, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import { Separator } from "@/components/ui/separator";
import { useHeapStore } from "@/stores/heapStore";
import { useSurveyStore } from "@/stores/surveyStore";
import { useEditingStore } from "@/stores/editingStore";
import type { Survey, Heap } from "@/types";

interface BaseElevationControlProps {
  survey: Survey;
  heaps: Heap[];
}

export function BaseElevationControl({
  survey,
  heaps,
}: BaseElevationControlProps) {
  const [isOpen, setIsOpen] = useState(true);
  const [isRecalculating, setIsRecalculating] = useState(false);

  // Estimated base from processing params or first heap
  const estimatedBase = getEstimatedBase(survey, heaps);

  // Local slider/input value
  const [localBase, setLocalBase] = useState<number>(
    survey.baseElevation ?? estimatedBase,
  );

  // Suggested base from ground selection
  const suggestedBase = useEditingStore((s) => s.suggestedBaseElevation);
  const setSuggestedBase = useEditingStore(
    (s) => s.setSuggestedBaseElevation,
  );
  const activeTool = useEditingStore((s) => s.activeTool);
  const setTool = useEditingStore((s) => s.setTool);
  const pushHistory = useEditingStore((s) => s.pushHistory);

  const loadBySurvey = useHeapStore((s) => s.loadBySurvey);
  const updateSurvey = useSurveyStore((s) => s.update);

  // Sync localBase when survey changes
  useEffect(() => {
    setLocalBase(survey.baseElevation ?? estimatedBase);
  }, [survey.id, survey.baseElevation, estimatedBase]);

  // Delta and ΔV calculation
  const currentBase = survey.baseElevation ?? estimatedBase;
  const delta = localBase - currentBase;
  const totalArea = heaps
    .filter((h) => !h.isExcluded)
    .reduce((sum, h) => sum + h.planimetricArea, 0);
  const approxDeltaV = -delta * totalArea;

  // Slider range: ±1m from current base
  const sliderMin = currentBase - 1;
  const sliderMax = currentBase + 1;

  const handleSliderChange = useCallback((values: number[]) => {
    setLocalBase(Math.round(values[0] * 100) / 100);
  }, []);

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = parseFloat(e.target.value);
      if (!isNaN(val)) {
        setLocalBase(Math.round(val * 100) / 100);
      }
    },
    [],
  );

  const handleRecalculate = useCallback(async () => {
    setIsRecalculating(true);
    try {
      // Snapshot current heaps for undo
      const before = [...heaps];

      const result = await window.api.elevation.recomputeAll({
        surveyId: survey.id,
        baseElevation: localBase,
      });

      // Refresh heap store
      await loadBySurvey(survey.id);

      // Update survey store to reflect new base_elevation
      await updateSurvey(survey.id, { baseElevation: localBase });

      // Push undo entry
      const after = (result.heaps as Record<string, unknown>[]).map(
        (r) =>
          ({
            id: r.id as number,
            surveyId: r.survey_id as number,
            label: (r.label as string) ?? null,
            volume: r.volume as number,
            planimetricArea: r.planimetric_area as number,
            surfaceArea: r.surface_area as number,
            maxHeight: r.max_height as number,
            meanHeight: r.mean_height as number,
            baseElevation: r.base_elevation as number,
            centroidE: r.centroid_e as number,
            centroidN: r.centroid_n as number,
            bboxMinE: r.bbox_min_e as number,
            bboxMinN: r.bbox_min_n as number,
            bboxMaxE: r.bbox_max_e as number,
            bboxMaxN: r.bbox_max_n as number,
            materialCategory: (r.material_category as string) ?? null,
            materialConfidence: (r.material_confidence as number) ?? null,
            isManuallyConfirmed: Boolean(r.is_manually_confirmed),
            isExcluded: Boolean(r.is_excluded),
            polygon: typeof r.polygon === "string" ? JSON.parse(r.polygon as string) : r.polygon,
            createdAt: r.created_at as string,
            updatedAt: r.updated_at as string,
          }) as Heap,
      );

      pushHistory({
        op: "modify",
        timestamp: Date.now(),
        before,
        after,
        surveyId: survey.id,
      });

      toast.success(
        `Volumi ricalcolati con quota base ${localBase.toFixed(2)} m`,
      );
    } catch (err) {
      toast.error(`Errore ricalcolo: ${String(err)}`);
      setLocalBase(currentBase);
    } finally {
      setIsRecalculating(false);
    }
  }, [
    survey.id,
    localBase,
    currentBase,
    heaps,
    loadBySurvey,
    updateSurvey,
    pushHistory,
  ]);

  const handleGroundSelect = useCallback(() => {
    setTool("ground-select");
  }, [setTool]);

  const handleApplySuggested = useCallback(() => {
    if (suggestedBase != null) {
      setLocalBase(Math.round(suggestedBase * 100) / 100);
      setSuggestedBase(null);
    }
  }, [suggestedBase, setSuggestedBase]);

  // Color for ΔV display
  const absDelta = Math.abs(delta);
  const deltaVColor =
    absDelta < 0.01
      ? "text-evlos-300"
      : absDelta < 0.5
        ? "text-warning-400"
        : "text-danger-400";

  // Method label
  const methodLabel =
    survey.baseElevation != null
      ? "override manuale"
      : "stima automatica";

  return (
    <div className="space-y-0">
      {/* Header */}
      <button
        type="button"
        className="flex w-full items-center gap-2 px-4 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground hover:bg-accent/50 transition-colors"
        onClick={() => setIsOpen(!isOpen)}
      >
        {isOpen ? (
          <ChevronDown size={14} strokeWidth={1.75} />
        ) : (
          <ChevronRight size={14} strokeWidth={1.75} />
        )}
        Quota di base
      </button>

      {isOpen && (
        <div className="px-4 pb-4 space-y-3">
          {/* Method */}
          <div className="flex justify-between items-center">
            <span className="text-xs text-muted-foreground">Metodo</span>
            <span className="text-xs font-mono">{methodLabel}</span>
          </div>

          {/* Input + unit */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">Quota</span>
            <Input
              type="number"
              step={0.01}
              value={localBase.toFixed(2)}
              onChange={handleInputChange}
              className="h-8 bg-evlos-800 border-evlos-600 text-evlos-50 font-mono text-right w-24"
            />
            <span className="text-xs text-muted-foreground">m s.l.m.</span>
          </div>

          {/* Slider */}
          <div className="space-y-1">
            <Slider
              min={sliderMin}
              max={sliderMax}
              step={0.01}
              value={[localBase]}
              onValueChange={handleSliderChange}
            />
            <div className="flex justify-between">
              <span className="text-[10px] font-mono text-muted-foreground">
                {sliderMin.toFixed(2)}
              </span>
              <span className="text-[10px] font-mono text-muted-foreground">
                {sliderMax.toFixed(2)}
              </span>
            </div>
          </div>

          {/* ΔV display */}
          {absDelta >= 0.005 && (
            <div className="space-y-0.5">
              <div className={`font-mono text-lg ${deltaVColor}`}>
                {approxDeltaV >= 0 ? "+" : ""}
                {approxDeltaV.toFixed(1)} m³
              </div>
              <div className="text-[10px] text-muted-foreground">
                ΔV stimato (approssimazione lineare)
              </div>
            </div>
          )}

          {/* Suggested from ground selection */}
          {suggestedBase != null && (
            <div className="flex items-center gap-2 bg-success-900/30 border border-success-700/30 rounded p-2">
              <span className="text-xs text-success-400">
                Suggerito da terreno noto:{" "}
                <span className="font-mono">{suggestedBase.toFixed(2)} m</span>
              </span>
              <Button
                variant="outline"
                size="sm"
                className="h-6 text-xs px-2"
                onClick={handleApplySuggested}
              >
                Applica
              </Button>
            </div>
          )}

          {/* Buttons */}
          <Button
            className="w-full"
            disabled={absDelta < 0.005 || isRecalculating}
            onClick={handleRecalculate}
          >
            {isRecalculating ? (
              <RefreshCw size={14} className="mr-2 animate-spin" strokeWidth={1.75} />
            ) : (
              <RefreshCw size={14} className="mr-2" strokeWidth={1.75} />
            )}
            Ricalcola volumi
          </Button>

          <Button
            variant="outline"
            className="w-full"
            onClick={handleGroundSelect}
            disabled={activeTool === "ground-select"}
          >
            <MapPin size={14} className="mr-2" strokeWidth={1.75} />
            Seleziona terreno noto
          </Button>

          <Separator />

          {/* Warning banner */}
          <div className="bg-warning-900/20 border border-warning-700/30 text-warning-400 text-xs p-2 rounded">
            Variazione ±5cm = ±175 m³ su cumulo tipico 3500 m²
          </div>
        </div>
      )}
    </div>
  );
}

function getEstimatedBase(survey: Survey, heaps: Heap[]): number {
  // Try processing params
  if (survey.processingParams) {
    const params = survey.processingParams;
    if (typeof params === "object" && params !== null) {
      const est = (params as Record<string, unknown>).estimated_base_elevation;
      if (typeof est === "number") return est;
      const base = (params as Record<string, unknown>).base_elevation;
      if (typeof base === "number") return base;
    }
  }
  // Fallback: first heap's base elevation
  if (heaps.length > 0 && heaps[0].baseElevation != null) {
    return heaps[0].baseElevation;
  }
  return 0.0;
}
