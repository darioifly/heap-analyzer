import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MainLayout } from "./MainLayout";

describe("MainLayout", () => {
  it("renders left panel with Progetti header", () => {
    render(<MainLayout />);
    expect(screen.getByText("Progetti")).toBeInTheDocument();
  });

  it("renders right panel with Proprietà header", () => {
    render(<MainLayout />);
    expect(screen.getByText("Proprietà")).toBeInTheDocument();
  });

  it("renders center panel with empty state message", () => {
    render(<MainLayout />);
    expect(
      screen.getByText("Importa un rilievo per visualizzare la mappa"),
    ).toBeInTheDocument();
  });

  it("renders 2 resize handles", () => {
    const { container } = render(<MainLayout />);
    const handles = container.querySelectorAll("[data-separator]");
    expect(handles).toHaveLength(2);
  });
});
