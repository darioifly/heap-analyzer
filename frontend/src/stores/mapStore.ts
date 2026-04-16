import { create } from "zustand";

interface MapStore {
  ortophotoVisible: boolean;
  ortophotoOpacity: number;
  heapsVisible: boolean;
  heapsOpacity: number;
  ndsmVisible: boolean;
  ndsmOpacity: number;
  labelsVisible: boolean;

  setOrtophotoVisible: (v: boolean) => void;
  setOrtophotoOpacity: (o: number) => void;
  setHeapsVisible: (v: boolean) => void;
  setHeapsOpacity: (o: number) => void;
  setNdsmVisible: (v: boolean) => void;
  setNdsmOpacity: (o: number) => void;
  setLabelsVisible: (v: boolean) => void;
}

export const useMapStore = create<MapStore>((set) => ({
  ortophotoVisible: true,
  ortophotoOpacity: 1,
  heapsVisible: true,
  heapsOpacity: 1,
  ndsmVisible: true,
  ndsmOpacity: 0.5,
  labelsVisible: true,

  setOrtophotoVisible: (v) => set({ ortophotoVisible: v }),
  setOrtophotoOpacity: (o) => set({ ortophotoOpacity: o }),
  setHeapsVisible: (v) => set({ heapsVisible: v }),
  setHeapsOpacity: (o) => set({ heapsOpacity: o }),
  setNdsmVisible: (v) => set({ ndsmVisible: v }),
  setNdsmOpacity: (o) => set({ ndsmOpacity: o }),
  setLabelsVisible: (v) => set({ labelsVisible: v }),
}));
