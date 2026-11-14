import { useT } from '../i18n';
import { Panel } from './Panel';

/** Placeholder - implemented in T-29. */
export function Climatology() {
  const { t } = useT();
  return (
    <Panel title={t('panel.climatology')}>
      <p className="muted">{t('common.comingSoon')}</p>
    </Panel>
  );
}
