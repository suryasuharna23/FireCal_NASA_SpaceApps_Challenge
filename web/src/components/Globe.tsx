import { useT } from '../i18n';
import { Panel } from './Panel';

/** Placeholder - implemented in T-41. */
export function Globe() {
  const { t } = useT();
  return (
    <Panel title={t('panel.globe')}>
      <p className="muted">{t('common.comingSoon')}</p>
    </Panel>
  );
}
