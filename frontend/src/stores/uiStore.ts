import { create } from "zustand";

interface UiStore {
  theme: "light" | "dark";
  sidebarLeftCollapsed: boolean;
  sidebarRightCollapsed: boolean;
  viewMode: "2d" | "3d";

  toggleTheme: () => void;
  toggleSidebarLeft: () => void;
  toggleSidebarRight: () => void;
  setViewMode: (mode: "2d" | "3d") => void;
}

export const useUiStore = create<UiStore>((set) => ({
  theme: "dark",
  sidebarLeftCollapsed: false,
  sidebarRightCollapsed: false,
  viewMode: "2d",

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
}));
