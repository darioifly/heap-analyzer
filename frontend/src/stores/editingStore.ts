import { create } from "zustand";
import type { Heap } from "@/types";

export type EditingTool =
  | "select"
  | "draw"
  | "modify"
  | "split"
  | "merge"
  | "delete"
  | "ground-select";

interface HistoryEntry {
  op: "create" | "modify" | "delete" | "split" | "merge";
  timestamp: number;
  /** Snapshot of affected heaps BEFORE the operation. */
  before: Heap[];
  /** Snapshot of affected heaps AFTER the operation. */
  after: Heap[];
  surveyId: number;
}

const MAX_HISTORY = 20;

interface EditingState {
  activeTool: EditingTool;
  undoStack: HistoryEntry[];
  redoStack: HistoryEntry[];
  /** IDs of heaps selected for merge (multi-select via Shift+click). */
  mergeSelection: number[];
  /** Suggested base elevation from ground selection tool (F3.S02). */
  suggestedBaseElevation: number | null;

  setTool: (tool: EditingTool) => void;
  pushHistory: (entry: HistoryEntry) => void;
  canUndo: () => boolean;
  canRedo: () => boolean;
  undo: () => HistoryEntry | undefined;
  redo: () => HistoryEntry | undefined;
  clearHistory: (surveyId?: number) => void;
  toggleMergeSelection: (heapId: number) => void;
  clearMergeSelection: () => void;
  setSuggestedBaseElevation: (value: number | null) => void;
}

export const useEditingStore = create<EditingState>((set, get) => ({
  activeTool: "select",
  undoStack: [],
  redoStack: [],
  mergeSelection: [],
  suggestedBaseElevation: null,

  setTool: (tool) => {
    set({ activeTool: tool });
    // Clear merge selection when switching away from merge
    if (tool !== "merge" && tool !== "select") {
      set({ mergeSelection: [] });
    }
  },

  pushHistory: (entry) => {
    set((state) => {
      const newStack = [...state.undoStack, entry];
      // Cap at MAX_HISTORY — drop oldest
      if (newStack.length > MAX_HISTORY) {
        newStack.splice(0, newStack.length - MAX_HISTORY);
      }
      return { undoStack: newStack, redoStack: [] };
    });
  },

  canUndo: () => get().undoStack.length > 0,
  canRedo: () => get().redoStack.length > 0,

  undo: () => {
    const state = get();
    if (state.undoStack.length === 0) return undefined;
    const entry = state.undoStack[state.undoStack.length - 1];
    set({
      undoStack: state.undoStack.slice(0, -1),
      redoStack: [...state.redoStack, entry],
    });
    return entry;
  },

  redo: () => {
    const state = get();
    if (state.redoStack.length === 0) return undefined;
    const entry = state.redoStack[state.redoStack.length - 1];
    set({
      redoStack: state.redoStack.slice(0, -1),
      undoStack: [...state.undoStack, entry],
    });
    return entry;
  },

  clearHistory: (surveyId) => {
    if (surveyId !== undefined) {
      set((state) => ({
        undoStack: state.undoStack.filter((e) => e.surveyId !== surveyId),
        redoStack: state.redoStack.filter((e) => e.surveyId !== surveyId),
      }));
    } else {
      set({ undoStack: [], redoStack: [] });
    }
  },

  toggleMergeSelection: (heapId) => {
    set((state) => {
      const idx = state.mergeSelection.indexOf(heapId);
      if (idx >= 0) {
        return {
          mergeSelection: state.mergeSelection.filter((id) => id !== heapId),
        };
      }
      return { mergeSelection: [...state.mergeSelection, heapId] };
    });
  },

  clearMergeSelection: () => set({ mergeSelection: [] }),

  setSuggestedBaseElevation: (value) => set({ suggestedBaseElevation: value }),
}));
