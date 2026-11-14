import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import type { ReactElement } from 'react';

/** Render with a fresh QueryClient (no retries) for component tests. */
export function renderWithQuery(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

/** Stub global fetch with a router of path -> JSON body (or Response). */
export function mockFetch(routes: Record<string, unknown>) {
  const fn = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(typeof input === 'string' ? input : input.toString());
    const body = routes[url.pathname];
    if (body === undefined) return new Response('{"detail":"not found"}', { status: 404 });
    if (body instanceof Response) return body;
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  });
  vi.stubGlobal('fetch', fn);
  return fn;
}

export const META_OK = {
  api_version: '0.1.0',
  status: 'ok',
  attribution: 'NASA FIRMS',
  max_aoi_km2: 1_000_000,
  default_reference_years: [2003, 2022],
  data_version: 'abc123',
  last_updated: '2026-11-13T02:10:00+00:00',
  last_acq_date: '2026-11-12',
  start_month: '2000-11',
  end_month: '2026-11',
  transition_month: '2021-12',
  grid_res_deg: 0.25,
  nrt: {
    provisional: true,
    since: '2026-10-01',
    provisional_months: ['2026-10', '2026-11'],
    last_run: '2026-11-13T02:00:00+00:00',
    ok: true,
    errors: {},
  },
};
