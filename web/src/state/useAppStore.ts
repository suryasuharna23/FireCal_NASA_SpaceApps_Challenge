import { create } from 'zustand';
import type { Aoi } from '../lib/aoi';
import type { PointsColor } from '../lib/points';

/** Shared view state for globe, map and calendar (FR-W-25: single time source). */
export type ViewMode = 'harmonized' | 'raw';
export type ColorScale = 'linear' | 'log';
export type CalendarView = 'count' | 'anomaly';
export type MapDisplay = 'points' | 'heatmap';
export type PlaybackPeriod = 'year' | 'month' | 'day' | 'hour';
export type DataScope = 'indonesia' | 'global';

export interface YearMonth {
  year: number;
  month: number; // 1-12
}

interface AppState {
  scope: DataScope;
  setScope: (scope: DataScope) => void;
  aoi: Aoi | null;
  /** Inclusive range as YYYY-MM; null = full available API range. */
  start: string | null;
  end: string | null;
  referenceYears: [number, number] | null;
  selected: YearMonth | null;
  playbackPeriod: PlaybackPeriod;
  playbackDay: number;
  playbackHour: number;
  mode: ViewMode;
  scale: ColorScale;
  calendarView: CalendarView;
  pointsColor: PointsColor;
  mapDisplay: MapDisplay;
  setAoi: (aoi: Aoi | null) => void;
  setRange: (start: string | null, end: string | null) => void;
  setReferenceYears: (years: [number, number] | null) => void;
  setSelected: (ym: YearMonth | null) => void;
  setPlaybackPeriod: (period: PlaybackPeriod) => void;
  setPlaybackDay: (day: number) => void;
  setPlaybackHour: (hour: number) => void;
  setMode: (mode: ViewMode) => void;
  setScale: (scale: ColorScale) => void;
  setCalendarView: (view: CalendarView) => void;
  setPointsColor: (by: PointsColor) => void;
  setMapDisplay: (display: MapDisplay) => void;
}

export const useAppStore = create<AppState>()((set) => ({
  scope: 'indonesia',
  setScope: (scope) =>
    set((state) => ({
      scope,
      aoi: state.scope === scope ? state.aoi : null,
      selected: null,
      playbackDay: 1,
      playbackHour: 0,
      mode: scope === 'global' ? 'raw' : 'harmonized',
    })),
  aoi: null,
  start: null,
  end: null,
  referenceYears: null,
  selected: null,
  playbackPeriod: 'month',
  playbackDay: 1,
  playbackHour: 0,
  mode: 'harmonized',
  scale: 'linear',
  calendarView: 'count',
  pointsColor: 'sensor',
  mapDisplay: 'points',
  setAoi: (aoi) =>
    set((state) =>
      state.scope === 'global' && /^NE[01]-IDN(?:-|$)/.test(aoi?.regionId ?? '')
        ? {
            scope: 'indonesia',
            aoi,
            selected: null,
            playbackDay: 1,
            playbackHour: 0,
            mode: 'harmonized',
          }
        : { aoi },
    ),
  setRange: (start, end) => set({ start, end }),
  setReferenceYears: (referenceYears) => set({ referenceYears }),
  setSelected: (selected) => set({ selected }),
  setPlaybackPeriod: (playbackPeriod) => set({ playbackPeriod }),
  setPlaybackDay: (playbackDay) => set({ playbackDay }),
  setPlaybackHour: (playbackHour) => set({ playbackHour }),
  setMode: (mode) => set({ mode }),
  setScale: (scale) => set({ scale }),
  setCalendarView: (calendarView) => set({ calendarView }),
  setPointsColor: (pointsColor) => set({ pointsColor }),
  setMapDisplay: (mapDisplay) => set({ mapDisplay }),
}));
