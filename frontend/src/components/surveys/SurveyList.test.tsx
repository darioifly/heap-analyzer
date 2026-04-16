import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { SurveyList } from "./SurveyList";
import { useProjectStore } from "@/stores/projectStore";
import { useSurveyStore } from "@/stores/surveyStore";

function setupMockApi(surveys: Record<string, unknown>[] = []) {
  window.api = {
    python: {
      execute: vi.fn(),
      cancel: vi.fn(),
      onProgress: vi.fn(),
      onWarning: vi.fn(),
      removeAllListeners: vi.fn(),
    },
    db: {
      listProjects: vi.fn().mockResolvedValue([]),
      createProject: vi.fn(),
      updateProject: vi.fn(),
      deleteProject: vi.fn(),
      listSurveys: vi.fn().mockResolvedValue(surveys),
      createSurvey: vi.fn(),
      updateSurvey: vi.fn(),
      deleteSurvey: vi.fn(),
      listHeaps: vi.fn().mockResolvedValue([]),
      createHeap: vi.fn(),
      updateHeap: vi.fn(),
      bulkCreateHeaps: vi.fn().mockResolvedValue([]),
    },
    dialog: {
      openFile: vi.fn().mockResolvedValue(null),
      saveFile: vi.fn().mockResolvedValue(null),
    },
  };
}

describe("SurveyList", () => {
  beforeEach(() => {
    setupMockApi();
    useProjectStore.setState({ selectedProjectId: null, projects: [] });
    useSurveyStore.setState({ surveys: [], selectedSurveyId: null, isLoading: false, error: null });
  });

  it("renders nothing when no project selected", () => {
    const { container } = render(<SurveyList onProcessSurvey={vi.fn()} />);
    expect(container.innerHTML).toBe("");
  });

  it("renders empty state when project selected but no surveys", () => {
    useProjectStore.setState({ selectedProjectId: 1 });
    render(<SurveyList onProcessSurvey={vi.fn()} />);
    expect(screen.getByText("Nessun rilievo. Importa il primo.")).toBeInTheDocument();
  });

  it("renders survey cards when surveys exist", () => {
    useProjectStore.setState({ selectedProjectId: 1 });
    useSurveyStore.setState({
      surveys: [
        {
          id: 1,
          projectId: 1,
          surveyDate: "2026-01-15",
          operator: "Mario Rossi",
          lasPath: "/test.las",
          tiffPath: "/test.tif",
          processingParams: null,
          processingStatus: "completed" as const,
          dsmPath: null,
          dtmPath: null,
          ndsmPath: null,
          labelMapPath: null,
          createdAt: "",
          updatedAt: "",
        },
      ],
    });
    render(<SurveyList onProcessSurvey={vi.fn()} />);
    expect(screen.getByText("Mario Rossi")).toBeInTheDocument();
    expect(screen.getByText("Completato")).toBeInTheDocument();
  });
});
