import { MousePointerClick } from "lucide-react";

export function SidebarRight() {
  return (
    <div className="flex flex-col h-full border-l border-border">
      {/* Header */}
      <div className="flex items-center px-4 py-3 border-b border-border">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Proprietà
        </h2>
      </div>

      {/* Empty state */}
      <div className="flex flex-col items-center justify-center flex-1 px-4 py-8 text-center">
        <MousePointerClick
          className="text-muted-foreground mb-3"
          size={32}
          strokeWidth={1.75}
        />
        <p className="text-sm text-muted-foreground">
          Seleziona un cumulo per vedere i dettagli
        </p>
      </div>
    </div>
  );
}
