import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Layout } from "./Layout";

describe("Layout", () => {
  it("renders header with HEAP ANALYZER text", () => {
    render(
      <Layout>
        <div>content</div>
      </Layout>,
    );
    expect(screen.getByText("HEAP ANALYZER")).toBeInTheDocument();
  });

  it("renders main content area with children", () => {
    render(
      <Layout>
        <div data-testid="child">content</div>
      </Layout>,
    );
    expect(screen.getByTestId("child")).toBeInTheDocument();
  });

  it("renders status bar with engine status", () => {
    render(
      <Layout>
        <div>content</div>
      </Layout>,
    );
    expect(screen.getByText("Engine pronto")).toBeInTheDocument();
  });
});
