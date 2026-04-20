import { useState } from "react";
import { Loader2, Upload, Plus, FolderInput } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { useSurveyStore } from "@/stores/surveyStore";
import { useProjectStore } from "@/stores/projectStore";
import { SurveyCard } from "./SurveyCard";
import { ImportSurveyDialog } from "./ImportSurveyDialog";
import { ImportDJIDialog } from "./ImportDJIDialog";

interface SurveyListProps {
  onProcessSurvey: (surveyId: number) => void;
}

export function SurveyList({ onProcessSurvey }: SurveyListProps) {
  const selectedProjectId = useProjectStore((s) => s.selectedProjectId);
  const { surveys, selectedSurveyId, isLoading, create, select, loadByProject } =
    useSurveyStore();
  const [importOpen, setImportOpen] = useState(false);
  const [djiImportOpen, setDjiImportOpen] = useState(false);

  if (!selectedProjectId) return null;

  const handleImport = async (data: {
    lasPath: string;
    tiffPath: string;
    surveyDate: string;
    operator: string | null;
  }) => {
    try {
      await create({
        projectId: selectedProjectId,
        lasPath: data.lasPath,
        tiffPath: data.tiffPath,
        surveyDate: data.surveyDate,
        operator: data.operator,
        processingParams: null,
      });
      toast.success("Rilievo importato");
    } catch {
      toast.error("Errore durante l'importazione del rilievo");
    }
  };

  return (
    <>
      <Separator />

      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Rilievi
        </h2>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => setDjiImportOpen(true)}
            aria-label="Importa da DJI Terra"
            title="Importa da DJI Terra"
          >
            <FolderInput size={16} strokeWidth={1.75} />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => setImportOpen(true)}
            aria-label="Nuovo rilievo"
            title="Nuovo rilievo"
          >
            <Plus size={16} strokeWidth={1.75} />
          </Button>
        </div>
      </div>

      <ScrollArea className="flex-1">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2
              className="animate-spin text-muted-foreground"
              size={24}
            />
          </div>
        ) : surveys.length === 0 ? (
          <div className="flex flex-col items-center justify-center px-4 py-6 text-center">
            <Upload
              className="text-muted-foreground mb-2"
              size={24}
              strokeWidth={1.75}
            />
            <p className="text-xs text-muted-foreground mb-2">
              Nessun rilievo. Importa il primo.
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setImportOpen(true)}
            >
              Importa rilievo
            </Button>
          </div>
        ) : (
          <div className="py-1">
            {surveys.map((survey) => (
              <SurveyCard
                key={survey.id}
                survey={survey}
                isSelected={survey.id === selectedSurveyId}
                onClick={() => select(survey.id)}
                onProcess={() => onProcessSurvey(survey.id)}
              />
            ))}
          </div>
        )}
      </ScrollArea>

      <ImportSurveyDialog
        open={importOpen}
        onOpenChange={setImportOpen}
        onImport={handleImport}
      />

      <ImportDJIDialog
        open={djiImportOpen}
        onOpenChange={setDjiImportOpen}
        projectId={selectedProjectId}
        onImported={(surveyId) => {
          loadByProject(selectedProjectId);
          select(surveyId);
        }}
      />
    </>
  );
}
