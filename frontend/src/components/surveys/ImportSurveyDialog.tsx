import { useState } from "react";
import { FolderOpen, CheckCircle, XCircle, Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

const ERROR_SUGGESTIONS: Record<string, string> = {
  CRS_MISMATCH:
    "I sistemi di riferimento dei file non coincidono. Suggerimento: verifica che entrambi i file siano in EPSG:32632 o EPSG:32633.",
  BOUNDS_NO_OVERLAP:
    "I file coprono aree geografiche diverse. Suggerimento: verifica che LAS e ortofoto siano dello stesso volo.",
  FILE_CORRUPT:
    "Uno dei file è corrotto o non valido. Suggerimento: rigenera il file dal software fotogrammetrico.",
};

function truncatePath(p: string, maxLen = 50): string {
  if (p.length <= maxLen) return p;
  return "..." + p.slice(p.length - maxLen + 3);
}

function todayIso(): string {
  return new Date().toISOString().split("T")[0];
}

interface ImportSurveyDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onImport: (data: {
    lasPath: string;
    tiffPath: string;
    surveyDate: string;
    operator: string | null;
  }) => void;
}

export function ImportSurveyDialog({
  open,
  onOpenChange,
  onImport,
}: ImportSurveyDialogProps) {
  const [lasPath, setLasPath] = useState("");
  const [tiffPath, setTiffPath] = useState("");
  const [surveyDate, setSurveyDate] = useState(todayIso());
  const [operator, setOperator] = useState("");
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<{
    valid: boolean;
    errors: string[];
  } | null>(null);

  const resetState = () => {
    setLasPath("");
    setTiffPath("");
    setSurveyDate(todayIso());
    setOperator("");
    setValidating(false);
    setValidationResult(null);
  };

  const handleOpenChange = (open: boolean) => {
    if (!open) resetState();
    onOpenChange(open);
  };

  const pickLas = async () => {
    const path = await window.api.dialog.openFile({
      title: "Seleziona file nuvola di punti",
      filters: [{ name: "Nuvola di punti", extensions: ["las", "laz"] }],
    });
    if (path) {
      setLasPath(path);
      setValidationResult(null);
    }
  };

  const pickTiff = async () => {
    const path = await window.api.dialog.openFile({
      title: "Seleziona file ortofoto",
      filters: [{ name: "GeoTIFF", extensions: ["tif", "tiff"] }],
    });
    if (path) {
      setTiffPath(path);
      setValidationResult(null);
    }
  };

  const handleValidate = async () => {
    setValidating(true);
    setValidationResult(null);
    try {
      const result = await window.api.python.execute("validate", [
        "--las",
        lasPath,
        "--tiff",
        tiffPath,
      ]);
      const data = result.data as { valid: boolean; errors?: string[] };
      setValidationResult({
        valid: data.valid,
        errors: data.errors ?? [],
      });
    } catch (err) {
      setValidationResult({
        valid: false,
        errors: [String(err)],
      });
    } finally {
      setValidating(false);
    }
  };

  const handleImport = () => {
    onImport({
      lasPath,
      tiffPath,
      surveyDate,
      operator: operator.trim() || null,
    });
    handleOpenChange(false);
  };

  const canValidate = lasPath && tiffPath && !validating;
  const canImport = validationResult?.valid === true;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>Importa rilievo</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* LAS file picker */}
          <div className="space-y-2">
            <Label>File nuvola di punti (LAS/LAZ) *</Label>
            <div className="flex gap-2">
              <Input
                readOnly
                value={lasPath ? truncatePath(lasPath) : ""}
                placeholder="Nessun file selezionato"
                className="flex-1"
              />
              <Button variant="outline" size="sm" onClick={pickLas}>
                <FolderOpen size={16} className="mr-1" strokeWidth={1.75} />
                Sfoglia...
              </Button>
            </div>
          </div>

          {/* TIFF file picker */}
          <div className="space-y-2">
            <Label>File ortofoto (GeoTIFF) *</Label>
            <div className="flex gap-2">
              <Input
                readOnly
                value={tiffPath ? truncatePath(tiffPath) : ""}
                placeholder="Nessun file selezionato"
                className="flex-1"
              />
              <Button variant="outline" size="sm" onClick={pickTiff}>
                <FolderOpen size={16} className="mr-1" strokeWidth={1.75} />
                Sfoglia...
              </Button>
            </div>
          </div>

          {/* Survey date */}
          <div className="space-y-2">
            <Label htmlFor="survey-date">Data rilievo</Label>
            <Input
              id="survey-date"
              type="date"
              value={surveyDate}
              onChange={(e) => setSurveyDate(e.target.value)}
            />
          </div>

          {/* Operator */}
          <div className="space-y-2">
            <Label htmlFor="operator">Operatore</Label>
            <Input
              id="operator"
              value={operator}
              onChange={(e) => setOperator(e.target.value)}
              placeholder="Es. Mario Rossi"
            />
          </div>

          {/* Validation result */}
          {validationResult && (
            <Alert
              variant={validationResult.valid ? "default" : "destructive"}
              className={
                validationResult.valid
                  ? "border-success-500 bg-success-50 dark:bg-success-900/20"
                  : undefined
              }
            >
              {validationResult.valid ? (
                <>
                  <CheckCircle className="h-4 w-4 text-success-600" />
                  <AlertTitle className="text-success-700 dark:text-success-400">
                    Validazione superata
                  </AlertTitle>
                  <AlertDescription className="text-success-600 dark:text-success-300">
                    Bounds compatibili, CRS coincidenti.
                  </AlertDescription>
                </>
              ) : (
                <>
                  <XCircle className="h-4 w-4" />
                  <AlertTitle>Validazione fallita</AlertTitle>
                  <AlertDescription>
                    <ul className="list-disc pl-4 mt-1 space-y-1">
                      {validationResult.errors.map((err, i) => (
                        <li key={i}>
                          {ERROR_SUGGESTIONS[err] ?? err}
                        </li>
                      ))}
                    </ul>
                  </AlertDescription>
                </>
              )}
            </Alert>
          )}
        </div>

        <DialogFooter className="gap-2">
          <Button
            variant="outline"
            onClick={handleValidate}
            disabled={!canValidate}
          >
            {validating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Valida
          </Button>
          <Button onClick={handleImport} disabled={!canImport}>
            Importa
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
