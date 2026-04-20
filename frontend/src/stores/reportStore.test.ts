import { describe, it, expect, beforeEach } from "vitest";
import { setupMockApi } from "@/test/mock-api";
import { useReportStore } from "./reportStore";

describe("reportStore", () => {
  beforeEach(() => {
    setupMockApi();
    useReportStore.setState({
      isGenerating: false,
      progress: null,
      lastResult: null,
      lastError: null,
    });
  });

  it("starts in idle state", () => {
    const state = useReportStore.getState();
    expect(state.isGenerating).toBe(false);
    expect(state.progress).toBeNull();
    expect(state.lastResult).toBeNull();
    expect(state.lastError).toBeNull();
  });

  it("startGeneration sets isGenerating=true and calls IPC", async () => {
    const store = useReportStore.getState();

    await store.startGeneration({
      surveyId: 1,
      format: "pdf",
      destinationDir: "/tmp/test",
      logoPath: null,
      companyName: null,
      notes: null,
      onlyConfirmed: false,
    });

    expect(window.api.report.generate).toHaveBeenCalledWith({
      surveyId: 1,
      format: "pdf",
      destinationDir: "/tmp/test",
      logoPath: null,
      companyName: null,
      notes: null,
      onlyConfirmed: false,
    });

    // After successful completion
    const finalState = useReportStore.getState();
    expect(finalState.isGenerating).toBe(false);
    expect(finalState.lastResult).not.toBeNull();
  });

  it("handleProgress updates progress state", () => {
    useReportStore.getState().handleProgress({
      phase: "overview",
      percent: 50,
      message: "Rendering...",
    });

    const state = useReportStore.getState();
    expect(state.progress?.phase).toBe("overview");
    expect(state.progress?.percent).toBe(50);
  });

  it("handleComplete sets lastResult and clears isGenerating", () => {
    useReportStore.setState({ isGenerating: true });
    useReportStore.getState().handleComplete({ paths: ["/tmp/report.pdf"] });

    const state = useReportStore.getState();
    expect(state.isGenerating).toBe(false);
    expect(state.lastResult?.paths).toEqual(["/tmp/report.pdf"]);
  });

  it("handleError sets lastError and clears isGenerating", () => {
    useReportStore.setState({ isGenerating: true });
    useReportStore.getState().handleError("Something failed");

    const state = useReportStore.getState();
    expect(state.isGenerating).toBe(false);
    expect(state.lastError).toBe("Something failed");
  });

  it("cancelGeneration calls IPC cancel", () => {
    useReportStore.setState({ isGenerating: true });
    useReportStore.getState().cancelGeneration();

    expect(window.api.report.cancel).toHaveBeenCalled();
    expect(useReportStore.getState().isGenerating).toBe(false);
  });

  it("reset clears all state", () => {
    useReportStore.setState({
      isGenerating: true,
      progress: { phase: "test", percent: 50, message: "" },
      lastResult: { paths: ["/tmp/x.pdf"] },
      lastError: "err",
    });

    useReportStore.getState().reset();
    const state = useReportStore.getState();
    expect(state.isGenerating).toBe(false);
    expect(state.progress).toBeNull();
    expect(state.lastResult).toBeNull();
    expect(state.lastError).toBeNull();
  });
});
