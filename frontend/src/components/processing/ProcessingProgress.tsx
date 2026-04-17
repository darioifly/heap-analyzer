import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { useProcessingStore } from "@/stores/processingStore";

const PHASE_LABELS: Record<string, string> = {
  loading_metadata: "Caricamento metadati",
  generating_dsm: "Generazione DSM",
  estimating_dtm: "Stima quota base",
  computing_ndsm: "Calcolo nDSM",
  segmenting_heaps: "Segmentazione cumuli",
  computing_metrics: "Calcolo volumi e metriche",
  saving_results: "Salvataggio risultati",
  potree_conversion: "Conversione 3D",
};

function formatTime(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  return `${String(min).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

interface ProcessingProgressProps {
  onCancel: () => void;
}

export function ProcessingProgress({ onCancel }: ProcessingProgressProps) {
  const { progress, startTime } = useProcessingStore();

  const percent = progress?.percent ?? 0;
  const phase = progress?.phase ?? "";
  const message = progress?.message ?? "";
  const elapsed = startTime ? Date.now() - startTime : 0;

  const phaseLabel = PHASE_LABELS[phase] ?? phase;

  // ETA: only show if percent > 5 to avoid wildly inaccurate estimates
  let eta = "";
  if (percent > 5 && elapsed > 0) {
    const remaining = (elapsed * (100 - percent)) / percent;
    eta = `~${formatTime(remaining)} rimanenti`;
  }

  return (
    <div className="space-y-4">
      <Progress value={percent} className="h-3" />

      <div className="space-y-2 text-sm">
        <div className="flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
          <span className="font-medium">{phaseLabel}</span>
        </div>

        {message && (
          <p className="text-muted-foreground text-xs">{message}</p>
        )}

        <div className="flex justify-between text-xs text-muted-foreground font-mono">
          <span>{percent.toFixed(0)}%</span>
          <span>{formatTime(elapsed)} trascorsi</span>
          {eta && <span>{eta}</span>}
        </div>
      </div>

      <Button
        variant="destructive"
        size="sm"
        onClick={onCancel}
        className="w-full"
      >
        Annulla elaborazione
      </Button>
    </div>
  );
}
