import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ProcessingProgress } from "./ProcessingProgress";
import { useProcessingStore } from "@/stores/processingStore";

describe("ProcessingProgress", () => {
  beforeEach(() => {
    useProcessingStore.getState().reset();
  });

  it("shows percent and phase label", () => {
    useProcessingStore.setState({
      isRunning: true,
      progress: {
        phase: "generating_dsm",
        percent: 45,
        message: "Generazione DSM in corso...",
      },
      startTime: Date.now() - 30000,
    });

    render(<ProcessingProgress onCancel={vi.fn()} />);
    expect(screen.getByText("Generazione DSM")).toBeInTheDocument();
    expect(screen.getByText("45%")).toBeInTheDocument();
  });

  it("shows cancel button", () => {
    useProcessingStore.setState({
      isRunning: true,
      progress: { phase: "computing_metrics", percent: 80, message: "" },
      startTime: Date.now() - 60000,
    });

    render(<ProcessingProgress onCancel={vi.fn()} />);
    expect(screen.getByText("Annulla elaborazione")).toBeInTheDocument();
  });
});
