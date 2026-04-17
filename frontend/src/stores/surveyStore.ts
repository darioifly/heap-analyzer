import { create } from "zustand";
import type { ProcessingStatus, Survey } from "@/types";

function toDbRow(data: Partial<Omit<Survey, "id" | "createdAt" | "updatedAt">>): Record<string, unknown> {
  const row: Record<string, unknown> = {};
  if (data.projectId !== undefined) row.project_id = data.projectId;
  if (data.surveyDate !== undefined) row.survey_date = data.surveyDate;
  if (data.operator !== undefined) row.operator = data.operator;
  if (data.lasPath !== undefined) row.las_path = data.lasPath;
  if (data.tiffPath !== undefined) row.tiff_path = data.tiffPath;
  if (data.processingParams !== undefined) row.processing_params = data.processingParams ? JSON.stringify(data.processingParams) : null;
  if (data.processingStatus !== undefined) row.processing_status = data.processingStatus;
  if (data.dsmPath !== undefined) row.dsm_path = data.dsmPath;
  if (data.dtmPath !== undefined) row.dtm_path = data.dtmPath;
  if (data.ndsmPath !== undefined) row.ndsm_path = data.ndsmPath;
  if (data.labelMapPath !== undefined) row.label_map_path = data.labelMapPath;
  if (data.tilesPath !== undefined) row.tiles_path = data.tilesPath;
  if (data.ndsmHeatmapPath !== undefined) row.ndsm_heatmap_path = data.ndsmHeatmapPath;
  if (data.baseElevation !== undefined) row.base_elevation = data.baseElevation;
  if (data.potreePath !== undefined) row.potree_path = data.potreePath;
  return row;
}

function fromDbRow(row: Record<string, unknown>): Survey {
  return {
    id: row.id as number,
    projectId: row.project_id as number,
    surveyDate: row.survey_date as string,
    operator: (row.operator as string) ?? null,
    lasPath: row.las_path as string,
    tiffPath: row.tiff_path as string,
    processingParams: row.processing_params
      ? JSON.parse(row.processing_params as string) as Record<string, unknown>
      : null,
    processingStatus: (row.processing_status as ProcessingStatus) ?? "pending",
    dsmPath: (row.dsm_path as string) ?? null,
    dtmPath: (row.dtm_path as string) ?? null,
    ndsmPath: (row.ndsm_path as string) ?? null,
    labelMapPath: (row.label_map_path as string) ?? null,
    tilesPath: (row.tiles_path as string) ?? null,
    ndsmHeatmapPath: (row.ndsm_heatmap_path as string) ?? null,
    baseElevation: (row.base_elevation as number) ?? null,
    potreePath: (row.potree_path as string) ?? null,
    createdAt: row.created_at as string,
    updatedAt: row.updated_at as string,
  };
}

interface SurveyStore {
  surveys: Survey[];
  selectedSurveyId: number | null;
  isLoading: boolean;
  error: string | null;

  loadByProject: (projectId: number) => Promise<void>;
  create: (data: Omit<Survey, "id" | "createdAt" | "updatedAt" | "processingStatus" | "dsmPath" | "dtmPath" | "ndsmPath" | "labelMapPath" | "tilesPath" | "ndsmHeatmapPath" | "baseElevation" | "potreePath">) => Promise<Survey>;
  update: (id: number, data: Partial<Omit<Survey, "id" | "createdAt" | "updatedAt">>) => Promise<Survey>;
  delete: (id: number) => Promise<void>;
  select: (id: number | null) => void;
  clear: () => void;
}

export const useSurveyStore = create<SurveyStore>((set) => ({
  surveys: [],
  selectedSurveyId: null,
  isLoading: false,
  error: null,

  loadByProject: async (projectId) => {
    set({ isLoading: true, error: null });
    try {
      const rows = await window.api.db.listSurveys(projectId);
      const surveys = rows.map(fromDbRow);
      set({ surveys, isLoading: false });
    } catch (err) {
      set({ error: String(err), isLoading: false });
    }
  },

  create: async (data) => {
    set({ error: null });
    try {
      const dbData = {
        ...toDbRow(data),
        processing_status: "pending",
        dsm_path: null,
        dtm_path: null,
        ndsm_path: null,
        label_map_path: null,
        tiles_path: null,
        ndsm_heatmap_path: null,
        base_elevation: null,
        potree_path: null,
      };
      const row = await window.api.db.createSurvey(dbData);
      const survey = fromDbRow(row);
      set((state) => ({ surveys: [survey, ...state.surveys] }));
      return survey;
    } catch (err) {
      set({ error: String(err) });
      throw err;
    }
  },

  update: async (id, data) => {
    set({ error: null });
    try {
      const row = await window.api.db.updateSurvey(id, toDbRow(data));
      const survey = fromDbRow(row);
      set((state) => ({
        surveys: state.surveys.map((s) => (s.id === id ? survey : s)),
      }));
      return survey;
    } catch (err) {
      set({ error: String(err) });
      throw err;
    }
  },

  delete: async (id) => {
    set({ error: null });
    try {
      await window.api.db.deleteSurvey(id);
      set((state) => ({
        surveys: state.surveys.filter((s) => s.id !== id),
        selectedSurveyId: state.selectedSurveyId === id ? null : state.selectedSurveyId,
      }));
    } catch (err) {
      set({ error: String(err) });
      throw err;
    }
  },

  select: (id) => set({ selectedSurveyId: id }),

  clear: () => set({ surveys: [], selectedSurveyId: null }),
}));
