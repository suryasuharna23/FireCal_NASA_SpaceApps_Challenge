import { useQuery } from '@tanstack/react-query';

export const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(
  /\/$/,
  '',
);

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function parse<T>(response: Response, path: string): Promise<T> {
  if (!response.ok) {
    let detail = `${path} failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body?.detail === 'string') detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

export async function apiGet<T>(path: string, params?: Record<string, string | number>) {
  const url = new URL(`${BASE_URL}${path}`);
  for (const [k, v] of Object.entries(params ?? {})) url.searchParams.set(k, String(v));
  return parse<T>(await fetch(url), path);
}

export async function apiPost<T>(path: string, body: unknown, signal?: AbortSignal) {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });
  return parse<T>(response, path);
}

export interface Meta {
  global?: {
    status: 'ok' | 'unavailable';
    detail?: string;
    data_version?: string;
    start_date?: string;
    requested_through?: string;
    start_month?: string;
    end_month?: string;
    last_acq_date?: string;
    rows?: number;
    provisional?: boolean;
    lagging_sources?: { source: string; available_through: string }[];
    live?: Meta['live'];
  };
  api_version: string;
  status: 'ok' | 'no_data';
  detail?: string;
  attribution: string;
  max_aoi_km2: number;
  default_reference_years: [number, number];
  data_version: string | null;
  live?: {
    status: 'waiting' | 'updating' | 'updated' | 'up_to_date' | 'failed' | 'missing_key';
    checked_at?: string;
    requested_through?: string;
    lagging_sources?: { source: string; available_through: string }[];
    detail?: string;
  } | null;
  last_updated?: string;
  last_acq_date?: string | null;
  start_month?: string;
  end_month?: string;
  transition_month?: string;
  calibration_period?: string;
  grid_res_deg?: number;
  dataset_status?: string | null;
  source_versions?: Record<string, string[]> | null;
  coverage?: {
    country: string;
    satellites: string[];
    includes_nrt: boolean;
    region_fallback: string;
  } | null;
  nrt?: {
    provisional: boolean;
    since: string | null;
    provisional_months: string[];
    last_run: string | null;
    ok: boolean;
    errors: Record<string, string>;
  };
  validation?: {
    test_years: number[] | null;
    r: number | null;
    bias: number | null;
    mae: number | null;
    meets_target: boolean | null;
    limitations: string[];
  };
}

export function useMeta() {
  return useQuery({
    queryKey: ['meta'],
    queryFn: () => apiGet<Meta>('/meta'),
    staleTime: 5 * 60 * 1000,
    refetchInterval: 60 * 1000,
  });
}
