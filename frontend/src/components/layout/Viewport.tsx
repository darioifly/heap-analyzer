import { Map } from "lucide-react";
import { useSurveyStore } from "@/stores/surveyStore";
import { useUiStore } from "@/stores/uiStore";
import { MapView } from "@/components/map/MapView";
import { PotreeView } from "@/components/three/PotreeView";
import { CrossSectionPanel } from "@/components/charts/CrossSectionPanel";

export function Viewport() {
  const selectedSurveyId = useSurveyStore((s) => s.selectedSurveyId);
  const survey = useSurveyStore((s) =>
    s.surveys.find((sv) => sv.id === s.selectedSurveyId),
  );
  const viewMode = useUiStore((s) => s.viewMode);

  if (selectedSurveyId && survey?.processingStatus === "completed") {
    return (
      <div className="relative h-full w-full">
        {viewMode === "3d" ? (
          <PotreeView surveyId={selectedSurveyId} />
        ) : (
          <MapView surveyId={selectedSurveyId} />
        )}
        <CrossSectionPanel />
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center h-full text-center">
      <Map
        className="text-muted-foreground mb-3"
        size={48}
        strokeWidth={1.75}
      />
      <p className="text-sm text-muted-foreground">
        {survey?.processingStatus === "pending" || survey?.processingStatus === "error"
          ? "Elaborazione necessaria per visualizzare la mappa"
          : "Importa un rilievo per visualizzare la mappa"}
      </p>
    </div>
  );
}
