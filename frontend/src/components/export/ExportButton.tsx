import { useState } from "react";
import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useSurveyStore } from "@/stores/surveyStore";
import { ExportDialog } from "./ExportDialog";

export function ExportButton() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const survey = useSurveyStore((s) =>
    s.surveys.find((sv) => sv.id === s.selectedSurveyId),
  );

  const disabled = !survey || survey.processingStatus !== "completed";

  return (
    <>
      <Button
        variant="outline"
        size="sm"
        className="text-white border-white/20 hover:bg-white/10"
        disabled={disabled}
        onClick={() => setDialogOpen(true)}
      >
        <Download size={14} className="mr-1.5" strokeWidth={1.75} />
        Esporta CSV
      </Button>

      <ExportDialog open={dialogOpen} onOpenChange={setDialogOpen} />
    </>
  );
}
