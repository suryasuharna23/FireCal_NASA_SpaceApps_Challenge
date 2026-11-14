import { useT } from '../i18n';
import { FIRE_REGIONS, regionAoi } from '../lib/regions';
import { useAppStore } from '../state/useAppStore';

/** Regions offered as one-click starting points. */
const QUICK_START = ['id-sumsel', 'br-cerrado', 'us-california', 'au-topend'];

/**
 * Single onboarding card shown in the results area until an area is chosen, instead
 * of an empty "select an area" message in every panel.
 */
export function EmptyState() {
  const { t } = useT();
  const setAoi = useAppStore((s) => s.setAoi);
  const picks = FIRE_REGIONS.filter((r) => QUICK_START.includes(r.id));

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
        {picks.map((region) => (
          <button
            key={region.id}
            type="button"
            className="chip"
            onClick={() => setAoi(regionAoi(region))}
          >
            {region.name}
            <span className="chip__meta">{region.country}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
