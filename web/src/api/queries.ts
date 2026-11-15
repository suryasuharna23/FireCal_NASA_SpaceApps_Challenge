import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useAppStore } from '../state/useAppStore';
import type { PlaybackFrame } from '../lib/playback';
import { apiGet, apiPost } from './client';

export interface MonthValue {
  year: number;
  month: number;
  value: number;
  raw: number;
  n_modis: number;
  n_viirs: number;
  ci_low: number;
  ci_high: number;
  source: 'MODIS' | 'VIIRS';
  provisional: boolean;
  median: number | null;
  anomaly_pct: number | null;
  percentile: number | null;
}

export interface CalendarResponse {
  aoi: { area_km2: number; cells: number };
  start: string;
  end: string;
  reference_years: [number, number];
  transition_month: string;
  data_version: string;
  max_value: number;
  months: MonthValue[];
}

export interface ClimatologyMonth {
  month: number;
  median: number | null;
  p25: number | null;
  p75: number | null;
  current: number | null;
  critical: boolean;
}

export interface StatsResponse {
  aoi: { area_km2: number; cells: number };
  start: string;
  end: string;
  reference_years: [number, number];
  data_version: string;
  climatology: ClimatologyMonth[];
  critical_threshold: number | null;
  critical_months: number[];
  annual: { year: number; total: number; rank: number; complete: boolean }[];
  summary: {
    total: number | null;
    monthly_mean: number | null;
    peak_month: number | null;
    max_year: number | null;
    max_year_total: number | null;
    current: {
      month: string;
      value: number | null;
      median: number | null;
      anomaly_pct: number | null;
      percentile: number | null;
      provisional: boolean;
    } | null;
  };
}

/** Request body shared by /calendar, /stats and /export (null = API default). */
export function useSeriesRequest() {
  const aoi = useAppStore((s) => s.aoi);
  const start = useAppStore((s) => s.start);
  const end = useAppStore((s) => s.end);
  const referenceYears = useAppStore((s) => s.referenceYears);
  if (!aoi) return null;
  return {
    aoi: aoi.geometry,
    ...(start ? { start } : {}),
    ...(end ? { end } : {}),
    ...(referenceYears ? { reference_years: referenceYears } : {}),
  };
}

function useSeries<T>(path: '/calendar' | '/stats') {
  const body = useSeriesRequest();
  return useQuery({
    queryKey: [path, body],
    queryFn: ({ signal }) => apiPost<T>(path, body, signal),
    enabled: body !== null,
    placeholderData: keepPreviousData,
    staleTime: 10 * 60 * 1000,
  });
}

export const useCalendar = () => useSeries<CalendarResponse>('/calendar');
export const useStats = () => useSeries<StatsResponse>('/stats');

export interface PointsResponse {
  type: 'FeatureCollection';
  year: number;
  month: number;
  period?: string;
  day?: number | null;
  hour?: number | null;
  count: number;
  aggregated: boolean;
  cell_size_deg?: number;
  features: {
    type: 'Feature';
    geometry: { type: 'Point'; coordinates: [number, number] };
    properties: Record<string, string | number | null>;
  }[];
}

/** Raw detections of one month inside the AOI, or grid cells above 50,000 (FR-W-15). */
export function usePoints(ym: PlaybackFrame | null) {
  const scope = useAppStore((s) => s.scope);
  const aoi = useAppStore((s) => s.aoi);
  const body =
    aoi && ym && ym.period !== 'year'
      ? { aoi: aoi.geometry, ...ym, ...(scope === 'global' ? { scope } : {}) }
      : null;
  return useQuery({
    queryKey: ['/points', body],
    queryFn: ({ signal }) => apiPost<PointsResponse>('/points', body, signal),
    enabled: body !== null,
    staleTime: 10 * 60 * 1000,
  });
}

export interface GlobeResponse {
  year: number;
  month: number;
  period?: string;
  mode: 'harmonized' | 'raw';
  res: number;
  source: 'MODIS' | 'VIIRS' | 'MODIS+VIIRS';
  provisional: boolean;
  count: number;
  total: number;
  max: number;
  truncated: boolean;
  /** [lon, lat, value] triples on a 0.5° grid, strongest first. */
  cells: [number, number, number][];
  data_version: string | null;
}

/** World hotspot cells for one month (FR-W-23). */
export function useGlobe(ym: PlaybackFrame | null, mode: 'harmonized' | 'raw') {
  const scope = useAppStore((s) => s.scope);
  return useQuery({
    queryKey: ['/globe', ym, mode, scope],
    queryFn: () => apiGet<GlobeResponse>('/globe', { ...ym!, mode, scope }),
    enabled: ym !== null,
    staleTime: 30 * 60 * 1000,
  });
}
