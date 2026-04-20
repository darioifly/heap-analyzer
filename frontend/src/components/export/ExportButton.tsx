/**
 * Export split-button with dropdown menu for PDF, CSV, or both.
 */

import { useState } from "react";
import { Download, FileText, Table2, Package } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useSurveyStore } from "@/stores/surveyStore";
import { ExportDialog } from "./ExportDialog";
import { ReportDialog } from "./ReportDialog";
import type { ReportFormat } from "@/stores/reportStore";

export function ExportButton() {
  const [csvDialogOpen, setCsvDialogOpen] = useState(false);
  const [reportDialogOpen, setReportDialogOpen] = useState(false);
  const [reportFormat, setReportFormat] = useState<ReportFormat>("pdf");

  const survey = useSurveyStore((s) =>
    s.surveys.find((sv) => sv.id === s.selectedSurveyId),
  );

  const disabled = !survey || survey.processingStatus !== "completed";

  const openReport = (format: ReportFormat) => {
    setReportFormat(format);
    setReportDialogOpen(true);
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
