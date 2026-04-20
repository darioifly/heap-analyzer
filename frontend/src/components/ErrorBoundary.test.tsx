// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach } from "vitest";
import "@testing-library/jest-dom/vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ErrorBoundary } from "./ErrorBoundary";

function Thrower({ shouldThrow }: { shouldThrow: boolean }): JSX.Element {
  if (shouldThrow) throw new Error("Guasto sintetico");
  return <div>child ok</div>;
}

beforeEach(() => {
  // Silence React's noisy error log during the throw
  vi.spyOn(console, "error").mockImplementation(() => {});
  (window as unknown as { api: unknown }).api = {
    logging: { rendererError: vi.fn() },
  };
});

describe("ErrorBoundary", () => {
  it("renders children when no error", () => {
    render(
      <ErrorBoundary>
        <Thrower shouldThrow={false} />
      </ErrorBoundary>,
    );
    expect(screen.getByText("child ok")).toBeInTheDocument();
  });

  it("renders fallback UI when a child throws", () => {
    render(
      <ErrorBoundary>
        <Thrower shouldThrow={true} />
      </ErrorBoundary>,
    );
    expect(screen.getByText("Qualcosa è andato storto")).toBeInTheDocument();
    expect(screen.getByText(/Guasto sintetico/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Ricarica applicazione/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Copia dettagli/i }),
    ).toBeInTheDocument();
  });

  it("reassures the user their data is safe", () => {
    render(
      <ErrorBoundary>
        <Thrower shouldThrow={true} />
      </ErrorBoundary>,
    );
    expect(
      screen.getByText(/I tuoi dati non sono stati persi/i),
    ).toBeInTheDocument();
  });

  it("invokes logging IPC with error details", () => {
    const rendererError = vi.fn();
    (window as unknown as { api: { logging: { rendererError: typeof rendererError } } }).api = {
      logging: { rendererError },
    };

    render(
      <ErrorBoundary>
        <Thrower shouldThrow={true} />
      </ErrorBoundary>,
    );
    expect(rendererError).toHaveBeenCalledTimes(1);
    const call = rendererError.mock.calls[0][0];
    expect(call.message).toBe("Guasto sintetico");
    expect(call.context).toBe("ErrorBoundary");
  });

  it("reload button calls window.location.reload", () => {
    const reload = vi.fn();
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...window.location, reload },
    });

    render(
      <ErrorBoundary>
        <Thrower shouldThrow={true} />
      </ErrorBoundary>,
    );
    fireEvent.click(screen.getByRole("button", { name: /Ricarica/i }));
    expect(reload).toHaveBeenCalledOnce();
  });
});
