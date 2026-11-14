import type { CalendarResponse, MonthValue, StatsResponse } from '../api/queries';

/** Deterministic calendar: seasonal peak in September, VIIRS from 2022. */
export function calendarFixture(startYear = 2019, endYear = 2021, endMonth = 12): CalendarResponse {
  const months: MonthValue[] = [];
  for (let year = startYear; year <= endYear; year++) {
    for (let month = 1; month <= (year === endYear ? endMonth : 12); month++) {
      const value = Math.round(200 * Math.exp(-0.5 * ((month - 9) / 1.4) ** 2) + (year - 2019) * 5);
      const median = Math.round(200 * Math.exp(-0.5 * ((month - 9) / 1.4) ** 2));
      months.push({
        year,
        month,
        value,
        raw: year >= 2022 ? value * 3 : value,
        n_modis: value,
        n_viirs: value * 3,
        ci_low: value,
        ci_high: value,
        source: year >= 2022 ? 'VIIRS' : 'MODIS',
        provisional: year === endYear && month === endMonth,
        median,
        anomaly_pct: median ? ((value - median) / median) * 100 : null,
        percentile: 50,
      });
    }
  }
  return {
    aoi: { area_km2: 197_000, cells: 256 },
    start: `${startYear}-01`,
    end: `${endYear}-${String(endMonth).padStart(2, '0')}`,
    reference_years: [2003, 2022],
    transition_month: '2021-12',
    data_version: 'abc123',
    max_value: Math.max(...months.map((m) => m.value)),
    months,
  };
}

export function statsFixture(): StatsResponse {
  return {
    aoi: { area_km2: 197_000, cells: 256 },
    start: '2019-01',
    end: '2021-12',
    reference_years: [2003, 2022],
    data_version: 'abc123',
    climatology: Array.from({ length: 12 }, (_, i) => ({
      month: i + 1,
      median: [10, 8, 9, 12, 20, 40, 90, 150, 200, 120, 40, 15][i]!,
      p25: [5, 4, 5, 8, 12, 25, 60, 100, 150, 80, 25, 9][i]!,
      p75: [15, 12, 13, 18, 30, 60, 130, 210, 260, 170, 60, 22][i]!,
      current: [12, 9, 10, 11, 25, 48, 110, 180, 260, 140, 50, 18][i]!,
      critical: [8, 9, 10].includes(i + 1),
    })),
    critical_threshold: 100,
    critical_months: [8, 9, 10],
    annual: [
      { year: 2019, total: 1800, rank: 1, complete: true },
      { year: 2020, total: 900, rank: 3, complete: true },
      { year: 2021, total: 1200, rank: 2, complete: true },
    ],
    summary: {
      total: 3900,
      monthly_mean: 108.3,
      peak_month: 9,
      max_year: 2019,
      max_year_total: 1800,
      current: {
        month: '2021-12',
        value: 18,
        median: 15,
        anomaly_pct: 20,
        percentile: 70,
        provisional: true,
      },
    },
  };
}

export const AOI = {
  kind: 'draw' as const,
  areaKm2: 197_000,
  label: 'Area',
  geometry: {
    type: 'Polygon' as const,
    coordinates: [
      [
        [104, -2],
        [108, -2],
        [108, 2],
        [104, 2],
        [104, -2],
      ],
    ],
  },
};
