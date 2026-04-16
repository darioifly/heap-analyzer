import { describe, it, expect, beforeEach } from "vitest";
import { useProcessingStore } from "./processingStore";

describe("processingStore", () => {
  beforeEach(() => {
    useProcessingStore.getState().reset();
  });

  it("transitions from idle to running", () => {
    useProcessingStore.getState().start(1);
    const state = useProcessingStore.getState();
    expect(state.isRunning).toBe(true);
    expect(state.surveyId).toBe(1);
    expect(state.startTime).toBeTypeOf("number");
  });

  it("updates progress", () => {
    useProcessingStore.getState().start(1);
    useProcessingStore.getState().updateProgress({
      phase: "dsm",
      percent: 45,
      message: "Generazione DSM...",
    });
    expect(useProcessingStore.getState().progress?.percent).toBe(45);
  });

  it("accumulates warnings", () => {
    useProcessingStore.getState().start(1);
    useProcessingStore.getState().addWarning("Warning 1");
    useProcessingStore.getState().addWarning("Warning 2");
    expect(useProcessingStore.getState().warnings).toHaveLength(2);
  });

  it("transitions to completed", () => {
    useProcessingStore.getState().start(1);
    useProcessingStore.getState().complete();
    const state = useProcessingStore.getState();
    expect(state.isRunning).toBe(false);
    expect(state.progress?.percent).toBe(100);
  });

  it("transitions to failed", () => {
    useProcessingStore.getState().start(1);
    useProcessingStore.getState().fail("CRS mismatch");
    const state = useProcessingStore.getState();
    expect(state.isRunning).toBe(false);
    expect(state.error).toBe("CRS mismatch");
  });

  it("cancel stops processing", () => {
    useProcessingStore.getState().start(1);
    useProcessingStore.getState().cancel();
    expect(useProcessingStore.getState().isRunning).toBe(false);
  });
});
