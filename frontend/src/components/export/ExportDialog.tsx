import { useState, useMemo } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { useSurveyStore } from "@/stores/surveyStore";
import { useHeapStore } from "@/stores/heapStore";
import { useProjectStore } from "@/stores/projectStore";

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("it-IT", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function sanitizeFilename(s: string): string {
  return s.replace(/[^a-zA-Z0-9_\-. ]/g, "_").replace(/\s+/g, "_");
}

interface ExportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ExportDialog({ open, onOpenChange }: ExportDialogProps) {
  const [onlyConfirmed, setOnlyConfirmed] = useState(false);
  const [excludeMarked, setExcludeMarked] = useState(true);
  const [exporting, setExporting] = useState(false);

  const survey = useSurveyStore((s) =>
    s.surveys.find((sv) => sv.id === s.selectedSurveyId),
  );
  const heaps = useHeapStore((s) => s.heaps);
  const project = useProjectStore((s) => s.getSelected());

  const filteredCount = useMemo(() => {
    return heaps.filter((h) => {
      if (excludeMarked && h.isExcluded) return false;
      if (onlyConfirmed && !h.isManuallyConfirmed) return false;
      return true;
    }).length;
  }, [heaps, excludeMarked, onlyConfirmed]);

  const handleExport = async () => {
    if (!survey) return;

    const defaultName = sanitizeFilename(
      `cumuli_${survey.surveyDate}_${project?.name ?? "export"}.csv`,
    );

    const savePath = await window.api.dialog.saveFile({
      title: "Esporta CSV",
      defaultPath: defaultName,
      filters: [{ name: "CSV", extensions: ["csv"] }],
    });

    if (!savePath) return;

    setExporting(true);
    try {
      // Use existing results.json from processing output directory
      const outputDir = survey.lasPath.replace(/[/\\][^/\\]+$/, "/output");
      await window.api.python.execute("export-csv", [
        "--results", `${outputDir}/results.json`,
        "--output", savePath,
        "--survey-date", survey.surveyDate,
      ]);

      toast.success(`Esportati ${filteredCount} cumuli`, {
        action: {
          label: "Apri cartella",
          onClick: () => window.api.shell.showItemInFolder(savePath),
        },
      });
      onOpenChange(false);
    } catch (err) {
      toast.error(`Errore durante l'esportazione: ${String(err)}`);
    } finally {
      setExporting(false);
    }
  };

  if (!survey) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[420px]">
        <DialogHeader>
          <DialogTitle>Esporta CSV cumuli</DialogTitle>
          <DialogDescription>
            Rilievo del {formatDate(survey.surveyDate)} — {heaps.length} cumuli
            totali
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <Checkbox
              checked={onlyConfirmed}
              onCheckedChange={(v) => setOnlyConfirmed(v === true)}
              id="only-confirmed"
            />
            <Label htmlFor="only-confirmed" className="text-sm">
              Solo cumuli confermati manualmente
            </Label>
          </div>

          <div className="flex items-center gap-2">
            <Checkbox
              checked={excludeMarked}
              onCheckedChange={(v) => setExcludeMarked(v === true)}
              id="exclude-marked"
            />
            <Label htmlFor="exclude-marked" className="text-sm">
              Escludi cumuli marcati come esclusi
            </Label>
          </div>

          <p className="text-sm text-muted-foreground">
            Verranno esportati{" "}
            <span className="font-mono font-medium text-foreground">
              {filteredCount}
            </span>{" "}
            cumuli
          </p>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={exporting}
          >
            Annulla
          </Button>
          <Button
            onClick={handleExport}
            disabled={exporting || filteredCount === 0}
          >
            {exporting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Esporta
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
