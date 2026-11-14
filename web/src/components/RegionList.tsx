import { useT } from '../i18n';
import { FIRE_REGIONS, regionAoi } from '../lib/regions';
import { useAppStore } from '../state/useAppStore';

/** Quick list of fire regions; choosing one flies the globe there and opens its calendar. */
export function RegionList() {
  const { t } = useT();
  const aoi = useAppStore((s) => s.aoi);
  const setAoi = useAppStore((s) => s.setAoi);

  return (
    <div className="region-list">
      <ul aria-label={t('regions.title')}>
        {FIRE_REGIONS.map((region) => (
          <li key={region.id}>
            <button
              type="button"
              className="chip"
              aria-pressed={aoi?.regionId === region.id}
              title={`${region.name}, ${region.country} · ${region.radiusKm} km`}
              onClick={() => setAoi(regionAoi(region))}
            >
              {region.name}
              <span className="chip__meta">{region.country}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
