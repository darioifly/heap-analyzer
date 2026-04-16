import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProjectList } from "./ProjectList";
import { useProjectStore } from "@/stores/projectStore";
import { setupMockApi } from "@/test/mock-api";

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
    setupMockApi();
    render(<ProjectList />);
    expect(await screen.findByText("Nessun progetto")).toBeInTheDocument();
  });

  it("renders project list when projects loaded from API", async () => {
    setupMockApi({ projects: [mockProject] });
    render(<ProjectList />);
    expect(await screen.findByText("Test Acciaieria")).toBeInTheDocument();
    expect(screen.getByText("Brescia")).toBeInTheDocument();
  });

  it("opens dialog when + button clicked", async () => {
    setupMockApi();
    const user = userEvent.setup();
    render(<ProjectList />);
    await waitFor(() => {
      expect(screen.getByLabelText("Nuovo progetto")).toBeInTheDocument();
    });
    await user.click(screen.getByLabelText("Nuovo progetto"));
    expect(await screen.findByText("Nuovo progetto", { selector: "[role='heading'], h2, [class*='DialogTitle']" })).toBeInTheDocument();
  });
});
