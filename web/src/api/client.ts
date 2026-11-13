import { useQuery } from '@tanstack/react-query';

const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '');

export async function apiGet<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(`${BASE_URL}${path}`);
  if (params) url.search = new URLSearchParams(params).toString();
  const response = await fetch(url);
  if (!response.ok) throw new Error(`GET ${path} failed: ${response.status}`);
  return (await response.json()) as T;
}

export interface Meta {
  api_version: string;
  data_version: string | null;
  last_updated: string | null;
  nrt_provisional: boolean | null;
  attribution: string;
}

export function useMeta() {
  return useQuery({ queryKey: ['meta'], queryFn: () => apiGet<Meta>('/meta') });
}
