import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProjectList } from "./ProjectList";
import { useProjectStore } from "@/stores/projectStore";

const mockProject = {
  id: 1,
  name: "Test Acciaieria",
  location: "Brescia",
  crs: "EPSG:32632",
  notes: null,
  material_categories: "[]",
  created_at: "2026-01-01",
  updated_at: "2026-01-01",
};

function setupMockApi(projects: Record<string, unknown>[] = []) {
  window.api = {
    python: {
      execute: vi.fn(),
      cancel: vi.fn(),
      onProgress: vi.fn(),
      onWarning: vi.fn(),
      removeAllListeners: vi.fn(),
    },
    db: {
      listProjects: vi.fn().mockResolvedValue(projects),
      createProject: vi.fn().mockImplementation((data) =>
        Promise.resolve({ id: 2, ...data, created_at: "2026-01-02", updated_at: "2026-01-02" }),
      ),
      updateProject: vi.fn(),
      deleteProject: vi.fn().mockResolvedValue(undefined),
      listSurveys: vi.fn().mockResolvedValue([]),
      createSurvey: vi.fn(),
      updateSurvey: vi.fn(),
      deleteSurvey: vi.fn().mockResolvedValue(undefined),
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

describe("ProjectList", () => {
  beforeEach(() => {
    useProjectStore.setState({
      projects: [],
      selectedProjectId: null,
      isLoading: false,
      error: null,
    });
  });

  it("renders empty state when no projects", async () => {
    setupMockApi([]);
    render(<ProjectList />);
    expect(await screen.findByText("Nessun progetto")).toBeInTheDocument();
  });

  it("renders project list when projects loaded from API", async () => {
    setupMockApi([mockProject]);
    render(<ProjectList />);
    expect(await screen.findByText("Test Acciaieria")).toBeInTheDocument();
    expect(screen.getByText("Brescia")).toBeInTheDocument();
  });

  it("opens dialog when + button clicked", async () => {
    setupMockApi([]);
    const user = userEvent.setup();
    render(<ProjectList />);
    await waitFor(() => {
      expect(screen.getByLabelText("Nuovo progetto")).toBeInTheDocument();
    });
    await user.click(screen.getByLabelText("Nuovo progetto"));
    expect(await screen.findByText("Nuovo progetto", { selector: "[role='heading'], h2, [class*='DialogTitle']" })).toBeInTheDocument();
  });
});
