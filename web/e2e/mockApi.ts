import type { Page } from '@playwright/test';

/** Deterministic API responses so end-to-end tests run without the backend (CI). */
function calendar() {
  const months = [];
  for (let year = 2001; year <= 2026; year++) {
    for (let month = 1; month <= (year === 2026 ? 11 : 12); month++) {
      const median = Math.round(200 * Math.exp(-0.5 * ((month - 9) / 1.4) ** 2));
      const value = Math.round(median * (year === 2016 ? 3 : 1 + ((year * month) % 7) / 20));
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
        provisional: year === 2026 && month === 11,
        median,
        anomaly_pct: median ? ((value - median) / median) * 100 : null,
        percentile: 50,
      });
    }
  }
  return {
    aoi: { area_km2: 282_332, cells: 452 },
    start: '2001-01',
    end: '2026-11',
    reference_years: [2003, 2022],
    transition_month: '2021-12',
    data_version: 'e2e',
    max_value: Math.max(...months.map((m) => m.value)),
    months,
  };
}

const stats = {
  aoi: { area_km2: 282_332, cells: 452 },
  start: '2001-01',
  end: '2026-11',
  reference_years: [2003, 2022],
  data_version: 'e2e',
  climatology: Array.from({ length: 12 }, (_, i) => ({
    month: i + 1,
    median: [10, 8, 9, 12, 20, 40, 90, 150, 200, 120, 40, 15][i],
    p25: [5, 4, 5, 8, 12, 25, 60, 100, 150, 80, 25, 9][i],
    p75: [15, 12, 13, 18, 30, 60, 130, 210, 260, 170, 60, 22][i],
    current: i < 11 ? [12, 9, 10, 11, 25, 48, 110, 180, 260, 140, 50, 18][i] : null,
    critical: [8, 9, 10].includes(i + 1),
  })),
  critical_threshold: 100,
  critical_months: [8, 9, 10],
  annual: Array.from({ length: 26 }, (_, i) => ({
    year: 2001 + i,
    total: 2001 + i === 2016 ? 3000 : 800 + ((i * 37) % 400),
    rank: 2001 + i === 2016 ? 1 : 2 + i,
    complete: i < 25,
  })),
  summary: {
    total: 30000,
    monthly_mean: 96,
    peak_month: 9,
    max_year: 2016,
    max_year_total: 3000,
    current: {
      month: '2026-11',
      value: 50,
      median: 40,
      anomaly_pct: 25,
      percentile: 80,
      provisional: true,
    },
  },
};

const meta = {
  api_version: '0.1.0',
  status: 'ok',
  attribution: 'NASA FIRMS',
  max_aoi_km2: 1_000_000,
  default_reference_years: [2003, 2022],
  data_version: 'e2e',
  last_updated: '2026-11-14T02:10:00+00:00',
  last_acq_date: '2026-11-13',
  start_month: '2000-11',
  end_month: '2026-11',
  transition_month: '2021-12',
  calibration_period: '2013-01:2021-12',
  grid_res_deg: 0.25,
  nrt: {
    provisional: true,
    since: '2026-10-01',
    provisional_months: ['2026-11'],
    last_run: null,
    ok: true,
    errors: {},
  },
  validation: {
    test_years: [2016, 2019],
    r: 0.98,
    bias: 0.02,
    mae: 12,
    meets_target: true,
    limitations: [],
  },
};

const globe = {
  year: 2026,
  month: 11,
  mode: 'harmonized',
  res: 0.5,
  source: 'VIIRS',
  provisional: true,
  count: 3,
  total: 60,
  max: 30,
  truncated: false,
  cells: [
    [104.25, -3.25, 30],
    [113.75, -2.25, 20],
    [-60.25, -9.75, 10],
  ],
  data_version: 'e2e',
};

const points = {
  type: 'FeatureCollection',
  year: 2026,
  month: 11,
  count: 1,
  aggregated: false,
  features: [
    {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [104.3, -3.3] },
      properties: { sensor: 'VIIRS', satellite: 'S-NPP', frp: 4.2, time: '2026-11-03T18:10Z' },
    },
  ],
};

export async function mockApi(page: Page) {
  const json = (body: unknown) => ({
    status: 200,
    contentType: 'application/json',
    headers: { 'Access-Control-Allow-Origin': '*' },
    body: JSON.stringify(body),
  });
  await page.route('http://localhost:8000/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (route.request().method() === 'OPTIONS') {
      return route.fulfill({
        status: 204,
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Headers': '*',
          'Access-Control-Allow-Methods': 'GET, POST',
        },
      });
    }
    if (path === '/meta') return route.fulfill(json(meta));
    if (path === '/globe') return route.fulfill(json(globe));
    if (path === '/calendar') return route.fulfill(json(calendar()));
    if (path === '/stats') return route.fulfill(json(stats));
    if (path === '/points') return route.fulfill(json(points));
    if (path === '/regions') return route.fulfill(json({ query: '', results: [] }));
    if (path === '/export') {
      return route.fulfill({
        status: 200,
        contentType: 'text/csv',
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Expose-Headers': 'Content-Disposition',
          'Content-Disposition': 'attachment; filename="firecal_monthly_2001-01_2026-11.csv"',
        },
        body: '# Data: NASA FIRMS\nyear,month,n_harmonized\n2026,11,50\n',
      });
    }
    return route.fulfill({ status: 404, body: '{"detail":"not mocked"}' });
  });
  // Keep tests offline and deterministic: a minimal local basemap style instead of
  // OpenFreeMap (so the globe still loads and its tools enable), and no web fonts.
  await page.route(/tiles\.openfreemap\.org/, (route) =>
    route.request().url().includes('/styles/')
      ? route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            version: 8,
            sources: {},
            layers: [
              { id: 'background', type: 'background', paint: { 'background-color': '#141a2b' } },
            ],
          }),
        })
      : route.abort(),
  );
  await page.route(/fonts\.(googleapis|gstatic)\.com/, (route) => route.abort());
}
