import { useEffect, useState } from "react";
import { Boxes, Moon, Sun, Settings, Map, Box } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useUiStore } from "@/stores/uiStore";
import { useProjectStore } from "@/stores/projectStore";
import { useSurveyStore } from "@/stores/surveyStore";
import { ExportButton } from "@/components/export/ExportButton";

export function HeaderBar() {
  const toggleTheme = useUiStore((s) => s.toggleTheme);
  const viewMode = useUiStore((s) => s.viewMode);
  const setViewMode = useUiStore((s) => s.setViewMode);
  const selectedProject = useProjectStore((s) => {
    const id = s.selectedProjectId;
    return id ? s.projects.find((p) => p.id === id) : undefined;
  });
  const selectedSurveyId = useSurveyStore((s) => s.selectedSurveyId);
  const survey = useSurveyStore((s) =>
    s.surveys.find((sv) => sv.id === s.selectedSurveyId),
  );

  const [potreeAvailable, setPotreeAvailable] = useState(false);

  useEffect(() => {
    if (!selectedSurveyId || survey?.processingStatus !== "completed") {
      setPotreeAvailable(false);
      return;
    }
    window.api.potree
      .getStatus({ surveyId: selectedSurveyId })
      .then((status) => setPotreeAvailable(status.available))
      .catch(() => setPotreeAvailable(false));
  }, [selectedSurveyId, survey?.processingStatus]);

  // Reset to 2D if potree becomes unavailable
  useEffect(() => {
    if (!potreeAvailable && viewMode === "3d") {
      setViewMode("2d");
    }
  }, [potreeAvailable, viewMode, setViewMode]);

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
        {/* 2D/3D toggle */}
        <div className="flex items-center gap-0.5 bg-evlos-800 rounded-lg p-0.5 border border-evlos-700">
          <button
            onClick={() => setViewMode("2d")}
            className={`flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded transition-colors ${
              viewMode === "2d"
                ? "bg-evlos-600 text-white shadow-sm"
                : "text-evlos-300 hover:text-evlos-100"
            }`}
            aria-pressed={viewMode === "2d"}
          >
            <Map size={14} strokeWidth={1.75} /> 2D
          </button>
          <button
            onClick={() => potreeAvailable && setViewMode("3d")}
            disabled={!potreeAvailable}
            className={`flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded transition-colors ${
              viewMode === "3d"
                ? "bg-evlos-600 text-white shadow-sm"
                : "text-evlos-300 hover:text-evlos-100"
            } ${!potreeAvailable ? "opacity-40 cursor-not-allowed" : ""}`}
            aria-pressed={viewMode === "3d"}
            title={
              !potreeAvailable
                ? "Dati 3D non disponibili. Elabora il rilievo."
                : "Vista 3D"
            }
          >
            <Box size={14} strokeWidth={1.75} /> 3D
          </button>
        </div>

        <ExportButton />
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
