import type { Feature, MultiPolygon, Polygon } from 'geojson';
import { create } from 'zustand';

/** Shared view state for globe, map and calendar (FR-W-25: single time source). */
export type ViewMode = 'harmonized' | 'raw';
export type ColorScale = 'linear' | 'log';

export interface YearMonth {
  year: number;
  month: number; // 1-12
}

interface AppState {
  aoi: Feature<Polygon | MultiPolygon> | null;
  start: YearMonth;
  end: YearMonth;
  referenceYears: [number, number];
  selected: YearMonth;
  mode: ViewMode;
  scale: ColorScale;
  setAoi: (aoi: AppState['aoi']) => void;
  setRange: (start: YearMonth, end: YearMonth) => void;
  setReferenceYears: (years: [number, number]) => void;
  setSelected: (ym: YearMonth) => void;
  setMode: (mode: ViewMode) => void;
  setScale: (scale: ColorScale) => void;
}

const now = new Date();
const currentMonth: YearMonth = { year: now.getUTCFullYear(), month: now.getUTCMonth() + 1 };

export const useAppStore = create<AppState>()((set) => ({
  aoi: null,
  start: { year: 2001, month: 1 },
  end: currentMonth,
  referenceYears: [2003, 2022],
  selected: currentMonth,
  mode: 'harmonized',
  scale: 'linear',
  setAoi: (aoi) => set({ aoi }),
  setRange: (start, end) => set({ start, end }),
  setReferenceYears: (referenceYears) => set({ referenceYears }),
  setSelected: (selected) => set({ selected }),
  setMode: (mode) => set({ mode }),
  setScale: (scale) => set({ scale }),
}));
