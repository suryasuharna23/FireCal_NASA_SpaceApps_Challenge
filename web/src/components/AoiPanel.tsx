import type { ReactNode } from 'react';
import { useT } from '../i18n';
import { formatKm2 } from '../lib/aoi';
import { useAppStore } from '../state/useAppStore';
import { Panel } from './Panel';

/** Current AOI summary plus the alternative ways to choose an area. */
export function AoiPanel({ children }: { children?: ReactNode }) {
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
      <p className="aoi-summary" aria-live="polite">
        {aoi ? (
          <>
            <strong>{aoi.label ?? t('aoi.drawn')}</strong>
            <span className="muted"> · {formatKm2(aoi.areaKm2, lang)}</span>
          </>
        ) : (
          <span className="muted">{t('common.selectAoi')}</span>
        )}
      </p>
      {children}
    </Panel>
  );
}
