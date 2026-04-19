/**
 * Zustand store for VLM model management state.
 */

import { create } from 'zustand';

/** GPU hardware status. */
export interface GpuStatus {
  cuda_available: boolean;
  cuda_version: string | null;
  device_name: string | null;
  vram_total_mb: number | null;
  vram_free_mb: number | null;
}

/** VLM model descriptor. */
export interface ModelInfo {
  name: string;
  display_name: string;
  hf_id: string;
  vram_required_mb: number;
  description: string;
  is_downloaded: boolean;
  warns_if_insufficient: boolean;
}

/** Download progress for a single model. */
export interface DownloadProgressInfo {
  model_name: string;
  percent: number;
  message: string;
}

interface VlmState {
  gpuStatus: GpuStatus | null;
  models: ModelInfo[];
  downloadProgress: Record<string, DownloadProgressInfo>;
  loadedModel: string | null;
  isLoading: boolean;
  error: string | null;
}

interface VlmActions {
  refreshGpuStatus: () => Promise<void>;
  refreshModels: () => Promise<void>;
  downloadModel: (modelName: string) => Promise<void>;
  cancelDownload: (modelName: string) => void;
  handleDownloadProgress: (data: DownloadProgressInfo) => void;
}

export const useVlmStore = create<VlmState & VlmActions>((set, get) => ({
  gpuStatus: null,
  models: [],
  downloadProgress: {},
  loadedModel: null,
  isLoading: false,
  error: null,

  refreshGpuStatus: async () => {
    try {
      const status = await window.api.vlm.gpuInfo();
      set({ gpuStatus: status });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      set({ error: msg });
    }
  },

  refreshModels: async () => {
    try {
      const models = await window.api.vlm.listModels();
      set({ models });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      set({ error: msg });
    }
  },

  downloadModel: async (modelName: string) => {
    set((s) => ({
      downloadProgress: {
        ...s.downloadProgress,
        [modelName]: { model_name: modelName, percent: 0, message: 'Avvio download...' },
      },
    }));

    // Listen for progress events
    window.api.vlm.onDownloadProgress((data) => {
      get().handleDownloadProgress(data);
    });

    try {
      await window.api.vlm.download({ modelName });
      // Refresh model list to update download status
      await get().refreshModels();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      set({ error: msg });
    } finally {
      set((s) => {
        const progress = { ...s.downloadProgress };
        delete progress[modelName];
        return { downloadProgress: progress };
      });
      window.api.vlm.removeDownloadListeners();
    }
  },

  cancelDownload: (_modelName: string) => {
    window.api.vlm.cancelDownload();
  },

  handleDownloadProgress: (data: DownloadProgressInfo) => {
    set((s) => ({
      downloadProgress: {
        ...s.downloadProgress,
        [data.model_name]: data,
      },
    }));
  },
}));
