import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useT } from '../i18n';
import {
  listCountryProvinces,
  listFireRegions,
  loadRegionAoi,
  loadRegionBoundaries,
  regionAtCoordinate,
  regionFeatureAoi,
  type FireRegion,
} from '../lib/regions';
import { useAppStore } from '../state/useAppStore';

/** Quick list of fire regions; choosing one flies the globe there and opens its calendar. */
export function RegionList() {
  const { t } = useT();
  const scope = useAppStore((s) => s.scope);
  const aoi = useAppStore((s) => s.aoi);
  const setAoi = useAppStore((s) => s.setAoi);
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState('');
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const regions = useQuery({
    queryKey: ['fire-regions', scope],
    queryFn: () => listFireRegions(scope),
    staleTime: 60 * 60 * 1000,
  });
  const provincesQuery = useQuery({
    queryKey: ['country-provinces', expanded],
    queryFn: () => listCountryProvinces(expanded!),
    enabled: expanded !== null,
    staleTime: 60 * 60 * 1000,
  });
  const country = (regions.data ?? []).find((region) => region.level === 0);
  const entries = (regions.data ?? []).filter((region) =>
    scope === 'global' ? region.level === 0 : region.level === 1,
  );
  const visible = entries.filter((region) =>
    region.name
      .toLocaleLowerCase(scope === 'global' ? 'en' : 'id')
      .includes(filter.toLocaleLowerCase(scope === 'global' ? 'en' : 'id')),
  );
  const showCountry =
    scope === 'indonesia' &&
    country &&
    country.name.toLocaleLowerCase('id').includes(filter.toLocaleLowerCase('id'));

  const choose = async (region: FireRegion) => {
    setLoadingId(region.id);
    setError(null);
    try {
      setAoi(await loadRegionAoi(region, scope));
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setLoadingId(null);
    }
  };

  const select = async (region: FireRegion) => {
    if (scope === 'global' && region.level === 0 && region.too_large) {
      setExpanded((current) => (current === region.country ? null : region.country));
    }
    await choose(region);
  };

  const chooseCoordinate = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const lat = Number(latitude);
    const lon = Number(longitude);
    if (
      !latitude.trim() ||
      !longitude.trim() ||
      !Number.isFinite(lat) ||
      !Number.isFinite(lon) ||
      Math.abs(lat) > 90 ||
      Math.abs(lon) > 180
    ) {
      setError(t('coord.invalid'));
      return;
    }
    setLoadingId('coordinate');
    setError(null);
    try {
      const region = regionAtCoordinate(await loadRegionBoundaries(scope), lat, lon);
      if (region) setAoi(regionFeatureAoi(region));
      else setError(t('coord.outside'));
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setLoadingId(null);
    }
  };

  return (
    <div className="region-list">
      <form className="region-list__coordinates" onSubmit={(event) => void chooseCoordinate(event)}>
        <label>
          {t('coord.latitude')}
          <input
            type="number"
            min={-90}
            max={90}
            step="any"
            required
            value={latitude}
            onChange={(event) => setLatitude(event.target.value)}
            placeholder="-6.2"
          />
        </label>
        <label>
          {t('coord.longitude')}
          <input
            type="number"
            min={-180}
            max={180}
            step="any"
            required
            value={longitude}
            onChange={(event) => setLongitude(event.target.value)}
            placeholder="106.8"
          />
        </label>
        <button type="submit" className="btn btn--small" disabled={loadingId !== null}>
          {t('coord.select')}
        </button>
      </form>
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
        <p className="muted small">
          {scope === 'global'
            ? t('regions.availableCountries', { n: entries.length })
            : t('regions.available', { n: entries.length })}
          {scope === 'global' &&
            ' · Other countries use the available 2026 snapshot. Select Indonesia for its full regional history.'}
        </p>
      )}
      <ul aria-label={t('regions.title')}>
        {visible.map((region) => (
          <li key={region.id}>
            <button
              type="button"
              className="chip"
              aria-pressed={aoi?.regionId === region.id}
              aria-expanded={scope === 'global' && expanded === region.country ? 'true' : undefined}
              title={`${region.name}, ${region.country}`}
              disabled={loadingId !== null}
              onClick={() => void select(region)}
            >
              {region.name}
              <span className="chip__meta">
                {region.too_large && scope === 'global'
                  ? t('search.tooLarge')
                  : scope === 'global'
                    ? region.level === 0
                      ? t('search.country')
                      : region.country
                    : region.country}
              </span>
            </button>
          </li>
        ))}
        {scope === 'global' &&
          expanded !== null &&
          (provincesQuery.data ?? []).map((region) => (
            <li key={region.id} className="region-list__province">
              <button
                type="button"
                className="chip"
                aria-pressed={aoi?.regionId === region.id}
                title={`${region.name}, ${region.country}`}
                disabled={loadingId !== null}
                onClick={() => void choose(region)}
              >
                {region.name}
                <span className="chip__meta">{t('search.province')}</span>
              </button>
            </li>
          ))}
      </ul>
      {scope === 'global' && expanded !== null && provincesQuery.isFetching && (
        <p className="muted small">{t('status.loading')}</p>
      )}
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
