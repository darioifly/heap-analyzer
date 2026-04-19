import { create } from "zustand";
import type { ComparisonState } from "@/lib/comparisonColors";

// ---------------------------------------------------------------------------
// Types mirroring Python MatchResult / HeapMatch
// ---------------------------------------------------------------------------

export interface HeapMatch {
  heap_a_id: number;
  heap_b_id: number;
  iou: number;
  state: ComparisonState;
  delta_volume: number;
  delta_planimetric_area: number;
  delta_max_height: number;
  delta_volume_percent: number;
  a_candidates: number[];
  b_candidates: number[];
}

export interface MatchSummary {
  unchanged: number;
  grown: number;
  decreased: number;
  added: number;
  removed: number;
  ambiguous: number;
}

export interface MatchResult {
  matched: HeapMatch[];
  removed_in_a: number[];
  added_in_b: number[];
  total_delta_volume: number;
  total_delta_volume_percent: number;
  volume_a: number;
  volume_b: number;
  config: {
    iou_threshold: number;
    stability_threshold: number;
    grid_resolution: number | null;
  };
  summary: MatchSummary;
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

interface ComparisonStore {
  activeComparison: MatchResult | null;
  comparisonId: number | null;
  surveyAId: number | null;
  surveyBId: number | null;
  isRunning: boolean;
  progress: { percent: number; message: string } | null;
  error: string | null;

  runComparison: (
    surveyAId: number,
    surveyBId: number,
    config?: { iouThreshold?: number; stabilityThreshold?: number },
  ) => Promise<void>;
  loadComparison: (id: number) => Promise<void>;
  clearComparison: () => void;
  setProgress: (percent: number, message: string) => void;
}

export const useComparisonStore = create<ComparisonStore>((set) => ({
  activeComparison: null,
  comparisonId: null,
  surveyAId: null,
  surveyBId: null,
  isRunning: false,
  progress: null,
  error: null,

  runComparison: async (surveyAId, surveyBId, config) => {
    set({
      isRunning: true,
      error: null,
      progress: { percent: 0, message: "Avvio confronto..." },
      surveyAId,
      surveyBId,
    });

    // Listen for progress events
    const progressHandler = (data: { percent: number; message: string }) => {
      set({ progress: { percent: data.percent, message: data.message } });
    };
    window.api.comparison.onProgress(progressHandler);

    try {
      const { comparisonId, result } = await window.api.comparison.run({
        surveyAId,
        surveyBId,
        iouThreshold: config?.iouThreshold,
        stabilityThreshold: config?.stabilityThreshold,
      });

      set({
        activeComparison: result as unknown as MatchResult,
        comparisonId,
        isRunning: false,
        progress: null,
      });
    } catch (err) {
      set({ error: String(err), isRunning: false, progress: null });
    } finally {
      window.api.comparison.removeProgressListeners();
    }
  },

  loadComparison: async (id) => {
    set({ isRunning: true, error: null });
    try {
      const data = await window.api.comparison.get({ id });
      if (data && data.results) {
        set({
          activeComparison: data.results as unknown as MatchResult,
          comparisonId: data.id,
          surveyAId: data.surveyAId,
          surveyBId: data.surveyBId,
          isRunning: false,
        });
      } else {
        set({ error: "Confronto non trovato", isRunning: false });
      }
    } catch (err) {
      set({ error: String(err), isRunning: false });
    }
  },

  clearComparison: () =>
    set({
      activeComparison: null,
      comparisonId: null,
      surveyAId: null,
      surveyBId: null,
      isRunning: false,
      progress: null,
      error: null,
    }),

  setProgress: (percent, message) =>
    set({ progress: { percent, message } }),
}));
