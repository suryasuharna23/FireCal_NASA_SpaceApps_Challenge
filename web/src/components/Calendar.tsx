import { useT } from '../i18n';
import { Panel } from './Panel';

/** Placeholder - implemented in T-26. */
export function Calendar() {
  const t = useT();
  return (
    <Panel title={t('calendar')}>
      <p>{t('comingSoon')}</p>
    </Panel>
  );
}
