import { MousePointerClick } from "lucide-react";
import { useHeapStore } from "@/stores/heapStore";
import { useSurveyStore } from "@/stores/surveyStore";
import { HeapProperties } from "@/components/heaps/HeapProperties";
import { SurveySummary } from "@/components/heaps/SurveySummary";
import { BaseElevationControl } from "@/components/heaps/BaseElevationControl";
import { Separator } from "@/components/ui/separator";

export function SidebarRight() {
  const selectedHeapId = useHeapStore((s) => s.selectedHeapId);
  const heaps = useHeapStore((s) => s.heaps);
  const selectedHeap = heaps.find((h) => h.id === selectedHeapId);

  const selectedSurveyId = useSurveyStore((s) => s.selectedSurveyId);
  const survey = useSurveyStore((s) =>
    s.surveys.find((sv) => sv.id === s.selectedSurveyId),
  );

  return (
    <div className="flex flex-col h-full border-l border-border">
      {/* Header */}
      <div className="flex items-center px-4 py-3 border-b border-border">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Proprietà
        </h2>
      </div>

      {/* Base Elevation Control — always visible when survey is loaded */}
      {survey && selectedSurveyId && survey.processingStatus === "completed" && (
        <>
          <BaseElevationControl survey={survey} heaps={heaps} />
          <Separator />
        </>
      )}

      {selectedHeap ? (
        <HeapProperties heap={selectedHeap} />
      ) : survey && selectedSurveyId ? (
        <SurveySummary survey={survey} heaps={heaps} />
      ) : (
        <div className="flex flex-col items-center justify-center flex-1 px-4 py-8 text-center">
          <MousePointerClick
            className="text-muted-foreground mb-3"
            size={32}
            strokeWidth={1.75}
          />
          <p className="text-sm text-muted-foreground">
            Seleziona un cumulo per vedere i dettagli
          </p>
        </div>
      )}
    </div>
  );
}
