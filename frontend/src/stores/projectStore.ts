import { create } from "zustand";
import type { Crs, Project } from "@/types";

// Serialize frontend Project → DB row format (camelCase → snake_case, JSON arrays)
function toDbRow(data: Partial<Omit<Project, "id" | "createdAt" | "updatedAt">>): Record<string, unknown> {
  const row: Record<string, unknown> = {};
  if (data.name !== undefined) row.name = data.name;
  if (data.location !== undefined) row.location = data.location;
  if (data.crs !== undefined) row.crs = data.crs;
  if (data.notes !== undefined) row.notes = data.notes;
  if (data.materialCategories !== undefined) row.material_categories = JSON.stringify(data.materialCategories);
  return row;
}

// Deserialize DB row → frontend Project
function fromDbRow(row: Record<string, unknown>): Project {
  return {
    id: row.id as number,
    name: row.name as string,
    location: (row.location as string) ?? null,
    crs: (row.crs as Crs) ?? "EPSG:32632",
    notes: (row.notes as string) ?? null,
    materialCategories: row.material_categories
      ? JSON.parse(row.material_categories as string) as string[]
      : [],
    createdAt: row.created_at as string,
    updatedAt: row.updated_at as string,
  };
}

interface ProjectStore {
  projects: Project[];
  selectedProjectId: number | null;
  isLoading: boolean;
  error: string | null;

  loadAll: () => Promise<void>;
  create: (data: Omit<Project, "id" | "createdAt" | "updatedAt">) => Promise<Project>;
  update: (id: number, data: Partial<Omit<Project, "id" | "createdAt" | "updatedAt">>) => Promise<Project>;
  delete: (id: number) => Promise<void>;
  select: (id: number | null) => void;
  getSelected: () => Project | undefined;
}

export const useProjectStore = create<ProjectStore>((set, get) => ({
  projects: [],
  selectedProjectId: null,
  isLoading: false,
  error: null,

  loadAll: async () => {
    set({ isLoading: true, error: null });
    try {
      const rows = await window.api.db.listProjects();
      const projects = rows.map(fromDbRow);
      set({ projects, isLoading: false });
    } catch (err) {
      set({ error: String(err), isLoading: false });
    }
  },

  create: async (data) => {
    set({ error: null });
    try {
      const row = await window.api.db.createProject(toDbRow(data));
      const project = fromDbRow(row);
      set((state) => ({ projects: [project, ...state.projects] }));
      return project;
    } catch (err) {
      set({ error: String(err) });
      throw err;
    }
  },

  update: async (id, data) => {
    set({ error: null });
    try {
      const row = await window.api.db.updateProject(id, toDbRow(data));
      const project = fromDbRow(row);
      set((state) => ({
        projects: state.projects.map((p) => (p.id === id ? project : p)),
      }));
      return project;
    } catch (err) {
      set({ error: String(err) });
      throw err;
    }
  },

  delete: async (id) => {
    set({ error: null });
    try {
      await window.api.db.deleteProject(id);
      set((state) => ({
        projects: state.projects.filter((p) => p.id !== id),
        selectedProjectId: state.selectedProjectId === id ? null : state.selectedProjectId,
      }));
    } catch (err) {
      set({ error: String(err) });
      throw err;
    }
  },

  select: (id) => set({ selectedProjectId: id }),

  getSelected: () => {
    const { projects, selectedProjectId } = get();
    return projects.find((p) => p.id === selectedProjectId);
  },
}));
