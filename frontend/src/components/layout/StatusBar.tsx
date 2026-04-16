import { Loader2 } from "lucide-react";
import { useProcessingStore } from "@/stores/processingStore";

const PHASE_LABELS: Record<string, string> = {
  loading_metadata: "Metadati",
  generating_dsm: "DSM",
  estimating_dtm: "DTM",
  computing_ndsm: "nDSM",
  segmenting_heaps: "Segmentazione",
  computing_metrics: "Volumi",
  saving_results: "Salvataggio",
};

export function StatusBar() {
  const { isRunning, progress } = useProcessingStore();

  const phase = progress?.phase ?? "";
  const percent = progress?.percent ?? 0;
  const phaseLabel = PHASE_LABELS[phase] ?? phase;

  return (
    <div className="h-8 shrink-0 bg-muted border-t border-border flex items-center px-4 text-xs text-muted-foreground">
      {/* Left: engine status */}
      <div className="flex items-center gap-2 flex-1">
        <span className="inline-block h-2 w-2 rounded-full bg-success-500" />
        <span>Engine pronto</span>
      </div>

      {/* Center */}
      <div className="flex-1 text-center" />

      {/* Right: processing status */}
      <div className="flex items-center gap-2 flex-1 justify-end">
        {isRunning ? (
          <>
            <Loader2 className="h-3 w-3 animate-spin" />
            <span>
              Elaborazione: {phaseLabel} ({percent.toFixed(0)}%)
            </span>
          </>
        ) : (
          <span>Inattivo</span>
        )}
      </div>
    </div>
  );
}
