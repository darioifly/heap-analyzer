import { useEffect, useState } from "react";
import { FolderPlus, Loader2, Plus } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useProjectStore } from "@/stores/projectStore";
import { useSurveyStore } from "@/stores/surveyStore";
import { ProjectCard } from "./ProjectCard";
import { ProjectDialog } from "./ProjectDialog";
import { DeleteProjectDialog } from "./DeleteProjectDialog";
import type { Crs, Project } from "@/types";

export function ProjectList() {
  const {
    projects,
    selectedProjectId,
    isLoading,
    loadAll,
    create,
    update,
    delete: deleteProject,
    select,
  } = useProjectStore();

  const { loadByProject, clear: clearSurveys } = useSurveyStore();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | undefined>();
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [projectToDelete, setProjectToDelete] = useState<Project | null>(null);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const handleSelect = (id: number) => {
    select(id);
    loadByProject(id);
  };

  const handleCreate = () => {
    setEditingProject(undefined);
    setDialogOpen(true);
  };

  const handleEdit = (project: Project) => {
    setEditingProject(project);
    setDialogOpen(true);
  };

  const handleDelete = (project: Project) => {
    setProjectToDelete(project);
    setDeleteDialogOpen(true);
  };

  const handleSave = async (data: {
    name: string;
    location: string | null;
    crs: Crs;
    notes: string | null;
    materialCategories: string[];
  }) => {
    try {
      if (editingProject) {
        await update(editingProject.id, data);
        toast.success("Progetto aggiornato");
      } else {
        const project = await create(data);
        select(project.id);
        toast.success("Progetto creato");
      }
      setDialogOpen(false);
    } catch {
      toast.error("Errore durante il salvataggio del progetto");
    }
  };

  const handleConfirmDelete = async () => {
    if (!projectToDelete) return;
    try {
      await deleteProject(projectToDelete.id);
      clearSurveys();
      toast.success("Progetto eliminato");
    } catch {
      toast.error("Errore durante l'eliminazione del progetto");
    }
    setDeleteDialogOpen(false);
    setProjectToDelete(null);
  };

  return (
    <>
      <div className="flex flex-col h-full">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Progetti
          </h2>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={handleCreate}
            aria-label="Nuovo progetto"
          >
            <Plus size={16} strokeWidth={1.75} />
          </Button>
        </div>

        {/* List */}
        <ScrollArea className="flex-1">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="animate-spin text-muted-foreground" size={24} />
            </div>
          ) : projects.length === 0 ? (
            <div className="flex flex-col items-center justify-center px-4 py-8 text-center">
              <FolderPlus className="text-muted-foreground mb-3" size={32} strokeWidth={1.75} />
              <p className="text-sm text-muted-foreground mb-3">Nessun progetto</p>
              <Button variant="outline" size="sm" onClick={handleCreate}>
                Crea il primo progetto
              </Button>
            </div>
          ) : (
            <div className="py-1">
              {projects.map((project) => (
                <ProjectCard
                  key={project.id}
                  project={project}
                  isSelected={project.id === selectedProjectId}
                  surveyCount={0}
                  onClick={() => handleSelect(project.id)}
                  onEdit={() => handleEdit(project)}
                  onDelete={() => handleDelete(project)}
                />
              ))}
            </div>
          )}
        </ScrollArea>
      </div>

      <ProjectDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        project={editingProject}
        onSave={handleSave}
      />

      {projectToDelete && (
        <DeleteProjectDialog
          open={deleteDialogOpen}
          onOpenChange={setDeleteDialogOpen}
          projectName={projectToDelete.name}
          onConfirm={handleConfirmDelete}
        />
      )}
    </>
  );
}
