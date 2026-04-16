import { useState } from "react";
import { ProjectList } from "@/components/projects/ProjectList";
import { SurveyList } from "@/components/surveys/SurveyList";
import { ProcessingDialog } from "@/components/processing/ProcessingDialog";

export function SidebarLeft() {
  const [processingSurveyId, setProcessingSurveyId] = useState<number | null>(null);

  return (
    <div className="flex flex-col h-full border-r border-border">
      <ProjectList />
      <SurveyList onProcessSurvey={(id) => setProcessingSurveyId(id)} />

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
