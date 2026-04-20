import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  FolderInput,
  Loader2,
  XCircle,
} from "lucide-react";
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
import { Checkbox } from "@/components/ui/checkbox";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import type { DJITerraManifest } from "@/types/dji";

type Step = "select" | "scanning" | "review" | "importing";

interface ImportDJIDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: number;
  onImported: (surveyId: number) => void;
}

function truncateMiddle(p: string, maxLen = 60): string {
  if (p.length <= maxLen) return p;
  const keep = Math.floor((maxLen - 3) / 2);
  return p.slice(0, keep) + "..." + p.slice(p.length - keep);
}

function todayIso(): string {
  return new Date().toISOString().split("T")[0];
}

export function ImportDJIDialog({
  open,
  onOpenChange,
  projectId,
  onImported,
}: ImportDJIDialogProps) {
  const [step, setStep] = useState<Step>("select");
  const [folderPath, setFolderPath] = useState<string>("");
  const [manifest, setManifest] = useState<DJITerraManifest | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);
  const [useDjiDsm, setUseDjiDsm] = useState(true);
  const [copyFiles, setCopyFiles] = useState(false);
  const [surveyDate, setSurveyDate] = useState(todayIso());
  const [operator, setOperator] = useState("");

  const reset = () => {
    setStep("select");
    setFolderPath("");
    setManifest(null);
    setScanError(null);
    setUseDjiDsm(true);
    setCopyFiles(false);
    setSurveyDate(todayIso());
    setOperator("");
  };

  const handleOpenChange = (value: boolean) => {
    if (!value) reset();
    onOpenChange(value);
  };

  const pickFolder = async () => {
    const path = await window.api.dialog.openDirectory({
      title: "Seleziona cartella DJI Terra",
    });
    if (!path) return;
    setFolderPath(path);
    setScanError(null);
    setStep("scanning");

    const response = await window.api.dji.scanFolder({ folderPath: path });
    if (response.ok) {
      setManifest(response.manifest);
      if (response.manifest.survey_date) {
        setSurveyDate(response.manifest.survey_date);
      }
      setStep("review");
    } else {
      setScanError(response.message);
      setStep("select");
    }
  };

  const handleImport = async () => {
    if (!manifest) return;
    setStep("importing");
    try {
      const { surveyId } = await window.api.dji.importSurvey({
        projectId,
        folderPath,
        manifest,
        useDjiDsm,
        copyFiles,
        surveyDate,
        operator: operator.trim(),
      });
      toast.success("Rilievo DJI Terra importato");
      onImported(surveyId);
      handleOpenChange(false);
    } catch (err) {
      toast.error(
        err instanceof Error
          ? `Importazione fallita: ${err.message}`
          : "Importazione fallita",
      );
      setStep("review");
    }
  };

  const busy = step === "scanning" || step === "importing";
  const canImport =
    step === "review" && manifest !== null && surveyDate !== "";

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[640px]">
        <DialogHeader>
          <DialogTitle>Importa rilievo da DJI Terra</DialogTitle>
          <DialogDescription>
            Seleziona la cartella radice del progetto DJI Terra (contiene{" "}
            <code className="font-mono text-xs">map/</code>,{" "}
            <code className="font-mono text-xs">models/</code>, ...).
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Step A — folder selection */}
          {step === "select" && (
            <div className="space-y-3">
              <Button
                variant="outline"
                className="w-full h-24 border-dashed"
                onClick={pickFolder}
              >
                <FolderInput className="mr-2" size={20} strokeWidth={1.75} />
                Seleziona cartella
              </Button>
              {scanError && (
                <Alert variant="destructive">
                  <XCircle className="h-4 w-4" />
                  <AlertTitle>Scansione fallita</AlertTitle>
                  <AlertDescription>{scanError}</AlertDescription>
                </Alert>
              )}
            </div>
          )}

          {/* Scanning state */}
          {step === "scanning" && (
            <div className="flex items-center gap-3 py-8 justify-center text-sm text-muted-foreground">
              <Loader2 className="animate-spin" size={18} />
              <span>
                Analisi cartella in corso…{" "}
                <span className="font-mono text-xs">
                  {truncateMiddle(folderPath, 40)}
                </span>
              </span>
            </div>
          )}

          {/* Step B — manifest preview */}
          {step === "review" && manifest && (
            <>
              {manifest.warnings.length > 0 && (
                <Alert className="border-warning-500 bg-warning-50 dark:bg-warning-900/20">
                  <AlertTriangle className="h-4 w-4 text-warning-600" />
                  <AlertTitle className="text-warning-700 dark:text-warning-400">
                    Avvisi dalla scansione
                  </AlertTitle>
                  <AlertDescription>
                    <ul className="list-disc pl-4 mt-1 space-y-1 text-xs">
                      {manifest.warnings.map((w, i) => (
                        <li key={i}>{w}</li>
                      ))}
                    </ul>
                  </AlertDescription>
                </Alert>
              )}

              <div className="rounded-md border border-border overflow-hidden text-xs">
                <table className="w-full">
                  <tbody>
                    <ManifestRow
                      label="Ortofoto"
                      value={truncateMiddle(manifest.orthophoto_path)}
                      status="ok"
                    />
                    <ManifestRow
                      label="DSM"
                      value={truncateMiddle(manifest.dsm_path)}
                      status="ok"
                    />
                    <ManifestRow
                      label="Nuvola di punti"
                      value={truncateMiddle(manifest.las_path)}
                      status="ok"
                    />
                    <ManifestRow
                      label="Classificazione terreno"
                      value={
                        manifest.has_ground_classification
                          ? "in cloud_merged.las"
                          : "assente"
                      }
                      status={manifest.has_ground_classification ? "ok" : "muted"}
                    />
                    <ManifestRow
                      label="CRS rilevato"
                      value={manifest.crs ?? "—"}
                      status={manifest.crs ? "ok" : "muted"}
                    />
                    <ManifestRow
                      label="Data rilievo"
                      value={manifest.survey_date ?? "—"}
                      status="ok"
                    />
                  </tbody>
                </table>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label htmlFor="dji-survey-date">Data rilievo</Label>
                  <Input
                    id="dji-survey-date"
                    type="date"
                    value={surveyDate}
                    onChange={(e) => setSurveyDate(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="dji-operator">Operatore</Label>
                  <Input
                    id="dji-operator"
                    value={operator}
                    onChange={(e) => setOperator(e.target.value)}
                    placeholder="Es. Mario Rossi"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label className="flex items-start gap-2 text-sm cursor-pointer">
                  <Checkbox
                    checked={useDjiDsm}
                    onCheckedChange={(v) => setUseDjiDsm(Boolean(v))}
                    className="mt-0.5"
                  />
                  <span>
                    <span className="font-medium">
                      Usa DSM di DJI Terra (salta generazione)
                    </span>
                    <span className="block text-xs text-muted-foreground mt-0.5">
                      Riduce il tempo di elaborazione di ~60% riusando{" "}
                      <code className="font-mono">map/dsm.tif</code>.
                    </span>
                  </span>
                </label>

                <label className="flex items-start gap-2 text-sm cursor-pointer">
                  <Checkbox
                    checked={copyFiles}
                    onCheckedChange={(v) => setCopyFiles(Boolean(v))}
                    className="mt-0.5"
                  />
                  <span>
                    <span className="font-medium">
                      Copia i file nella cartella del progetto
                    </span>
                    <span className="block text-xs text-muted-foreground mt-0.5">
                      Se disabilitato, il progetto referenzia i file nella loro
                      posizione originale. Spostando la cartella DJI il rilievo
                      diventa illeggibile.
                    </span>
                  </span>
                </label>
              </div>
            </>
          )}

          {/* Importing state */}
          {step === "importing" && (
            <div className="flex items-center gap-3 py-8 justify-center text-sm text-muted-foreground">
              <Loader2 className="animate-spin" size={18} />
              <span>
                {copyFiles ? "Copia file in corso…" : "Creazione rilievo…"}
              </span>
            </div>
          )}
        </div>

        <DialogFooter className="gap-2">
          <Button
            variant="ghost"
            onClick={() => handleOpenChange(false)}
            disabled={busy}
          >
            Annulla
          </Button>
          <Button onClick={handleImport} disabled={!canImport || busy}>
            Importa rilievo
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ManifestRow({
  label,
  value,
  status,
}: {
  label: string;
  value: string;
  status: "ok" | "muted";
}) {
  return (
    <tr className="border-b border-border last:border-b-0">
      <td className="px-3 py-2 text-muted-foreground whitespace-nowrap">
        {label}
      </td>
      <td className="px-3 py-2 font-mono text-[11px]">{value}</td>
      <td className="px-3 py-2 w-6">
        {status === "ok" ? (
          <CheckCircle2 size={14} className="text-success-600" />
        ) : (
          <span className="text-muted-foreground text-xs">—</span>
        )}
      </td>
    </tr>
  );
}
