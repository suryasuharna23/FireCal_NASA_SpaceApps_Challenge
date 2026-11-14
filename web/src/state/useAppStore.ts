import { create } from 'zustand';
import type { Aoi } from '../lib/aoi';
import type { PointsColor } from '../lib/points';

/** Shared view state for globe, map and calendar (FR-W-25: single time source). */
export type ViewMode = 'harmonized' | 'raw';
export type ColorScale = 'linear' | 'log';
export type CalendarView = 'count' | 'anomaly';

export interface YearMonth {
  year: number;
  month: number; // 1-12
}

interface AppState {
  aoi: Aoi | null;
  /** Inclusive range as YYYY-MM; null = API default (2001-01 .. latest). */
  start: string | null;
  end: string | null;
  referenceYears: [number, number] | null;
  selected: YearMonth | null;
  mode: ViewMode;
  scale: ColorScale;
  calendarView: CalendarView;
  pointsColor: PointsColor;
  setAoi: (aoi: Aoi | null) => void;
  setRange: (start: string | null, end: string | null) => void;
  setReferenceYears: (years: [number, number] | null) => void;
  setSelected: (ym: YearMonth | null) => void;
  setMode: (mode: ViewMode) => void;
  setScale: (scale: ColorScale) => void;
  setCalendarView: (view: CalendarView) => void;
  setPointsColor: (by: PointsColor) => void;
}

export const useAppStore = create<AppState>()((set) => ({
  aoi: null,
  start: null,
  end: null,
  referenceYears: null,
  selected: null,
  mode: 'harmonized',
  scale: 'linear',
  calendarView: 'count',
  pointsColor: 'sensor',
  setAoi: (aoi) => set({ aoi }),
  setRange: (start, end) => set({ start, end }),
  setReferenceYears: (referenceYears) => set({ referenceYears }),
  setSelected: (selected) => set({ selected }),
  setMode: (mode) => set({ mode }),
  setScale: (scale) => set({ scale }),
  setCalendarView: (calendarView) => set({ calendarView }),
  setPointsColor: (pointsColor) => set({ pointsColor }),
}));
