import { Map } from "lucide-react";
import { useSurveyStore } from "@/stores/surveyStore";
import { MapView } from "@/components/map/MapView";

export function Viewport() {
  const selectedSurveyId = useSurveyStore((s) => s.selectedSurveyId);
  const survey = useSurveyStore((s) =>
    s.surveys.find((sv) => sv.id === s.selectedSurveyId),
  );

  if (selectedSurveyId && survey?.processingStatus === "completed") {
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
