import { useQuery } from '@tanstack/react-query';
import type { MultiPolygon, Polygon } from 'geojson';
import { useEffect, useId, useState } from 'react';
import { apiGet } from '../api/client';
import { useT } from '../i18n';
import { formatKm2 } from '../lib/aoi';
import { useAppStore } from '../state/useAppStore';

interface RegionHit {
  id: string;
  name: string;
  level: number;
  country: string | null;
  parent: string | null;
  area_km2: number;
  bbox: [number, number, number, number];
  too_large: boolean;
}

interface RegionFeature {
  type: 'Feature';
  id: string;
  properties: RegionHit;
  geometry: Polygon | MultiPolygon;
}

function useDebounced<T>(value: T, ms = 250): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setV(value), ms);
    return () => window.clearTimeout(id);
  }, [value, ms]);
  return v;
}

/** Search countries and provinces/states and use the boundary as the AOI (FR-W-03). */
export function RegionSearch() {
  const { t, lang } = useT();
  const setAoi = useAppStore((s) => s.setAoi);
  const [query, setQuery] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const q = useDebounced(query.trim());
  const listId = useId();

  const results = useQuery({
    queryKey: ['/regions', q],
    queryFn: () => apiGet<{ results: RegionHit[] }>('/regions', { q, limit: 8 }),
    enabled: q.length >= 2,
    staleTime: 60 * 60 * 1000,
  });

  const choose = async (hit: RegionHit) => {
    setError(null);
    setLoadingId(hit.id);
    try {
      const feature = await apiGet<RegionFeature>(`/regions/${encodeURIComponent(hit.id)}`);
      setAoi({
        kind: 'region',
        geometry: feature.geometry,
        areaKm2: hit.area_km2,
        label: hit.level === 0 || !hit.country ? hit.name : `${hit.name}, ${hit.country}`,
        regionId: hit.id,
      });
      setQuery('');
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoadingId(null);
    }
  };

  const levelName = (level: number) =>
    t(level === 0 ? 'search.country' : level === 1 ? 'search.province' : 'search.district');
  const hits = q.length >= 2 ? (results.data?.results ?? []) : [];

  return (
    <div className="region-search">
      <label htmlFor={`${listId}-input`} className="region-search__label">
        {t('search.label')}
      </label>
      <input
        id={`${listId}-input`}
        type="search"
        value={query}
        placeholder={t('search.placeholder')}
        autoComplete="off"
        aria-controls={listId}
        aria-describedby={`${listId}-hint`}
        onChange={(e) => setQuery(e.target.value)}
      />
      <small id={`${listId}-hint`} className="muted">
        {t('search.hint')}
      </small>
      {results.isError && (
        <p className="form-error" role="alert">
          {(results.error as Error).message}
        </p>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {q.length >= 2 && results.isSuccess && hits.length === 0 && (
        <p className="muted small">{t('search.none')}</p>
      )}
      {hits.length > 0 && (
        <ul id={listId} className="region-search__results" aria-label={t('search.results')}>
          {hits.map((hit) => (
            <li key={hit.id}>
              <button
                type="button"
                disabled={hit.too_large || loadingId !== null}
                onClick={() => choose(hit)}
                title={hit.too_large ? t('search.tooLarge') : undefined}
              >
                <span className="region-search__name">{hit.name}</span>
                <span className="region-search__meta">
                  {levelName(hit.level)}
                  {hit.level > 0 && hit.country ? ` · ${hit.country}` : ''} ·{' '}
                  {formatKm2(hit.area_km2, lang)}
                  {hit.too_large && ` · ${t('search.tooLarge')}`}
                  {loadingId === hit.id && ' · …'}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
