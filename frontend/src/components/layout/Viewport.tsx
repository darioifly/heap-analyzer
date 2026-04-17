import { Map } from "lucide-react";
import { useSurveyStore } from "@/stores/surveyStore";
import { useUiStore } from "@/stores/uiStore";
import { MapView } from "@/components/map/MapView";
import { PotreeView } from "@/components/three/PotreeView";

export function Viewport() {
  const selectedSurveyId = useSurveyStore((s) => s.selectedSurveyId);
  const survey = useSurveyStore((s) =>
    s.surveys.find((sv) => sv.id === s.selectedSurveyId),
  );
  const viewMode = useUiStore((s) => s.viewMode);

  if (selectedSurveyId && survey?.processingStatus === "completed") {
    if (viewMode === "3d") {
      return <PotreeView surveyId={selectedSurveyId} />;
    }
    return <MapView surveyId={selectedSurveyId} />;
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
