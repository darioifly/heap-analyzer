/**
 * Export split-button with dropdown menu for PDF, CSV, or both.
 */

import { useState } from "react";
import {
  Download,
  FileText,
  Table2,
  Package,
  Map,
  FileArchive,
  Layers,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useSurveyStore } from "@/stores/surveyStore";
import { ExportDialog } from "./ExportDialog";
import { ReportDialog } from "./ReportDialog";
import type { ReportFormat } from "@/stores/reportStore";

type GeoFormat = "geojson" | "shapefile" | "both";

export function ExportButton() {
  const [csvDialogOpen, setCsvDialogOpen] = useState(false);
  const [reportDialogOpen, setReportDialogOpen] = useState(false);
  const [reportFormat, setReportFormat] = useState<ReportFormat>("pdf");
  const [exportingGis, setExportingGis] = useState(false);

  const survey = useSurveyStore((s) =>
    s.surveys.find((sv) => sv.id === s.selectedSurveyId),
  );

  const disabled = !survey || survey.processingStatus !== "completed";

  const openReport = (format: ReportFormat) => {
    setReportFormat(format);
    setReportDialogOpen(true);
  };

  const exportGis = async (format: GeoFormat) => {
    if (!survey) return;

    const outputDir = await window.api.dialog.openDirectory({
      title: "Seleziona cartella di destinazione",
    });
    if (!outputDir) return;

    setExportingGis(true);
    const labelByFormat: Record<GeoFormat, string> = {
      geojson: "GeoJSON",
      shapefile: "Shapefile",
      both: "GIS (GeoJSON + Shapefile)",
    };

    try {
      const result = await window.api.export.geo({
        surveyId: survey.id,
        format,
        outputDir,
      });
      toast.success(
        `Export ${labelByFormat[format]} completato: ${result.count} cumuli`,
        {
          action: result.paths[0]
            ? {
                label: "Apri cartella",
                onClick: () => window.api.shell.showItemInFolder(result.paths[0]),
              }
            : undefined,
        },
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("Nessun cumulo")) {
        toast.error("Nessun cumulo disponibile per l'esportazione");
      } else {
        toast.error(`Errore export GIS: ${msg}`);
      }
    } finally {
      setExportingGis(false);
    }
  };

  return (
    <>
      <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  className="text-white border-white/20 hover:bg-white/10"
                  disabled={disabled}
                >
                  <Download size={14} className="mr-1.5" strokeWidth={1.75} />
                  Esporta
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => openReport("pdf")}>
                  <FileText size={14} className="mr-2" />
                  Report PDF
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => setCsvDialogOpen(true)}>
                  <Table2 size={14} className="mr-2" />
                  CSV cumuli
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => openReport("pdf+csv")}>
                  <Package size={14} className="mr-2" />
                  Report PDF + CSV
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onClick={() => exportGis("geojson")}
                  disabled={exportingGis}
                >
                  <Map size={14} className="mr-2" />
                  Esporta GeoJSON
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => exportGis("shapefile")}
                  disabled={exportingGis}
                >
                  <FileArchive size={14} className="mr-2" />
                  Esporta Shapefile
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => exportGis("both")}
                  disabled={exportingGis}
                >
                  <Layers size={14} className="mr-2" />
                  Esporta Entrambi (GIS)
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </TooltipTrigger>
        {disabled && (
          <TooltipContent>
            <p>Seleziona un rilievo elaborato</p>
          </TooltipContent>
        )}
      </Tooltip>
      </TooltipProvider>

      <ExportDialog open={csvDialogOpen} onOpenChange={setCsvDialogOpen} />
      <ReportDialog
        open={reportDialogOpen}
        onOpenChange={setReportDialogOpen}
        initialFormat={reportFormat}
      />
    </>
  );
}
