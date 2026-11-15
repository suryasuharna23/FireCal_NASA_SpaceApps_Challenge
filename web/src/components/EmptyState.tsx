import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useT } from '../i18n';
import {
  FEATURED_REGION_IDS,
  listFireRegions,
  loadRegionAoi,
  type FireRegion,
} from '../lib/regions';
import { useAppStore } from '../state/useAppStore';

/**
 * Single onboarding card shown in the results area until an area is chosen, instead
 * of an empty "select an area" message in every panel.
 */
export function EmptyState() {
  const { t } = useT();
  const setAoi = useAppStore((s) => s.setAoi);
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const regions = useQuery({
    queryKey: ['fire-regions'],
    queryFn: listFireRegions,
    staleTime: 60 * 60 * 1000,
  });
  const featured = (regions.data ?? []).filter((region) => FEATURED_REGION_IDS.includes(region.id));

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
    <section className="empty" aria-labelledby="empty-title">
      <div className="empty__orbit" aria-hidden="true" />
      <h2 id="empty-title">{t('empty.title')}</h2>
      <p className="empty__lead">{t('empty.lead')}</p>
      <ol className="empty__steps">
        <li>
          <strong>{t('empty.step1')}</strong>
          <span>{t('empty.step1Hint')}</span>
        </li>
        <li>
          <strong>{t('empty.step2')}</strong>
          <span>{t('empty.step2Hint')}</span>
        </li>
        <li>
          <strong>{t('empty.step3')}</strong>
          <span>{t('empty.step3Hint')}</span>
        </li>
      </ol>
      <div className="empty__picks">
        <span className="muted">{t('empty.try')}</span>
        {featured.map((region) => (
          <button
            key={region.id}
            type="button"
            className="chip"
            disabled={loadingId !== null}
            onClick={() => void choose(region)}
          >
            {region.name}
            <span className="chip__meta">{region.country}</span>
          </button>
        ))}
      </div>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
