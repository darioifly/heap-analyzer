import { MoreVertical, Pencil, Trash2 } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { Project } from "@/types";

interface ProjectCardProps {
  project: Project;
  isSelected: boolean;
  surveyCount: number;
  onClick: () => void;
  onEdit: () => void;
  onDelete: () => void;
}

export function ProjectCard({
  project,
  isSelected,
  surveyCount,
  onClick,
  onEdit,
  onDelete,
}: ProjectCardProps) {
  return (
    <div
      className={cn(
        "flex items-center gap-2 px-4 py-2.5 cursor-pointer transition-colors",
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
        <p className="text-sm font-medium truncate">{project.name}</p>
        {project.location && (
          <p className="text-xs text-muted-foreground truncate">
            {project.location}
          </p>
        )}
      </div>

      {surveyCount > 0 && (
        <Badge variant="secondary" className="shrink-0 text-xs">
          {surveyCount}
        </Badge>
      )}

      <DropdownMenu>
        <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
          <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0">
            <MoreVertical size={14} strokeWidth={1.75} />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={onEdit}>
            <Pencil size={14} className="mr-2" />
            Modifica
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={onDelete}
            className="text-danger-500 focus:text-danger-500"
          >
            <Trash2 size={14} className="mr-2" />
            Elimina
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
