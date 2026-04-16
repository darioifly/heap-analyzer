import { Boxes, Moon, Sun, Settings } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useUiStore } from "@/stores/uiStore";
import { useProjectStore } from "@/stores/projectStore";

export function HeaderBar() {
  const toggleTheme = useUiStore((s) => s.toggleTheme);
  const selectedProject = useProjectStore((s) => {
    const id = s.selectedProjectId;
    return id ? s.projects.find((p) => p.id === id) : undefined;
  });

  return (
    <header className="h-[100px] shrink-0 bg-evlos-700 dark:bg-evlos-800 flex items-center px-6">
      {/* Logo */}
      <div className="flex items-center gap-3 flex-1">
        <Boxes className="text-white" size={28} strokeWidth={1.75} />
        <span className="text-white font-mono font-semibold text-lg tracking-wide">
          HEAP ANALYZER
        </span>
      </div>

      {/* Center: current project name */}
      <div className="flex-1 text-center">
        {selectedProject && (
          <span className="text-white font-medium text-sm">
            {selectedProject.name}
          </span>
        )}
      </div>

      {/* Right controls */}
      <div className="flex items-center gap-2 flex-1 justify-end">
        <Button
          variant="ghost"
          size="icon"
          className="text-white hover:bg-white/10"
          onClick={toggleTheme}
          aria-label="Cambia tema"
        >
          <Sun className="h-5 w-5 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" strokeWidth={1.75} />
          <Moon className="absolute h-5 w-5 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" strokeWidth={1.75} />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="text-white hover:bg-white/10"
          aria-label="Impostazioni"
        >
          <Settings size={20} strokeWidth={1.75} />
        </Button>
      </div>
    </header>
  );
}
