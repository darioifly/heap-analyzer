/**
 * Zustand store for PDF report generation state.
 */

import { create } from "zustand";

export type ReportFormat = "pdf" | "csv" | "pdf+csv";

export interface ReportProgress {
  phase: string;
  percent: number;
  message: string;
}

export interface ReportGeneratePayload {
  surveyId: number;
  format: ReportFormat;
  destinationDir: string;
  logoPath: string | null;
  companyName: string | null;
  notes: string | null;
  onlyConfirmed: boolean;
}

interface ReportState {
  isGenerating: boolean;
  progress: ReportProgress | null;
  lastResult: { paths: string[] } | null;
  lastError: string | null;
}

interface ReportActions {
  startGeneration: (payload: ReportGeneratePayload) => Promise<void>;
  cancelGeneration: () => void;
  handleProgress: (payload: ReportProgress) => void;
  handleComplete: (result: { paths: string[] }) => void;
  handleError: (err: string) => void;
  reset: () => void;
}

type ReportStore = ReportState & ReportActions;

export const useReportStore = create<ReportStore>((set) => ({
  isGenerating: false,
  progress: null,
  lastResult: null,
  lastError: null,

  startGeneration: async (payload) => {
    set({ isGenerating: true, progress: null, lastResult: null, lastError: null });

    // Register progress listener
    window.api.report.onProgress((data: ReportProgress) => {
      set({ progress: data });
    });

    try {
      const result = await window.api.report.generate(payload);
      set({
        isGenerating: false,
        lastResult: { paths: result.outputPaths },
        progress: null,
      });
    } catch (err) {
      set({
        isGenerating: false,
        lastError: String(err),
        progress: null,
      });
    } finally {
      window.api.report.removeProgressListeners();
    }
  },

  cancelGeneration: () => {
    window.api.report.cancel();
    set({ isGenerating: false, progress: null });
  },

  handleProgress: (payload) => {
    set({ progress: payload });
  },

  handleComplete: (result) => {
    set({ isGenerating: false, lastResult: result, progress: null });
  },

  handleError: (err) => {
    set({ isGenerating: false, lastError: err, progress: null });
  },

  reset: () => {
    set({ isGenerating: false, progress: null, lastResult: null, lastError: null });
  },
}));
