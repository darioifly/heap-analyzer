import { vi } from "vitest";

/** Create a fully typed mock of window.api for tests. */
export function setupMockApi(overrides?: {
  projects?: Record<string, unknown>[];
  surveys?: Record<string, unknown>[];
  heaps?: Record<string, unknown>[];
}) {
  window.api = {
    python: {
      execute: vi.fn(),
      cancel: vi.fn(),
      onProgress: vi.fn(),
      onWarning: vi.fn(),
      removeAllListeners: vi.fn(),
    },
    db: {
      listProjects: vi.fn().mockResolvedValue(overrides?.projects ?? []),
      createProject: vi.fn().mockImplementation((data) =>
        Promise.resolve({ id: Date.now(), ...data, created_at: "2026-01-01", updated_at: "2026-01-01" }),
      ),
      updateProject: vi.fn().mockImplementation((_id, data) =>
        Promise.resolve({ id: _id, ...data, created_at: "2026-01-01", updated_at: "2026-01-01" }),
      ),
      deleteProject: vi.fn().mockResolvedValue(undefined),
      listSurveys: vi.fn().mockResolvedValue(overrides?.surveys ?? []),
      createSurvey: vi.fn().mockImplementation((data) =>
        Promise.resolve({ id: Date.now(), ...data, created_at: "2026-01-01", updated_at: "2026-01-01" }),
      ),
      updateSurvey: vi.fn().mockImplementation((_id, data) =>
        Promise.resolve({ id: _id, ...data, created_at: "2026-01-01", updated_at: "2026-01-01" }),
      ),
      deleteSurvey: vi.fn().mockResolvedValue(undefined),
      listHeaps: vi.fn().mockResolvedValue(overrides?.heaps ?? []),
      createHeap: vi.fn(),
      updateHeap: vi.fn().mockImplementation((_id, data) =>
        Promise.resolve({ id: _id, ...data, created_at: "2026-01-01", updated_at: "2026-01-01" }),
      ),
      bulkCreateHeaps: vi.fn().mockResolvedValue([]),
    },
    shell: {
      showItemInFolder: vi.fn().mockResolvedValue(undefined),
    },
    tiles: {
      getBaseUrl: vi.fn().mockResolvedValue("http://127.0.0.1:3001"),
      getMetadata: vi.fn().mockResolvedValue(null),
    },
    dialog: {
      openFile: vi.fn().mockResolvedValue(null),
      saveFile: vi.fn().mockResolvedValue(null),
    },
    elevation: {
      recomputeAll: vi.fn().mockResolvedValue({ heaps: [], baseElevation: 100 }),
      sampleGround: vi.fn().mockResolvedValue({
        mean_elevation: 100.0, std_elevation: 0.01, num_pixels: 1000,
        per_polygon: [{ mean: 100.0, std: 0.01, num_pixels: 1000 }],
      }),
    },
    crossSection: {
      create: vi.fn().mockResolvedValue({ id: 1 }),
      list: vi.fn().mockResolvedValue([]),
      get: vi.fn().mockResolvedValue(null),
      update: vi.fn().mockResolvedValue({}),
      delete: vi.fn().mockResolvedValue({ ok: true }),
      recompute: vi.fn().mockResolvedValue({}),
    },
    potree: {
      convert: vi.fn().mockResolvedValue({}),
      getStatus: vi.fn().mockResolvedValue({ available: false }),
    },
    vlm: {
      gpuInfo: vi.fn().mockResolvedValue({
        cuda_available: false, cuda_version: null, device_name: null,
        vram_total_mb: null, vram_free_mb: null,
      }),
      listModels: vi.fn().mockResolvedValue([]),
      isDownloaded: vi.fn().mockResolvedValue(false),
      download: vi.fn().mockResolvedValue({ success: true }),
      cancelDownload: vi.fn().mockResolvedValue({ success: true }),
      onDownloadProgress: vi.fn(),
      removeDownloadListeners: vi.fn(),
    },
    editing: {
      createHeap: vi.fn().mockResolvedValue({ id: 999 }),
      recomputeHeap: vi.fn().mockResolvedValue({ id: 1 }),
      deleteHeap: vi.fn().mockResolvedValue({ ok: true }),
      splitHeap: vi.fn().mockResolvedValue([]),
      mergeHeaps: vi.fn().mockResolvedValue({ id: 1 }),
      restoreSnapshot: vi.fn().mockResolvedValue([]),
    },
  };
}
