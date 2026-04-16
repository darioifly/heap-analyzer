import { Play, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { Survey } from "@/types";

const STATUS_CONFIG: Record<
  string,
  { label: string; variant: "secondary" | "default" | "destructive" | "outline"; className?: string }
> = {
  pending: { label: "In attesa", variant: "secondary" },
  processing: { label: "In elaborazione", variant: "default", className: "animate-pulse bg-warning-500 text-white" },
  completed: { label: "Completato", variant: "default", className: "bg-success-600 text-white" },
  error: { label: "Errore", variant: "destructive" },
};

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("it-IT", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

interface SurveyCardProps {
  survey: Survey;
  isSelected: boolean;
  onClick: () => void;
  onProcess: () => void;
}

export function SurveyCard({
  survey,
  isSelected,
  onClick,
  onProcess,
}: SurveyCardProps) {
  const config = STATUS_CONFIG[survey.processingStatus] ?? STATUS_CONFIG.pending;

  return (
    <div
      className={cn(
        "flex items-center gap-2 px-4 py-2 cursor-pointer transition-colors",
        "hover:bg-accent dark:hover:bg-evlos-700",
        isSelected && "bg-primary/10 border-l-2 border-l-primary",
      )}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onClick();
      }}
    >
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium">{formatDate(survey.surveyDate)}</p>
        {survey.operator && (
          <p className="text-xs text-muted-foreground truncate">
            {survey.operator}
          </p>
        )}
      </div>

      <Badge variant={config.variant} className={cn("text-xs shrink-0", config.className)}>
        {config.label}
      </Badge>

      {(survey.processingStatus === "pending" ||
        survey.processingStatus === "error") && (
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 shrink-0"
          onClick={(e) => {
            e.stopPropagation();
            onProcess();
          }}
          title="Elabora"
        >
          <Play size={14} strokeWidth={1.75} />
        </Button>
      )}

      {survey.processingStatus === "completed" && (
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 shrink-0"
          onClick={(e) => {
            e.stopPropagation();
            onProcess();
          }}
          title="Rielabora"
        >
          <RefreshCw size={14} strokeWidth={1.75} />
        </Button>
      )}
    </div>
  );
}
