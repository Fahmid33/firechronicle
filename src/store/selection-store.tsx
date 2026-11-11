"use client";

import { createContext, useContext, useState, type ReactNode } from "react";
import { createStore, useStore } from "zustand";
import { FIRST_YEAR, LAST_YEAR, type DataLayer } from "@/types/explorer";
import type { BlockSelectionMetadata } from "@/types/map-data";

type Selection = {
  region_id: "BR-PA";
  block_id: string | null;
  year: number;
  month: number;
  activeLayer: DataLayer;
  blockMetadata: BlockSelectionMetadata | null;
  setPeriod: (year: number, month: number) => void;
  setLayer: (layer: DataLayer) => void;
  // Call only with IDs from approved within-Pará backend geometry.
  setBlock: (blockId: string | null, metadata?: BlockSelectionMetadata) => void;
};

export function createSelectionStore() {
  return createStore<Selection>()((set) => ({
    region_id: "BR-PA",
    block_id: null,
    year: 2020,
    month: 9,
    activeLayer: "observed",
    blockMetadata: null,
    setPeriod: (year, month) => {
      if (!Number.isInteger(year) || year < FIRST_YEAR || year > LAST_YEAR || !Number.isInteger(month) || month < 1 || month > 12) return;
      set((state) => ({ year, month, blockMetadata: null, activeLayer: year < 2012 ? "estimated" : state.activeLayer === "estimated" ? "observed" : state.activeLayer }));
    },
    setLayer: (activeLayer) => set({ activeLayer, blockMetadata: null }),
    setBlock: (block_id, metadata) => set({ block_id, blockMetadata: block_id ? metadata ?? null : null }),
  }));
}

type SelectionStore = ReturnType<typeof createSelectionStore>;
const SelectionContext = createContext<SelectionStore | null>(null);

export function SelectionProvider({ children }: { children: ReactNode }) {
  const [store] = useState(createSelectionStore);
  return <SelectionContext.Provider value={store}>{children}</SelectionContext.Provider>;
}

export function useSelection<T>(selector: (state: Selection) => T): T {
  const store = useContext(SelectionContext);
  if (!store) throw new Error("SelectionProvider is required");
  return useStore(store, selector);
}
