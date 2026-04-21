import { create } from "zustand";

export type ViewMode = "2d" | "3d";
export type ColorMode = "rgb" | "elevation" | "heap";
export type CameraPreset = "orbit" | "top" | "side";

interface UiStore {
  theme: "light" | "dark";
  sidebarLeftCollapsed: boolean;
  sidebarRightCollapsed: boolean;
  viewMode: ViewMode;

  // 3D-specific
  colorMode: ColorMode;
  showBasePlane: boolean;
  showHeapOverlay3D: boolean;
  showNdsmHeatmap3D: boolean;
  pointBudget: number;
  cameraPreset: CameraPreset | null;
  centerOnSelectionRequested: number;

  toggleTheme: () => void;
  toggleSidebarLeft: () => void;
  toggleSidebarRight: () => void;
  setViewMode: (mode: ViewMode) => void;

  // 3D actions
  setColorMode: (m: ColorMode) => void;
  toggleBasePlane: () => void;
  toggleHeapOverlay3D: () => void;
  toggleNdsmHeatmap3D: () => void;
  setPointBudget: (n: number) => void;
  applyCameraPreset: (p: CameraPreset) => void;
  clearCameraPreset: () => void;
  requestCenterOnSelection: () => void;
}

export const useUiStore = create<UiStore>((set) => ({
  theme: "dark",
  sidebarLeftCollapsed: false,
  sidebarRightCollapsed: false,
  viewMode: "2d",

  colorMode: "rgb",
  showBasePlane: true,
  showHeapOverlay3D: true,
  showNdsmHeatmap3D: false,
  pointBudget: 2_000_000,
  cameraPreset: null,
  centerOnSelectionRequested: 0,

  toggleTheme: () =>
    set((state) => {
      const next = state.theme === "dark" ? "light" : "dark";
      if (next === "dark") {
        document.documentElement.classList.add("dark");
      } else {
        document.documentElement.classList.remove("dark");
      }
      return { theme: next };
    }),

  toggleSidebarLeft: () =>
    set((state) => ({ sidebarLeftCollapsed: !state.sidebarLeftCollapsed })),

  toggleSidebarRight: () =>
    set((state) => ({ sidebarRightCollapsed: !state.sidebarRightCollapsed })),

  setViewMode: (mode) => set({ viewMode: mode }),

  setColorMode: (m) => set({ colorMode: m }),
  toggleBasePlane: () => set((s) => ({ showBasePlane: !s.showBasePlane })),
  toggleHeapOverlay3D: () => set((s) => ({ showHeapOverlay3D: !s.showHeapOverlay3D })),
  toggleNdsmHeatmap3D: () =>
    set((s) => ({ showNdsmHeatmap3D: !s.showNdsmHeatmap3D })),
  setPointBudget: (n) => set({ pointBudget: n }),
  applyCameraPreset: (p) => set({ cameraPreset: p }),
  clearCameraPreset: () => set({ cameraPreset: null }),
  requestCenterOnSelection: () =>
    set((s) => ({ centerOnSelectionRequested: s.centerOnSelectionRequested + 1 })),
}));
