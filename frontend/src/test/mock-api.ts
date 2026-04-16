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
    dialog: {
      openFile: vi.fn().mockResolvedValue(null),
      saveFile: vi.fn().mockResolvedValue(null),
    },
  };
}
