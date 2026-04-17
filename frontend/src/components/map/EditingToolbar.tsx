import {
  MousePointer2,
  Pentagon,
  Move,
  Scissors,
  GitMerge,
  Trash2,
  Undo2,
  Redo2,
  MapPin,
} from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Separator } from "@/components/ui/separator";
import { useEditingStore, type EditingTool } from "@/stores/editingStore";

interface ToolButton {
  tool: EditingTool;
  icon: React.ElementType;
  label: string;
  shortcut: string;
}

const TOOLS: ToolButton[] = [
  { tool: "select", icon: MousePointer2, label: "Seleziona", shortcut: "V" },
  { tool: "draw", icon: Pentagon, label: "Disegna cumulo", shortcut: "P" },
  { tool: "modify", icon: Move, label: "Modifica vertici", shortcut: "M" },
  { tool: "split", icon: Scissors, label: "Dividi cumulo", shortcut: "X" },
  { tool: "merge", icon: GitMerge, label: "Unisci cumuli", shortcut: "U" },
  { tool: "delete", icon: Trash2, label: "Elimina cumulo", shortcut: "Canc" },
  { tool: "ground-select", icon: MapPin, label: "Seleziona terreno noto", shortcut: "G" },
];

interface EditingToolbarProps {
  disabled?: boolean;
  mergeDisabled?: boolean;
}

export function EditingToolbar({
  disabled = false,
  mergeDisabled = false,
}: EditingToolbarProps) {
  const activeTool = useEditingStore((s) => s.activeTool);
  const setTool = useEditingStore((s) => s.setTool);
  const canUndo = useEditingStore((s) => s.canUndo());
  const canRedo = useEditingStore((s) => s.canRedo());

  return (
    <TooltipProvider delayDuration={300}>
      <div className="flex flex-col gap-1 rounded-lg bg-evlos-800/90 p-1.5 backdrop-blur-sm shadow-lg border border-border">
        {TOOLS.map((t) => {
          const isActive = activeTool === t.tool;
          const isDisabled =
            disabled || (t.tool === "merge" && mergeDisabled);
          const Icon = t.icon;

          return (
            <Tooltip key={t.tool}>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  onClick={() => {
                    if (!isDisabled) setTool(t.tool);
                  }}
                  disabled={isDisabled}
                  className={`flex h-9 w-9 items-center justify-center rounded transition-colors ${
                    isActive
                      ? "bg-evlos-600 text-white"
                      : isDisabled
                        ? "text-evlos-200 opacity-40 cursor-not-allowed"
                        : "text-evlos-200 hover:bg-evlos-700"
                  }`}
                >
                  <Icon size={18} strokeWidth={1.75} />
                </button>
              </TooltipTrigger>
              <TooltipContent side="right" className="flex items-center gap-2">
                <span>{t.label}</span>
                <kbd className="font-mono text-xs text-muted-foreground">
                  {t.shortcut}
                </kbd>
              </TooltipContent>
            </Tooltip>
          );
        })}

        <Separator className="my-0.5 bg-evlos-600" />

        {/* Undo */}
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              onClick={() => {
                if (canUndo) {
                  // Undo is handled by the PolygonEditor via the store
                  useEditingStore.getState().undo();
                }
              }}
              disabled={disabled || !canUndo}
              className={`flex h-9 w-9 items-center justify-center rounded transition-colors ${
                !canUndo || disabled
                  ? "text-evlos-200 opacity-40 cursor-not-allowed"
                  : "text-evlos-200 hover:bg-evlos-700"
              }`}
            >
              <Undo2 size={18} strokeWidth={1.75} />
            </button>
          </TooltipTrigger>
          <TooltipContent side="right" className="flex items-center gap-2">
            <span>Annulla</span>
            <kbd className="font-mono text-xs text-muted-foreground">
              Ctrl+Z
            </kbd>
          </TooltipContent>
        </Tooltip>

        {/* Redo */}
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              onClick={() => {
                if (canRedo) {
                  useEditingStore.getState().redo();
                }
              }}
              disabled={disabled || !canRedo}
              className={`flex h-9 w-9 items-center justify-center rounded transition-colors ${
                !canRedo || disabled
                  ? "text-evlos-200 opacity-40 cursor-not-allowed"
                  : "text-evlos-200 hover:bg-evlos-700"
              }`}
            >
              <Redo2 size={18} strokeWidth={1.75} />
            </button>
          </TooltipTrigger>
          <TooltipContent side="right" className="flex items-center gap-2">
            <span>Ripeti</span>
            <kbd className="font-mono text-xs text-muted-foreground">
              Ctrl+Shift+Z
            </kbd>
          </TooltipContent>
        </Tooltip>
      </div>
    </TooltipProvider>
  );
}
