/**
 * Report generation dialog.
 * Allows the user to configure and generate a PDF report, CSV, or both.
 */

import { useEffect, useRef, useState } from "react";
import { FolderOpen, ImageIcon, Loader2, X } from "lucide-react";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { useSurveyStore } from "@/stores/surveyStore";
import { useProjectStore } from "@/stores/projectStore";
import { useReportStore, type ReportFormat } from "@/stores/reportStore";

const PHASE_LABELS: Record<string, string> = {
  overview: "Generazione panoramica",
  "heap-sheets": "Schede cumuli",
  summary: "Tabella riepilogativa",
  charts: "Grafici",
  params: "Parametri",
  assemble: "Assemblaggio PDF",
  export: "Esportazione CSV",
};

interface ReportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialFormat?: ReportFormat;
}

export function ReportDialog({
  open,
  onOpenChange,
  initialFormat = "pdf",
}: ReportDialogProps) {
  const [format, setFormat] = useState<ReportFormat>(initialFormat);
  const [destinationDir, setDestinationDir] = useState("");
  const [logoPath, setLogoPath] = useState<string | null>(null);
  const [companyName, setCompanyName] = useState(
    () => localStorage.getItem("heap-analyzer-company") || "",
  );
  const [notes, setNotes] = useState("");
  const [onlyConfirmed, setOnlyConfirmed] = useState(false);

  const survey = useSurveyStore((s) =>
    s.surveys.find((sv) => sv.id === s.selectedSurveyId),
  );
  const project = useProjectStore((s) => s.getSelected());
  const { isGenerating, progress, lastResult, lastError, startGeneration, cancelGeneration, reset } =
    useReportStore();

  const firstInputRef = useRef<HTMLButtonElement>(null);

  // Reset format when dialog opens with new initialFormat
  useEffect(() => {
    if (open) {
      setFormat(initialFormat);
      reset();
    }
  }, [open, initialFormat, reset]);

  // Focus first input on open
  useEffect(() => {
    if (open && firstInputRef.current) {
      setTimeout(() => firstInputRef.current?.focus(), 100);
    }
  }, [open]);

  // Handle completion
  useEffect(() => {
    if (lastResult) {
      const filename = lastResult.paths[0]?.split(/[\\/]/).pop() || "report";
      toast.success(`Report generato: ${filename}`, {
        duration: 8000,
        action: {
          label: "Apri file",
          onClick: () => {
            if (lastResult.paths[0]) {
              window.api.shell.showItemInFolder(lastResult.paths[0]);
            }
          },
        },
      });
      onOpenChange(false);
    }
  }, [lastResult, onOpenChange]);

  // Handle error
  useEffect(() => {
    if (lastError) {
      toast.error(`Errore generazione: ${lastError}`);
    }
  }, [lastError]);

  const handleBrowseDir = async () => {
    const dir = await window.api.dialog.openDirectory({
      title: "Cartella di destinazione",
    });
    if (dir) setDestinationDir(dir);
  };

  const handleBrowseLogo = async () => {
    const file = await window.api.dialog.openFile({
      title: "Seleziona logo",
      filters: [{ name: "Immagini", extensions: ["png", "jpg", "jpeg"] }],
    });
    if (file) setLogoPath(file);
  };

  const handleGenerate = async () => {
    if (!survey || !destinationDir) return;

    // Remember company name
    if (companyName) {
      localStorage.setItem("heap-analyzer-company", companyName);
    }

    await startGeneration({
      surveyId: survey.id,
      format,
      destinationDir,
      logoPath,
      companyName: companyName || null,
      notes: notes || null,
      onlyConfirmed,
    });
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && e.ctrlKey && !isGenerating && destinationDir) {
      handleGenerate();
    }
  };

  if (!survey) return null;

  const canGenerate = !!destinationDir && !isGenerating;

  // Show progress overlay when generating
  if (isGenerating) {
    const phaseLabel = progress
      ? PHASE_LABELS[progress.phase] || progress.phase
      : "Preparazione...";
    const pct = progress?.percent ?? 0;

    return (
      <Dialog open={true} onOpenChange={() => {}}>
        <DialogContent
          className="sm:max-w-[400px]"
          onPointerDownOutside={(e) => e.preventDefault()}
          onEscapeKeyDown={(e) => e.preventDefault()}
        >
          <DialogHeader>
            <DialogTitle>Generazione report in corso...</DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">{phaseLabel}</span>
                <span className="font-mono text-muted-foreground">
                  {pct.toFixed(0)}%
                </span>
              </div>
              <div className="h-2 rounded-full bg-muted overflow-hidden">
                <div
                  className="h-full bg-primary rounded-full transition-all duration-300"
                  style={{ width: `${Math.min(100, pct)}%` }}
                />
              </div>
              {progress?.message && (
                <p className="text-xs text-muted-foreground">
                  {progress.message}
                </p>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={cancelGeneration}>
              Annulla
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-[520px]"
        onKeyDown={handleKeyDown}
      >
        <DialogHeader>
          <DialogTitle>Genera report</DialogTitle>
          <DialogDescription>
            Rilievo del{" "}
            {new Date(survey.surveyDate).toLocaleDateString("it-IT")}
            {project ? ` — ${project.name}` : ""}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Format selection */}
          <div className="space-y-2">
            <Label className="text-sm font-medium">Formato</Label>
            <div className="flex gap-2">
              {(
                [
                  { value: "pdf" as const, label: "Report PDF" },
                  { value: "csv" as const, label: "CSV cumuli" },
                  { value: "pdf+csv" as const, label: "PDF + CSV" },
                ] as const
              ).map((opt) => (
                <Button
                  key={opt.value}
                  ref={opt.value === "pdf" ? firstInputRef : undefined}
                  variant={format === opt.value ? "default" : "outline"}
                  size="sm"
                  onClick={() => setFormat(opt.value)}
                  className="flex-1"
                >
                  {opt.label}
                </Button>
              ))}
            </div>
          </div>

          <div className="border-t border-border" />

          {/* Destination directory */}
          <div className="space-y-2">
            <Label className="text-sm font-medium">
              Cartella di destinazione
            </Label>
            <div className="flex gap-2">
              <Input
                value={destinationDir}
                readOnly
                placeholder="Seleziona una cartella..."
                className="flex-1 text-sm"
              />
              <Button
                variant="outline"
                size="sm"
                onClick={handleBrowseDir}
              >
                <FolderOpen size={14} className="mr-1.5" />
                Sfoglia...
              </Button>
            </div>
          </div>

          {/* Logo (only for PDF formats) */}
          {format !== "csv" && (
            <div className="space-y-2">
              <Label className="text-sm font-medium">Logo (opzionale)</Label>
              <div className="flex items-center gap-2">
                {logoPath ? (
                  <div className="flex items-center gap-2">
                    <div className="w-[60px] h-[60px] rounded border border-border flex items-center justify-center overflow-hidden bg-muted">
                      <ImageIcon size={20} className="text-muted-foreground" />
                    </div>
                    <span className="text-xs text-muted-foreground truncate max-w-[200px]">
                      {logoPath.split(/[\\/]/).pop()}
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setLogoPath(null)}
                    >
                      <X size={12} className="mr-1" />
                      Rimuovi
                    </Button>
                  </div>
                ) : (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleBrowseLogo}
                  >
                    <ImageIcon size={14} className="mr-1.5" />
                    Seleziona logo
                  </Button>
                )}
              </div>
            </div>
          )}

          {/* Company name */}
          {format !== "csv" && (
            <div className="space-y-2">
              <Label className="text-sm font-medium">
                Nome azienda (opzionale)
              </Label>
              <Input
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="Es. Acciaierie Lucchini"
                className="text-sm"
              />
            </div>
          )}

          <div className="border-t border-border" />

          {/* Notes */}
          {format !== "csv" && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-medium">
                  Note aggiuntive (opzionale)
                </Label>
                <span className="text-xs text-muted-foreground">
                  {notes.length}/2000
                </span>
              </div>
              <Textarea
                value={notes}
                onChange={(e) =>
                  setNotes(e.target.value.slice(0, 2000))
                }
                rows={3}
                placeholder="Annotazioni per il report..."
                className="text-sm resize-y max-h-[160px]"
              />
            </div>
          )}

          {/* Only confirmed checkbox */}
          <div className="flex items-center gap-2">
            <Checkbox
              checked={onlyConfirmed}
              onCheckedChange={(v) => setOnlyConfirmed(v === true)}
              id="only-confirmed-report"
            />
            <Label htmlFor="only-confirmed-report" className="text-sm">
              Includi solo cumuli confermati
            </Label>
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            Annulla
          </Button>
          <Button
            onClick={handleGenerate}
            disabled={!canGenerate}
          >
            {isGenerating && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Genera
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
