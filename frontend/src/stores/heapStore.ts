import { create } from "zustand";
import type { Heap } from "@/types";
import type { Polygon } from "geojson";

function fromDbRow(row: Record<string, unknown>): Heap {
  return {
    id: row.id as number,
    surveyId: row.survey_id as number,
    label: (row.label as string) ?? null,
    polygon: (typeof row.polygon === "string" ? JSON.parse(row.polygon) : row.polygon) as Polygon,
    volume: row.volume as number,
    planimetricArea: row.planimetric_area as number,
    surfaceArea: row.surface_area as number,
    maxHeight: row.max_height as number,
    meanHeight: row.mean_height as number,
    baseElevation: row.base_elevation as number,
    centroidE: row.centroid_e as number,
    centroidN: row.centroid_n as number,
    bboxMinE: row.bbox_min_e as number,
    bboxMinN: row.bbox_min_n as number,
    bboxMaxE: row.bbox_max_e as number,
    bboxMaxN: row.bbox_max_n as number,
    materialCategory: (row.material_category as string) ?? null,
    materialConfidence: (row.material_confidence as number) ?? null,
    isManuallyConfirmed: Boolean(row.is_manually_confirmed),
    isExcluded: Boolean(row.is_excluded),
    createdAt: row.created_at as string,
    updatedAt: row.updated_at as string,
  };
}

function toDbRow(data: Partial<Omit<Heap, "id" | "createdAt" | "updatedAt">>): Record<string, unknown> {
  const row: Record<string, unknown> = {};
  if (data.surveyId !== undefined) row.survey_id = data.surveyId;
  if (data.label !== undefined) row.label = data.label;
  if (data.polygon !== undefined) row.polygon = JSON.stringify(data.polygon);
  if (data.volume !== undefined) row.volume = data.volume;
  if (data.planimetricArea !== undefined) row.planimetric_area = data.planimetricArea;
  if (data.surfaceArea !== undefined) row.surface_area = data.surfaceArea;
  if (data.maxHeight !== undefined) row.max_height = data.maxHeight;
  if (data.meanHeight !== undefined) row.mean_height = data.meanHeight;
  if (data.baseElevation !== undefined) row.base_elevation = data.baseElevation;
  if (data.centroidE !== undefined) row.centroid_e = data.centroidE;
  if (data.centroidN !== undefined) row.centroid_n = data.centroidN;
  if (data.bboxMinE !== undefined) row.bbox_min_e = data.bboxMinE;
  if (data.bboxMinN !== undefined) row.bbox_min_n = data.bboxMinN;
  if (data.bboxMaxE !== undefined) row.bbox_max_e = data.bboxMaxE;
  if (data.bboxMaxN !== undefined) row.bbox_max_n = data.bboxMaxN;
  if (data.materialCategory !== undefined) row.material_category = data.materialCategory;
  if (data.materialConfidence !== undefined) row.material_confidence = data.materialConfidence;
  if (data.isManuallyConfirmed !== undefined) row.is_manually_confirmed = data.isManuallyConfirmed ? 1 : 0;
  if (data.isExcluded !== undefined) row.is_excluded = data.isExcluded ? 1 : 0;
  return row;
}

interface HeapStore {
  heaps: Heap[];
  selectedHeapId: number | null;
  isLoading: boolean;
  error: string | null;

  loadBySurvey: (surveyId: number) => Promise<void>;
  bulkCreate: (heaps: Omit<Heap, "id" | "createdAt" | "updatedAt">[]) => Promise<Heap[]>;
  update: (id: number, data: Partial<Omit<Heap, "id" | "createdAt" | "updatedAt">>) => Promise<Heap>;
  select: (id: number | null) => void;
  clear: () => void;
}

export const useHeapStore = create<HeapStore>((set) => ({
  heaps: [],
  selectedHeapId: null,
  isLoading: false,
  error: null,

  loadBySurvey: async (surveyId) => {
    set({ isLoading: true, error: null });
    try {
      const rows = await window.api.db.listHeaps(surveyId);
      const heaps = rows.map(fromDbRow);
      set({ heaps, isLoading: false });
    } catch (err) {
      set({ error: String(err), isLoading: false });
    }
  },

  bulkCreate: async (heapData) => {
    set({ error: null });
    try {
      const dbRows = heapData.map(toDbRow);
      const rows = await window.api.db.bulkCreateHeaps(dbRows);
      const heaps = rows.map(fromDbRow);
      set((state) => ({ heaps: [...state.heaps, ...heaps] }));
      return heaps;
    } catch (err) {
      set({ error: String(err) });
      throw err;
    }
  },

  update: async (id, data) => {
    set({ error: null });
    try {
      const row = await window.api.db.updateHeap(id, toDbRow(data));
      const heap = fromDbRow(row);
      set((state) => ({
        heaps: state.heaps.map((h) => (h.id === id ? heap : h)),
      }));
      return heap;
    } catch (err) {
      set({ error: String(err) });
      throw err;
    }
  },

  select: (id) => set({ selectedHeapId: id }),

  clear: () => set({ heaps: [], selectedHeapId: null }),
}));
