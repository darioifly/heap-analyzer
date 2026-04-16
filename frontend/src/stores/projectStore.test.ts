import { describe, it, expect, beforeEach, vi } from "vitest";
import { useProjectStore } from "./projectStore";
import { setupMockApi } from "@/test/mock-api";

const mockProjects = [
  {
    id: 1,
    name: "Test Project",
    location: "Brescia",
    crs: "EPSG:32632",
    notes: null,
    material_categories: '["Rottame ferroso","Ghisa"]',
    created_at: "2026-01-01T00:00:00",
    updated_at: "2026-01-01T00:00:00",
  },
];

describe("projectStore", () => {
  beforeEach(() => {
    setupMockApi({ projects: mockProjects });
    useProjectStore.setState({
      projects: [],
      selectedProjectId: null,
      isLoading: false,
      error: null,
    });
  });

  it("loadAll populates projects", async () => {
    await useProjectStore.getState().loadAll();
    const state = useProjectStore.getState();
    expect(state.projects).toHaveLength(1);
    expect(state.projects[0].name).toBe("Test Project");
    expect(state.projects[0].materialCategories).toEqual(["Rottame ferroso", "Ghisa"]);
    expect(state.isLoading).toBe(false);
  });

  it("create adds project to state", async () => {
    const project = await useProjectStore.getState().create({
      name: "New Project",
      location: null,
      crs: "EPSG:32632",
      notes: null,
      materialCategories: [],
    });
    expect(project.id).toBeTypeOf("number");
    expect(useProjectStore.getState().projects).toHaveLength(1);
  });

  it("update modifies project in state", async () => {
    useProjectStore.setState({
      projects: [
        {
          id: 1, name: "Old", location: null, crs: "EPSG:32632",
          notes: null, materialCategories: [], createdAt: "", updatedAt: "",
        },
      ],
    });
    await useProjectStore.getState().update(1, { name: "Updated" });
    expect(useProjectStore.getState().projects[0].name).toBe("Updated");
  });

  it("delete removes project from state", async () => {
    useProjectStore.setState({
      projects: [
        {
          id: 1, name: "ToDelete", location: null, crs: "EPSG:32632",
          notes: null, materialCategories: [], createdAt: "", updatedAt: "",
        },
      ],
      selectedProjectId: 1,
    });
    await useProjectStore.getState().delete(1);
    expect(useProjectStore.getState().projects).toHaveLength(0);
    expect(useProjectStore.getState().selectedProjectId).toBeNull();
  });

  it("handles API errors", async () => {
    window.api.db.listProjects = vi.fn().mockRejectedValue(new Error("DB error"));
    await useProjectStore.getState().loadAll();
    expect(useProjectStore.getState().error).toBe("Error: DB error");
    expect(useProjectStore.getState().isLoading).toBe(false);
  });

  it("select updates selectedProjectId", () => {
    useProjectStore.getState().select(42);
    expect(useProjectStore.getState().selectedProjectId).toBe(42);
  });
});
