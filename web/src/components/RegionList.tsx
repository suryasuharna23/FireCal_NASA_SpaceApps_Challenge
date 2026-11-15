import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useT } from '../i18n';
import { listFireRegions, loadRegionAoi, type FireRegion } from '../lib/regions';
import { useAppStore } from '../state/useAppStore';

/** Quick list of fire regions; choosing one flies the globe there and opens its calendar. */
export function RegionList() {
  const { t } = useT();
  const aoi = useAppStore((s) => s.aoi);
  const setAoi = useAppStore((s) => s.setAoi);
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState('');
  const regions = useQuery({
    queryKey: ['fire-regions'],
    queryFn: listFireRegions,
    staleTime: 60 * 60 * 1000,
  });
  const country = (regions.data ?? []).find((region) => region.level === 0);
  const provinces = (regions.data ?? []).filter((region) => region.level === 1);
  const visible = provinces.filter((region) =>
    region.name.toLocaleLowerCase('id').includes(filter.toLocaleLowerCase('id')),
  );
  const showCountry =
    country && country.name.toLocaleLowerCase('id').includes(filter.toLocaleLowerCase('id'));

  const choose = async (region: FireRegion) => {
    setLoadingId(region.id);
    setError(null);
    try {
      setAoi(await loadRegionAoi(region));
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setLoadingId(null);
    }
  };

  return (
    <div className="region-list">
      <label className="region-list__filter">
        <span className="sr-only">{t('search.label')}</span>
        <input
          type="search"
          value={filter}
          placeholder={t('search.placeholder')}
          onChange={(event) => setFilter(event.target.value)}
        />
      </label>
      {showCountry && (
        <button
          type="button"
          className="chip region-list__country"
          aria-pressed={aoi?.regionId === country.id}
          disabled={loadingId !== null}
          onClick={() => void choose(country)}
        >
          {country.name}
          <span className="chip__meta">{t('regions.country')}</span>
        </button>
      )}
      {regions.data && (
        <p className="muted small">{t('regions.available', { n: provinces.length })}</p>
      )}
      <ul aria-label={t('regions.title')}>
        {visible.map((region) => (
          <li key={region.id}>
            <button
              type="button"
              className="chip"
              aria-pressed={aoi?.regionId === region.id}
              title={`${region.name}, ${region.country}`}
              disabled={loadingId !== null}
              onClick={() => void choose(region)}
            >
              {region.name}
              <span className="chip__meta">{region.country}</span>
            </button>
          </li>
        ))}
      </ul>
      {regions.isError && (
        <p className="form-error" role="alert">
          {(regions.error as Error).message}
        </p>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
