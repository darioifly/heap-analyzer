import { describe, it, expect, beforeEach } from "vitest";
import { useEditingStore } from "./editingStore";
import type { Heap } from "@/types";

const mockHeap = (id: number): Heap => ({
  id,
  surveyId: 1,
  label: `Heap ${id}`,
  polygon: { type: "Polygon", coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] },
  volume: 100,
  planimetricArea: 50,
  surfaceArea: 55,
  maxHeight: 3,
  meanHeight: 2,
  baseElevation: 100,
  centroidE: 500000,
  centroidN: 5000000,
  bboxMinE: 499990,
  bboxMinN: 4999990,
  bboxMaxE: 500010,
  bboxMaxN: 5000010,
  materialCategory: null,
  materialConfidence: null,
  isManuallyConfirmed: false,
  isExcluded: false,
  createdAt: "2026-01-01",
  updatedAt: "2026-01-01",
});

describe("editingStore", () => {
  beforeEach(() => {
    // Reset store state
    useEditingStore.setState({
      activeTool: "select",
      undoStack: [],
      redoStack: [],
      mergeSelection: [],
    });
  });

  describe("setTool", () => {
    it("sets the active tool", () => {
      useEditingStore.getState().setTool("draw");
      expect(useEditingStore.getState().activeTool).toBe("draw");
    });

    it("clears merge selection when switching away from merge/select", () => {
      useEditingStore.setState({ mergeSelection: [1, 2] });
      useEditingStore.getState().setTool("draw");
      expect(useEditingStore.getState().mergeSelection).toEqual([]);
    });

    it("preserves merge selection when switching to select", () => {
      useEditingStore.setState({ mergeSelection: [1, 2], activeTool: "merge" });
      useEditingStore.getState().setTool("select");
      expect(useEditingStore.getState().mergeSelection).toEqual([1, 2]);
    });
  });

  describe("history", () => {
    it("push adds to undo stack", () => {
      useEditingStore.getState().pushHistory({
        op: "create",
        timestamp: Date.now(),
        before: [],
        after: [mockHeap(1)],
        surveyId: 1,
      });
      expect(useEditingStore.getState().undoStack).toHaveLength(1);
    });

    it("push clears redo stack", () => {
      // Simulate having a redo entry
      useEditingStore.setState({
        redoStack: [{
          op: "create",
          timestamp: Date.now(),
          before: [],
          after: [mockHeap(1)],
          surveyId: 1,
        }],
      });

      useEditingStore.getState().pushHistory({
        op: "modify",
        timestamp: Date.now(),
        before: [mockHeap(1)],
        after: [mockHeap(1)],
        surveyId: 1,
      });

      expect(useEditingStore.getState().redoStack).toHaveLength(0);
    });

    it("caps undo stack at 20 entries", () => {
      for (let i = 0; i < 25; i++) {
        useEditingStore.getState().pushHistory({
          op: "create",
          timestamp: Date.now() + i,
          before: [],
          after: [mockHeap(i)],
          surveyId: 1,
        });
      }
      expect(useEditingStore.getState().undoStack).toHaveLength(20);
    });

    it("undo pops from undo and pushes to redo", () => {
      useEditingStore.getState().pushHistory({
        op: "create",
        timestamp: Date.now(),
        before: [],
        after: [mockHeap(1)],
        surveyId: 1,
      });

      const entry = useEditingStore.getState().undo();

      expect(entry).toBeDefined();
      expect(entry?.op).toBe("create");
      expect(useEditingStore.getState().undoStack).toHaveLength(0);
      expect(useEditingStore.getState().redoStack).toHaveLength(1);
    });

    it("redo pops from redo and pushes to undo", () => {
      useEditingStore.getState().pushHistory({
        op: "create",
        timestamp: Date.now(),
        before: [],
        after: [mockHeap(1)],
        surveyId: 1,
      });
      useEditingStore.getState().undo();

      const entry = useEditingStore.getState().redo();

      expect(entry).toBeDefined();
      expect(entry?.op).toBe("create");
      expect(useEditingStore.getState().undoStack).toHaveLength(1);
      expect(useEditingStore.getState().redoStack).toHaveLength(0);
    });

    it("undo returns undefined when stack is empty", () => {
      const entry = useEditingStore.getState().undo();
      expect(entry).toBeUndefined();
    });

    it("redo returns undefined when stack is empty", () => {
      const entry = useEditingStore.getState().redo();
      expect(entry).toBeUndefined();
    });

    it("canUndo returns correct boolean", () => {
      expect(useEditingStore.getState().canUndo()).toBe(false);
      useEditingStore.getState().pushHistory({
        op: "create",
        timestamp: Date.now(),
        before: [],
        after: [mockHeap(1)],
        surveyId: 1,
      });
      expect(useEditingStore.getState().canUndo()).toBe(true);
    });

    it("canRedo returns correct boolean", () => {
      expect(useEditingStore.getState().canRedo()).toBe(false);
      useEditingStore.getState().pushHistory({
        op: "create",
        timestamp: Date.now(),
        before: [],
        after: [mockHeap(1)],
        surveyId: 1,
      });
      useEditingStore.getState().undo();
      expect(useEditingStore.getState().canRedo()).toBe(true);
    });

    it("clearHistory clears all when no surveyId", () => {
      useEditingStore.getState().pushHistory({
        op: "create",
        timestamp: Date.now(),
        before: [],
        after: [mockHeap(1)],
        surveyId: 1,
      });
      useEditingStore.getState().clearHistory();
      expect(useEditingStore.getState().undoStack).toHaveLength(0);
      expect(useEditingStore.getState().redoStack).toHaveLength(0);
    });

    it("clearHistory filters by surveyId", () => {
      useEditingStore.getState().pushHistory({
        op: "create",
        timestamp: Date.now(),
        before: [],
        after: [mockHeap(1)],
        surveyId: 1,
      });
      useEditingStore.getState().pushHistory({
        op: "create",
        timestamp: Date.now(),
        before: [],
        after: [mockHeap(2)],
        surveyId: 2,
      });
      useEditingStore.getState().clearHistory(1);
      expect(useEditingStore.getState().undoStack).toHaveLength(1);
      expect(useEditingStore.getState().undoStack[0].surveyId).toBe(2);
    });
  });

  describe("merge selection", () => {
    it("toggleMergeSelection adds and removes", () => {
      useEditingStore.getState().toggleMergeSelection(1);
      expect(useEditingStore.getState().mergeSelection).toEqual([1]);

      useEditingStore.getState().toggleMergeSelection(2);
      expect(useEditingStore.getState().mergeSelection).toEqual([1, 2]);

      useEditingStore.getState().toggleMergeSelection(1);
      expect(useEditingStore.getState().mergeSelection).toEqual([2]);
    });

    it("clearMergeSelection empties the array", () => {
      useEditingStore.setState({ mergeSelection: [1, 2, 3] });
      useEditingStore.getState().clearMergeSelection();
      expect(useEditingStore.getState().mergeSelection).toEqual([]);
    });
  });
});
