import { useState, useEffect } from "react";
import { ProjectList } from "@/components/projects/ProjectList";
import { SurveyList } from "@/components/surveys/SurveyList";
import { HeapList } from "@/components/heaps/HeapList";
import { ProcessingDialog } from "@/components/processing/ProcessingDialog";
import { useSurveyStore } from "@/stores/surveyStore";
import { useHeapStore } from "@/stores/heapStore";

export function SidebarLeft() {
  const [processingSurveyId, setProcessingSurveyId] = useState<number | null>(null);

  const selectedSurveyId = useSurveyStore((s) => s.selectedSurveyId);
  const survey = useSurveyStore((s) =>
    s.surveys.find((sv) => sv.id === s.selectedSurveyId),
  );
  const heaps = useHeapStore((s) => s.heaps);
  const loadHeaps = useHeapStore((s) => s.loadBySurvey);
  const selectHeap = useHeapStore((s) => s.select);

  // Load heaps when a completed survey is selected
  useEffect(() => {
    if (selectedSurveyId && survey?.processingStatus === "completed") {
      loadHeaps(selectedSurveyId);
    }
  }, [selectedSurveyId, survey?.processingStatus, loadHeaps]);

  return (
    <div className="flex flex-col h-full border-r border-border">
      <ProjectList />
      <SurveyList onProcessSurvey={(id) => setProcessingSurveyId(id)} />
      <HeapList heaps={heaps} onSelect={(id) => selectHeap(id)} />

      <ProcessingDialog
        surveyId={processingSurveyId}
        open={processingSurveyId !== null}
        onOpenChange={(open) => {
          if (!open) setProcessingSurveyId(null);
        }}
      />
    </div>
  );
}
