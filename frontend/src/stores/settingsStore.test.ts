import { describe, it, expect, beforeEach, vi } from "vitest";
import { useSettingsStore, defaultSettings } from "./settingsStore";

describe("settingsStore", () => {
  beforeEach(() => {
    useSettingsStore.setState({
      settings: defaultSettings,
      loaded: false,
      saving: false,
    });
  });

  it("loads settings from disk and marks as loaded", async () => {
    (globalThis as unknown as { window: { api: unknown } }).window = {
      api: {
        settings: {
          load: vi.fn().mockResolvedValue({
            ...defaultSettings,
            report: { ...defaultSettings.report, companyName: "Acme" },
          }),
          save: vi.fn(),
          reset: vi.fn(),
          getProcessingSchema: vi.fn(),
        },
      },
    };

    await useSettingsStore.getState().loadFromDisk();
    const state = useSettingsStore.getState();
    expect(state.loaded).toBe(true);
    expect(state.settings.report.companyName).toBe("Acme");
  });

  it("falls back to defaults when load throws", async () => {
    (globalThis as unknown as { window: { api: unknown } }).window = {
      api: {
        settings: {
          load: vi.fn().mockRejectedValue(new Error("disk error")),
          save: vi.fn(),
          reset: vi.fn(),
          getProcessingSchema: vi.fn(),
        },
      },
    };

    await useSettingsStore.getState().loadFromDisk();
    const state = useSettingsStore.getState();
    expect(state.loaded).toBe(true);
    expect(state.settings).toEqual(defaultSettings);
  });

  it("applies partial patch optimistically and persists", async () => {
    const saveMock = vi.fn().mockImplementation(async (patch) => ({
      ...defaultSettings,
      ...patch,
    }));

    (globalThis as unknown as { window: { api: unknown } }).window = {
      api: {
        settings: {
          load: vi.fn(),
          save: saveMock,
          reset: vi.fn(),
          getProcessingSchema: vi.fn(),
        },
      },
    };

    await useSettingsStore.getState().save({
      report: { ...defaultSettings.report, companyName: "Patched" },
    });

    const state = useSettingsStore.getState();
    expect(state.settings.report.companyName).toBe("Patched");
    expect(saveMock).toHaveBeenCalledOnce();
  });

  it("rolls back on save failure", async () => {
    const saveMock = vi.fn().mockRejectedValue(new Error("write failed"));

    (globalThis as unknown as { window: { api: unknown } }).window = {
      api: {
        settings: {
          load: vi.fn(),
          save: saveMock,
          reset: vi.fn(),
          getProcessingSchema: vi.fn(),
        },
      },
    };

    // Seed a non-default starting state so rollback is observable.
    useSettingsStore.setState({
      settings: {
        ...defaultSettings,
        report: { ...defaultSettings.report, companyName: "Original" },
      },
    });

    await expect(
      useSettingsStore.getState().save({
        report: { ...defaultSettings.report, companyName: "WillFail" },
      }),
    ).rejects.toThrow("write failed");

    const state = useSettingsStore.getState();
    expect(state.settings.report.companyName).toBe("Original");
  });
});
