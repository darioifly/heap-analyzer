import { useEffect, useMemo, useState } from "react";
import { Play, Info, Sparkles } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ProcessingProgress } from "./ProcessingProgress";
import { useProcessingStore } from "@/stores/processingStore";
import { useSurveyStore } from "@/stores/surveyStore";
import { useHeapStore } from "@/stores/heapStore";
import { useProjectStore } from "@/stores/projectStore";
import { useVlmStore } from "@/stores/vlmStore";

interface ProcessingDialogProps {
  surveyId: number | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function InfoTip({ text }: { text: string }) {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Info size={14} className="text-muted-foreground inline ml-1 cursor-help" strokeWidth={1.75} />
        </TooltipTrigger>
        <TooltipContent className="max-w-[250px]">
          <p className="text-xs">{text}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

export function ProcessingDialog({
  surveyId,
  open,
  onOpenChange,
}: ProcessingDialogProps) {
  const [dsmResolution, setDsmResolution] = useState(0.1);
  const [heightThreshold, setHeightThreshold] = useState(0.5);
  const [minHeapArea, setMinHeapArea] = useState(50);
  const [baseMode, setBaseMode] = useState<"auto" | "manual_percentile" | "manual_elevation">("auto");
  const [basePercentile, setBasePercentile] = useState(5);
  const [manualElevation, setManualElevation] = useState(0);
  const [vlmEnabled, setVlmEnabled] = useState(true);
  const [vlmModel, setVlmModel] = useState<string | null>(null);

  const processingStore = useProcessingStore();
  const surveyStore = useSurveyStore();
  const heapStore = useHeapStore();
  const projectStore = useProjectStore();
  const vlmStore = useVlmStore();

  const survey = surveyStore.surveys.find((s) => s.id === surveyId);
  const project = projectStore.projects.find((p) => p.id === survey?.projectId);
  const projectCategories = project?.materialCategories ?? [];

  const downloadedModels = useMemo(
    () => vlmStore.models.filter((m) => m.is_downloaded),
    [vlmStore.models],
  );
  const cudaOk = vlmStore.gpuStatus?.cuda_available === true;
  const vlmReady = cudaOk && downloadedModels.length > 0;

  useEffect(() => {
    if (open) {
      void vlmStore.refreshGpuStatus();
      void vlmStore.refreshModels();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Keep vlmModel in sync with the downloaded list: if nothing selected, pick
  // the first; if the current selection is no longer downloaded (stale state),
  // replace it with the first available model.
  useEffect(() => {
    if (downloadedModels.length === 0) {
      if (vlmModel !== null) setVlmModel(null);
      return;
    }
    const stillAvailable = downloadedModels.some((m) => m.name === vlmModel);
    if (!stillAvailable) {
      setVlmModel(downloadedModels[0].name);
    }
  }, [downloadedModels, vlmModel]);

  const handleStart = async (useAdvanced: boolean) => {
    if (!survey || !surveyId) return;

    // Merge survey-level processing_params (set by DJI import to carry
    // precomputed_dsm_path, etc.) with the UI advanced-tab overrides.
    // Advanced UI wins on conflict.
    const surveyParams: Record<string, unknown> = survey.processingParams ?? {};
    const advancedParams: Record<string, unknown> = useAdvanced
      ? {
          dsm_resolution: dsmResolution,
          height_threshold: heightThreshold,
          min_heap_area: minHeapArea,
          base_mode: baseMode,
          ...(baseMode === "manual_percentile" ? { base_percentile: basePercentile } : {}),
          ...(baseMode === "manual_elevation" ? { manual_base_elevation: manualElevation } : {}),
        }
      : {};

    const runVlm = vlmEnabled && vlmReady && vlmModel !== null;
    let vlmModelsDir: string | null = null;
    if (runVlm) {
      try {
        vlmModelsDir = await window.api.vlm.getModelsDir();
      } catch (err) {
        console.warn("Cannot resolve vlm models dir:", err);
      }
    }
    const vlmParams: Record<string, unknown> = runVlm
      ? {
          vlm_validation_enabled: true,
          vlm_model_name: vlmModel,
          material_categories: projectCategories,
          ...(vlmModelsDir ? { vlm_models_dir: vlmModelsDir } : {}),
        }
      : {};
    if (vlmEnabled && !vlmReady) {
      toast.warning(
        cudaOk
          ? "Nessun modello VLM scaricato — validazione saltata"
          : "CUDA non disponibile — validazione VLM saltata",
      );
    }

    const merged: Record<string, unknown> = { ...surveyParams, ...advancedParams, ...vlmParams };
    const config: Record<string, unknown> | null =
      Object.keys(merged).length > 0 ? merged : null;

    processingStore.start(surveyId);
    await surveyStore.update(surveyId, { processingStatus: "processing" });

    // Set up progress listener
    window.api.python.removeAllListeners();
    window.api.python.onProgress((data) => {
      processingStore.updateProgress({
        phase: data.phase,
        percent: data.percent,
        message: data.message,
      });
    });
    window.api.python.onWarning((data) => {
      processingStore.addWarning(data.message);
    });

    try {
      const args = [
        "--las", survey.lasPath,
        "--tiff", survey.tiffPath,
        "--output", survey.lasPath.replace(/[/\\][^/\\]+$/, "/output"),
      ];
      if (config) {
        args.push("--config", JSON.stringify(config));
      }

      const result = await window.api.python.execute("process", args);
      const data = result.data as {
        heap_metrics?: Array<Record<string, unknown> & { vlm_is_heap?: boolean | null }>;
        intermediate_files?: Record<string, string>;
        dsm_path?: string;
        dtm_path?: string;
        ndsm_path?: string;
        label_map_path?: string;
        base_elevation?: number;
      };

      const ifiles = data.intermediate_files ?? {};

      // Update survey paths — including the survey-level base_elevation
      // so the 3D elevation gradient can key off it (without this,
      // pointZRangeRef falls back to the cloud's absolute Z min and the
      // whole cloud turns purple because ground dominates the range).
      await surveyStore.update(surveyId, {
        processingStatus: "completed",
        dsmPath: ifiles.dsm ?? (data.dsm_path as string) ?? null,
        dtmPath: ifiles.dtm ?? (data.dtm_path as string) ?? null,
        ndsmPath: ifiles.ndsm ?? (data.ndsm_path as string) ?? null,
        labelMapPath: ifiles.label_map ?? (data.label_map_path as string) ?? null,
        tilesPath: ifiles.tiles ?? null,
        ndsmHeatmapPath: ifiles.ndsm_heatmap ?? null,
        baseElevation: typeof data.base_elevation === "number" ? data.base_elevation : null,
      });

      // Bulk create heaps
      if (data.heap_metrics && data.heap_metrics.length > 0) {
        await heapStore.bulkCreate(
          data.heap_metrics.map((m) => ({
            surveyId,
            label: (m.label as string) ?? null,
            polygon: (typeof m.polygon_geojson === "string" ? JSON.parse(m.polygon_geojson as string) : m.polygon_geojson) as GeoJSON.Polygon,
            volume: m.volume_m3 as number,
            planimetricArea: m.planimetric_area_m2 as number,
            surfaceArea: m.surface_area_m2 as number,
            maxHeight: m.max_height_m as number,
            meanHeight: m.mean_height_m as number,
            baseElevation: m.base_elevation_m as number,
            centroidE: m.centroid_e as number,
            centroidN: m.centroid_n as number,
            bboxMinE: m.bbox_min_e as number,
            bboxMinN: m.bbox_min_n as number,
            bboxMaxE: m.bbox_max_e as number,
            bboxMaxN: m.bbox_max_n as number,
            materialCategory: (m.material_category as string) ?? null,
            materialConfidence: (m.material_confidence as number) ?? null,
            vlmReasoning: (m.vlm_reasoning as string) ?? null,
            isManuallyConfirmed: false,
            isExcluded: m.vlm_is_heap === false,
          })),
        );
      }

      // Count VLM false positives + detect "silent skip" (VLM was requested
      // but no heap came back with a VLM verdict — means Phase 7 bailed out,
      // e.g. model not downloaded; Python emits a warning we already show).
      const vlmFalsePositives = (data.heap_metrics ?? []).filter(
        (m) => m.vlm_is_heap === false,
      ).length;
      const vlmRanAnyVerdict = (data.heap_metrics ?? []).some(
        (m) => m.vlm_is_heap === true || m.vlm_is_heap === false,
      );
      if (runVlm && !vlmRanAnyVerdict) {
        toast.warning(
          "Validazione VLM richiesta ma non eseguita — vedi warning per il motivo.",
        );
      }

      // Attempt Potree conversion (non-blocking — skip if PotreeConverter not available)
      try {
        await window.api.potree.convert({ surveyId });
      } catch (potreeErr) {
        console.warn("Potree conversion skipped or failed:", potreeErr);
      }

      processingStore.complete();

      const heapCount = data.heap_metrics?.length ?? 0;
      const totalVolume = (data.heap_metrics ?? []).reduce(
        (sum, h) => sum + (h.volume_m3 as number ?? 0),
        0,
      );

      const vlmSuffix = vlmFalsePositives > 0
        ? ` VLM ha escluso ${vlmFalsePositives} falsi positivi.`
        : "";
      toast.success(
        `Elaborazione completata: ${heapCount} cumuli trovati. ` +
          `Volume totale: ${totalVolume.toFixed(0)} m\u00B3.${vlmSuffix}`,
      );

      // Show warnings
      const warnings = useProcessingStore.getState().warnings;
      for (const w of warnings) {
        toast.warning(w);
      }

      onOpenChange(false);
    } catch (err) {
      await surveyStore.update(surveyId, { processingStatus: "error" });
      processingStore.fail(String(err));
      toast.error(`Errore durante l'elaborazione: ${String(err)}`);
    } finally {
      window.api.python.removeAllListeners();
    }
  };

  const handleCancel = async () => {
    await window.api.python.cancel();
    if (surveyId) {
      await surveyStore.update(surveyId, { processingStatus: "pending" });
    }
    processingStore.cancel();
    toast.warning("Elaborazione annullata");
    onOpenChange(false);
  };

  if (!survey) return null;

  return (
    <Dialog open={open} onOpenChange={(o) => {
      if (!o && processingStore.isRunning) return; // Prevent closing while running
      onOpenChange(o);
    }}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>
            {processingStore.isRunning ? "Elaborazione in corso..." : "Elaborazione rilievo"}
          </DialogTitle>
        </DialogHeader>

        {processingStore.isRunning ? (
          <ProcessingProgress onCancel={handleCancel} />
        ) : (
          <Tabs defaultValue="default">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="default">Parametri default</TabsTrigger>
              <TabsTrigger value="advanced">Parametri avanzati</TabsTrigger>
            </TabsList>

            <TabsContent value="default" className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Verranno utilizzati i parametri standard ottimizzati per cumuli
                siderurgici.
              </p>
              <VlmValidationBlock
                enabled={vlmEnabled}
                setEnabled={setVlmEnabled}
                model={vlmModel}
                setModel={setVlmModel}
                downloadedModels={downloadedModels}
                cudaOk={cudaOk}
                categories={projectCategories}
              />
              <Button onClick={() => handleStart(false)} className="w-full">
                <Play size={16} className="mr-2" strokeWidth={1.75} />
                Avvia elaborazione
              </Button>
            </TabsContent>

            <TabsContent value="advanced" className="space-y-4">
              {/* DSM Resolution */}
              <div className="space-y-2">
                <Label>
                  Risoluzione DSM
                  <InfoTip text="Dimensione pixel del modello digitale di superficie. Valori più bassi = più dettaglio, più tempo." />
                </Label>
                <div className="flex items-center gap-3">
                  <Slider
                    value={[dsmResolution]}
                    onValueChange={([v]) => setDsmResolution(v)}
                    min={0.05}
                    max={0.5}
                    step={0.05}
                    className="flex-1"
                  />
                  <span className="text-sm font-mono w-20 text-right">
                    {dsmResolution.toFixed(2)} m/px
                  </span>
                </div>
              </div>

              {/* Height threshold */}
              <div className="space-y-2">
                <Label>
                  Soglia altezza minima
                  <InfoTip text="Altezza minima sopra il piano base per considerare un'area come cumulo." />
                </Label>
                <div className="flex items-center gap-3">
                  <Slider
                    value={[heightThreshold]}
                    onValueChange={([v]) => setHeightThreshold(v)}
                    min={0.1}
                    max={2.0}
                    step={0.1}
                    className="flex-1"
                  />
                  <span className="text-sm font-mono w-16 text-right">
                    {heightThreshold.toFixed(1)} m
                  </span>
                </div>
              </div>

              {/* Min heap area */}
              <div className="space-y-2">
                <Label>
                  Area minima cumulo
                  <InfoTip text="Area planimetrica minima. Oggetti più piccoli vengono filtrati (es. macchinari)." />
                </Label>
                <div className="flex items-center gap-3">
                  <Input
                    type="number"
                    value={minHeapArea}
                    onChange={(e) => setMinHeapArea(Number(e.target.value))}
                    min={10}
                    max={1000}
                    className="flex-1"
                  />
                  <span className="text-sm font-mono w-8">m²</span>
                </div>
              </div>

              {/* Base elevation mode */}
              <div className="space-y-2">
                <Label>
                  Modalità quota base
                  <InfoTip text="Come viene determinato il piano di riferimento per il calcolo dei volumi." />
                </Label>
                <Select
                  value={baseMode}
                  onValueChange={(v) => setBaseMode(v as typeof baseMode)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="auto">Automatica</SelectItem>
                    <SelectItem value="manual_percentile">
                      Percentile manuale
                    </SelectItem>
                    <SelectItem value="manual_elevation">
                      Quota fissa
                    </SelectItem>
                  </SelectContent>
                </Select>

                {baseMode === "manual_percentile" && (
                  <div className="flex items-center gap-3 mt-2">
                    <Label className="text-xs shrink-0">Percentile:</Label>
                    <Input
                      type="number"
                      value={basePercentile}
                      onChange={(e) => setBasePercentile(Number(e.target.value))}
                      min={1}
                      max={50}
                      className="w-20"
                    />
                  </div>
                )}

                {baseMode === "manual_elevation" && (
                  <div className="flex items-center gap-3 mt-2">
                    <Label className="text-xs shrink-0">Quota (m s.l.m.):</Label>
                    <Input
                      type="number"
                      value={manualElevation}
                      onChange={(e) => setManualElevation(Number(e.target.value))}
                      step={0.01}
                      className="w-24"
                    />
                  </div>
                )}
              </div>

              <VlmValidationBlock
                enabled={vlmEnabled}
                setEnabled={setVlmEnabled}
                model={vlmModel}
                setModel={setVlmModel}
                downloadedModels={downloadedModels}
                cudaOk={cudaOk}
                categories={projectCategories}
              />

              <Button onClick={() => handleStart(true)} className="w-full">
                <Play size={16} className="mr-2" strokeWidth={1.75} />
                Avvia elaborazione
              </Button>
            </TabsContent>
          </Tabs>
        )}
      </DialogContent>
    </Dialog>
  );
}

interface VlmValidationBlockProps {
  enabled: boolean;
  setEnabled: (v: boolean) => void;
  model: string | null;
  setModel: (v: string) => void;
  downloadedModels: { name: string; display_name: string }[];
  cudaOk: boolean;
  categories: string[];
}

function VlmValidationBlock({
  enabled,
  setEnabled,
  model,
  setModel,
  downloadedModels,
  cudaOk,
  categories,
}: VlmValidationBlockProps) {
  const disabledReason = !cudaOk
    ? "CUDA non disponibile su questa macchina"
    : downloadedModels.length === 0
      ? "Nessun modello VLM scaricato — apri Impostazioni → VLM"
      : null;

  return (
    <div className="rounded-md border border-border bg-muted/40 p-3 space-y-3">
      <div className="flex items-start gap-2">
        <Checkbox
          id="vlm-validate"
          checked={enabled}
          onCheckedChange={(c) => setEnabled(c === true)}
          disabled={disabledReason !== null}
          className="mt-0.5"
        />
        <div className="flex-1 space-y-1">
          <Label htmlFor="vlm-validate" className="cursor-pointer flex items-center gap-1.5">
            <Sparkles size={14} strokeWidth={1.75} className="text-primary" />
            Verifica cumuli con VLM e classifica materiale
            <InfoTip text="Il VLM scarta i falsi positivi (macchinari, binari, tetti) e assegna una categoria materiale a ogni cumulo. Richiede GPU CUDA e un modello VLM scaricato." />
          </Label>
          {disabledReason ? (
            <p className="text-xs text-muted-foreground">{disabledReason}</p>
          ) : categories.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              Classificazione in forma libera: il VLM descrive il materiale con 2-5 parole.
            </p>
          ) : (
            <p className="text-xs text-muted-foreground">
              Validazione + classificazione su {categories.length} categorie del progetto.
            </p>
          )}
        </div>
      </div>

      {enabled && disabledReason === null && (
        <div className="pl-6 space-y-1.5">
          <Label className="text-xs">Modello VLM</Label>
          <Select value={model ?? undefined} onValueChange={setModel}>
            <SelectTrigger className="h-8 text-sm">
              <SelectValue placeholder="Seleziona modello..." />
            </SelectTrigger>
            <SelectContent>
              {downloadedModels.map((m) => (
                <SelectItem key={m.name} value={m.name}>
                  {m.display_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}
    </div>
  );
}
