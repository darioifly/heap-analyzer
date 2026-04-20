// @vitest-environment happy-dom
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ImportDJIDialog } from "./ImportDJIDialog";
import { setupMockApi } from "@/test/mock-api";

const makeManifest = () => ({
  orthophoto_path: "/dji/map/result.tif",
  dsm_path: "/dji/map/dsm.tif",
  las_path: "/dji/models/pc/0/terra_las/cloud_merged.las",
  crs: "EPSG:32633",
  survey_date: "2026-03-30",
  bbox: [351000, 5120000, 352000, 5121000] as [number, number, number, number],
  has_ground_classification: true,
  pipeline_complete: true,
  warnings: [],
});

describe("ImportDJIDialog", () => {
  beforeEach(() => {
    setupMockApi();
    vi.mocked(window.api.dialog.openDirectory).mockResolvedValue("/dji");
  });

  it("shows folder-select state initially", () => {
    render(
      <ImportDJIDialog
        open
        onOpenChange={vi.fn()}
        projectId={1}
        onImported={vi.fn()}
      />,
    );
    expect(screen.getByText("Seleziona cartella")).toBeInTheDocument();
  });

  it("runs scan after folder pick and renders manifest on success", async () => {
    vi.mocked(window.api.dji.scanFolder).mockResolvedValue({
      ok: true,
      manifest: makeManifest(),
    });

    render(
      <ImportDJIDialog
        open
        onOpenChange={vi.fn()}
        projectId={1}
        onImported={vi.fn()}
      />,
    );

    await userEvent.click(screen.getByText("Seleziona cartella"));

    await waitFor(() => {
      expect(window.api.dji.scanFolder).toHaveBeenCalledWith({
        folderPath: "/dji",
      });
    });
    await waitFor(() => {
      // Manifest table rendered
      expect(screen.getByText("Ortofoto")).toBeInTheDocument();
      expect(screen.getByText("DSM")).toBeInTheDocument();
      expect(screen.getByText("Nuvola di punti")).toBeInTheDocument();
      expect(screen.getByText("EPSG:32633")).toBeInTheDocument();
    });
  });

  it("renders the warnings alert when the manifest carries warnings", async () => {
    vi.mocked(window.api.dji.scanFolder).mockResolvedValue({
      ok: true,
      manifest: {
        ...makeManifest(),
        warnings: ["Sentinel map/2dPipeline_done assente"],
      },
    });

    render(
      <ImportDJIDialog
        open
        onOpenChange={vi.fn()}
        projectId={1}
        onImported={vi.fn()}
      />,
    );

    await userEvent.click(screen.getByText("Seleziona cartella"));

    await waitFor(() => {
      expect(screen.getByText("Avvisi dalla scansione")).toBeInTheDocument();
      expect(
        screen.getByText(/2dPipeline_done assente/),
      ).toBeInTheDocument();
    });
  });

  it("renders an error state when scan fails", async () => {
    vi.mocked(window.api.dji.scanFolder).mockResolvedValue({
      ok: false,
      code: "DJI_INCOMPLETE",
      message: "DSM non trovato",
    });

    render(
      <ImportDJIDialog
        open
        onOpenChange={vi.fn()}
        projectId={1}
        onImported={vi.fn()}
      />,
    );

    await userEvent.click(screen.getByText("Seleziona cartella"));

    await waitFor(() => {
      expect(screen.getByText("Scansione fallita")).toBeInTheDocument();
      expect(screen.getByText("DSM non trovato")).toBeInTheDocument();
    });
    // No manifest table should be rendered in the failure case
    expect(screen.queryByText("Ortofoto")).not.toBeInTheDocument();
  });

  it("submits the import payload with default checkbox state", async () => {
    vi.mocked(window.api.dji.scanFolder).mockResolvedValue({
      ok: true,
      manifest: makeManifest(),
    });
    vi.mocked(window.api.dji.importSurvey).mockResolvedValue({ surveyId: 99 });

    const onImported = vi.fn();

    render(
      <ImportDJIDialog
        open
        onOpenChange={vi.fn()}
        projectId={42}
        onImported={onImported}
      />,
    );

    await userEvent.click(screen.getByText("Seleziona cartella"));

    await waitFor(() => {
      // Review step renders the CRS chip from the manifest
      expect(screen.getByText("EPSG:32633")).toBeInTheDocument();
    });

    // Fill operator
    const operator = screen.getByLabelText("Operatore");
    fireEvent.change(operator, { target: { value: "Alice" } });

    await userEvent.click(
      screen.getByRole("button", { name: "Importa rilievo" }),
    );

    await waitFor(() => {
      expect(window.api.dji.importSurvey).toHaveBeenCalledTimes(1);
    });

    const call = vi.mocked(window.api.dji.importSurvey).mock.calls[0][0];
    expect(call.projectId).toBe(42);
    expect(call.folderPath).toBe("/dji");
    expect(call.useDjiDsm).toBe(true); // default ON
    expect(call.copyFiles).toBe(false); // default OFF
    expect(call.operator).toBe("Alice");
    expect(call.surveyDate).toBe("2026-03-30"); // from manifest
    expect(onImported).toHaveBeenCalledWith(99);
  });
});
