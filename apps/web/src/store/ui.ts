import { create } from "zustand";

type Theme = "dark" | "light";

type UiState = {
  theme: Theme;
  sidebarOpen: boolean;
  paletteOpen: boolean;
  setTheme: (theme: Theme) => void;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  setPaletteOpen: (open: boolean) => void;
};

const initialTheme = (localStorage.getItem("resolveai-theme-v2") as Theme | null) ?? "light";

export const useUiStore = create<UiState>((set) => ({
  theme: initialTheme,
  sidebarOpen: false,
  paletteOpen: false,
  setTheme: (theme) => {
    localStorage.setItem("resolveai-theme-v2", theme);
    set({ theme });
  },
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
  setPaletteOpen: (paletteOpen) => set({ paletteOpen }),
}));
