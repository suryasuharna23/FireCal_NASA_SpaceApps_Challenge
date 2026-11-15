import { useT } from '../i18n';
import { formatKm2 } from '../lib/aoi';
import { useAppStore } from '../state/useAppStore';
import { Panel } from './Panel';
import { RegionList } from './RegionList';

/** Choose any province boundary present in the current Indonesia dataset. */
export function AoiPanel() {
  const { t, lang } = useT();
  const aoi = useAppStore((s) => s.aoi);
  const setAoi = useAppStore((s) => s.setAoi);

  return (
    <Panel
      title={t('panel.aoi')}
      id="aoi-panel"
      actions={
        aoi && (
          <button type="button" className="btn btn--small" onClick={() => setAoi(null)}>
            {t('aoi.clear')}
          </button>
        )
      }
    >
      <p className={`aoi-summary ${aoi ? 'aoi-summary--set' : ''}`} aria-live="polite">
        {aoi ? (
          <>
            <strong>{aoi.label}</strong>
            <span className="muted"> · {formatKm2(aoi.areaKm2, lang)}</span>
          </>
        ) : (
          <span className="muted">{t('aoiTabs.none')}</span>
        )}
      </p>
      <RegionList />
    </Panel>
  );
}
