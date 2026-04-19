import { create } from "zustand";

export interface CrossSectionProfile {
  distance: number[];
  dsm_z: (number | null)[];
  dtm_z: (number | null)[];
}

export interface CrossSectionSummary {
  id: number;
  surveyId: number;
  label: string | null;
  lineGeoJSON: string;
  sectionArea: number | null;
  length: number | null;
  maxHeight: number | null;
  bandWidth: number;
}

export interface CrossSectionFull extends CrossSectionSummary {
  profile: CrossSectionProfile;
}

const SECTION_COLORS = [
  "#f59e0b", "#3b82f6", "#10b981", "#ef4444", "#8b5cf6",
  "#ec4899", "#06b6d4", "#f97316",
];

function colorForIndex(idx: number): string {
  return SECTION_COLORS[idx % SECTION_COLORS.length];
}

function fromDbRow(row: Record<string, unknown>): CrossSectionSummary {
  return {
    id: row.id as number,
    surveyId: row.survey_id as number,
    label: (row.label as string) ?? null,
    lineGeoJSON: row.line_geojson as string,
    sectionArea: (row.section_area as number) ?? null,
    length: (row.length as number) ?? null,
    maxHeight: (row.max_height as number) ?? null,
    bandWidth: (row.band_width as number) ?? 1.0,
  };
}

function fullFromDbRow(row: Record<string, unknown>): CrossSectionFull {
  const summary = fromDbRow(row);
  const profileJson = row.profile_json as string | null;
  const profile: CrossSectionProfile = profileJson
    ? JSON.parse(profileJson) as CrossSectionProfile
    : { distance: [], dsm_z: [], dtm_z: [] };
  return { ...summary, profile };
}

interface CrossSectionStore {
  sections: CrossSectionSummary[];
  selectedId: number | null;
  fullCache: Record<number, CrossSectionFull>;
  panelOpen: boolean;

  loadForSurvey: (surveyId: number) => Promise<void>;
  create: (surveyId: number, lineGeoJSON: string, label?: string) => Promise<CrossSectionSummary>;
  select: (id: number | null) => Promise<void>;
  updateBandWidth: (id: number, width: number) => Promise<void>;
  updateLabel: (id: number, label: string) => Promise<void>;
  remove: (id: number) => Promise<void>;
  recompute: (id: number) => Promise<void>;
  setPanelOpen: (open: boolean) => void;
  getColor: (id: number) => string;
  getFull: (id: number) => CrossSectionFull | undefined;
  clear: () => void;
}

export const useCrossSectionStore = create<CrossSectionStore>((set, get) => ({
  sections: [],
  selectedId: null,
  fullCache: {},
  panelOpen: false,

  loadForSurvey: async (surveyId) => {
    try {
      const rows = await window.api.crossSection.list({ surveyId });
      const sections = rows.map(fromDbRow);
      set({ sections, selectedId: null, fullCache: {}, panelOpen: false });
    } catch (err) {
      console.error("Failed to load cross sections:", err);
    }
  },

  create: async (surveyId, lineGeoJSON, label) => {
    const row = await window.api.crossSection.create({ surveyId, lineGeoJSON, label });
    const summary = fromDbRow(row);
    const full = fullFromDbRow(row);
    set((s) => ({
      sections: [summary, ...s.sections],
      selectedId: summary.id,
      fullCache: { ...s.fullCache, [summary.id]: full },
      panelOpen: true,
    }));
    return summary;
  },

  select: async (id) => {
    if (id === null) {
      set({ selectedId: null });
      return;
    }
    set({ selectedId: id, panelOpen: true });
    // Load full data if not cached
    if (!get().fullCache[id]) {
      try {
        const row = await window.api.crossSection.get({ id });
        if (row) {
          const full = fullFromDbRow(row);
          set((s) => ({ fullCache: { ...s.fullCache, [id]: full } }));
        }
      } catch (err) {
        console.error("Failed to load cross section:", err);
      }
    }
  },

  updateBandWidth: async (id, width) => {
    // Optimistic update
    set((s) => ({
      sections: s.sections.map((sec) =>
        sec.id === id ? { ...sec, bandWidth: width } : sec,
      ),
      fullCache: s.fullCache[id]
        ? { ...s.fullCache, [id]: { ...s.fullCache[id], bandWidth: width } }
        : s.fullCache,
    }));
    await window.api.crossSection.update({ id, patch: { band_width: width } });
  },

  updateLabel: async (id, label) => {
    set((s) => ({
      sections: s.sections.map((sec) =>
        sec.id === id ? { ...sec, label } : sec,
      ),
      fullCache: s.fullCache[id]
        ? { ...s.fullCache, [id]: { ...s.fullCache[id], label } }
        : s.fullCache,
    }));
    await window.api.crossSection.update({ id, patch: { label } });
  },

  remove: async (id) => {
    await window.api.crossSection.delete({ id });
    set((s) => {
      const newSections = s.sections.filter((sec) => sec.id !== id);
      const newCache = { ...s.fullCache };
      delete newCache[id];
      return {
        sections: newSections,
        selectedId: s.selectedId === id ? null : s.selectedId,
        fullCache: newCache,
        panelOpen: s.selectedId === id && newSections.length === 0 ? false : s.panelOpen,
      };
    });
  },

  recompute: async (id) => {
    const row = await window.api.crossSection.recompute({ id });
    const summary = fromDbRow(row);
    const full = fullFromDbRow(row);
    set((s) => ({
      sections: s.sections.map((sec) => (sec.id === id ? summary : sec)),
      fullCache: { ...s.fullCache, [id]: full },
    }));
  },

  setPanelOpen: (open) => set({ panelOpen: open }),

  getColor: (id) => {
    const idx = get().sections.findIndex((s) => s.id === id);
    return colorForIndex(idx >= 0 ? idx : 0);
  },

  getFull: (id) => get().fullCache[id],

  clear: () => set({ sections: [], selectedId: null, fullCache: {}, panelOpen: false }),
}));
