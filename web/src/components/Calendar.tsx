import { useT } from '../i18n';
import { Panel } from './Panel';

/** Placeholder - implemented in T-26. */
export function Calendar() {
  const { t } = useT();
  return (
    <Panel title={t('panel.calendar')}>
      <p className="muted">{t('common.comingSoon')}</p>
    </Panel>
  );
}
