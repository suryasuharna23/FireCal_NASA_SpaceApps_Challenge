import { useT } from '../i18n';
import { formatKm2 } from '../lib/aoi';
import { useAppStore } from '../state/useAppStore';
import { Panel } from './Panel';
import { RegionList } from './RegionList';
import { CircleForm } from './CircleForm';
import { GeoJsonUpload } from './GeoJsonUpload';

/** Choose any province boundary present in the current Indonesia dataset. */
export function AoiPanel() {
  const { t, lang } = useT();
  const aoi = useAppStore((s) => s.aoi);
  const setAoi = useAppStore((s) => s.setAoi);
  const scope = useAppStore((s) => s.scope);

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
          <span className="muted">
            {scope === 'global'
              ? 'Choose a location anywhere in the world, or upload its boundary.'
              : t('aoiTabs.none')}
          </span>
        )}
      </p>
      {scope === 'global' ? (
        <>
          <RegionList />
          <CircleForm />
          <GeoJsonUpload />
        </>
      ) : (
        <RegionList />
      )}
    </Panel>
  );
}
