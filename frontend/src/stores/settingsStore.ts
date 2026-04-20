/**
 * Settings store — mirrors electron/src/services/settings.ts schema.
 *
 * Persistence is round-tripped via `window.api.settings.*`. The store holds
 * the canonical in-memory copy and exposes a dirty-guarded patch API so the
 * Settings modal can stage edits without committing.
 */

import { create } from "zustand";

export interface Settings {
  general: {
    dataDir: string | null;
    language: "it";
    theme: "dark" | "light";
  };
  processing: {
    overrides: Record<string, number | string | boolean>;
    pythonExecutable: string | null;
  };
  vlm: {
    modelsDir: string | null;
    preferredModel: string | null;
    estimatedVramGb: number;
  };
  report: {
    logoPath: string | null;
    companyName: string;
    defaultOperatorName: string;
    footerText: string;
  };
}

export const defaultSettings: Settings = {
  general: {
    dataDir: null,
    language: "it",
    theme: "dark",
  },
  processing: {
    overrides: {},
    pythonExecutable: null,
  },
  vlm: {
    modelsDir: null,
    preferredModel: null,
    estimatedVramGb: 8,
  },
  report: {
    logoPath: null,
    companyName: "",
    defaultOperatorName: "",
    footerText: "",
  },
};

interface SettingsState {
  settings: Settings;
  loaded: boolean;
  saving: boolean;
  loadFromDisk: () => Promise<void>;
  save: (patch: Partial<Settings>) => Promise<void>;
  reset: () => Promise<void>;
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  settings: defaultSettings,
  loaded: false,
  saving: false,

  loadFromDisk: async () => {
    try {
      const raw = await window.api.settings.load();
      set({ settings: raw as unknown as Settings, loaded: true });
    } catch {
      set({ settings: defaultSettings, loaded: true });
    }
  },

  save: async (patch: Partial<Settings>) => {
    const previous = get().settings;
    // Optimistic update
    const optimistic = deepMerge(previous, patch) as Settings;
    set({ settings: optimistic, saving: true });
    try {
      const saved = await window.api.settings.save(patch as Record<string, unknown>);
      set({ settings: saved as unknown as Settings, saving: false });
    } catch (err) {
      // Rollback
      set({ settings: previous, saving: false });
      throw err;
    }
  },

  reset: async () => {
    const restored = await window.api.settings.reset();
    set({ settings: restored as unknown as Settings });
  },
}));

function deepMerge<T>(base: T, patch: unknown): T {
  if (
    base === null
    || typeof base !== "object"
    || Array.isArray(base)
    || patch === null
    || typeof patch !== "object"
    || Array.isArray(patch)
  ) {
    return (patch ?? base) as T;
  }
  const result: Record<string, unknown> = { ...(base as Record<string, unknown>) };
  for (const [key, value] of Object.entries(patch as Record<string, unknown>)) {
    const current = (base as Record<string, unknown>)[key];
    if (
      current !== null
      && typeof current === "object"
      && !Array.isArray(current)
      && value !== null
      && typeof value === "object"
      && !Array.isArray(value)
    ) {
      result[key] = deepMerge(current, value);
    } else {
      result[key] = value;
    }
  }
  return result as T;
}
