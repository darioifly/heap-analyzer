import { create } from "zustand";
import type { ProcessingProgress } from "@/types";

interface ProcessingStore {
  isRunning: boolean;
  surveyId: number | null;
  progress: ProcessingProgress | null;
  startTime: number | null;
  warnings: string[];
  error: string | null;

  start: (surveyId: number) => void;
  updateProgress: (progress: ProcessingProgress) => void;
  addWarning: (warning: string) => void;
  complete: () => void;
  fail: (error: string) => void;
  cancel: () => void;
  reset: () => void;
}

export const useProcessingStore = create<ProcessingStore>((set) => ({
  isRunning: false,
  surveyId: null,
  progress: null,
  startTime: null,
  warnings: [],
  error: null,

  start: (surveyId) =>
    set({
      isRunning: true,
      surveyId,
      progress: null,
      startTime: Date.now(),
      warnings: [],
      error: null,
    }),

  updateProgress: (progress) => set({ progress }),

  addWarning: (warning) =>
    set((state) => ({ warnings: [...state.warnings, warning] })),

  complete: () =>
    set({
      isRunning: false,
      progress: { phase: "done", percent: 100, message: "Completato" },
    }),

  fail: (error) =>
    set({
      isRunning: false,
      error,
    }),

  cancel: () =>
    set({
      isRunning: false,
      progress: null,
      error: null,
    }),

  reset: () =>
    set({
      isRunning: false,
      surveyId: null,
      progress: null,
      startTime: null,
      warnings: [],
      error: null,
    }),
}));
