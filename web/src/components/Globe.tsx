import { useT } from '../i18n';
import { Panel } from './Panel';

/** Placeholder - implemented in T-41. */
export function Globe() {
  const t = useT();
  return (
    <Panel title={t('globe')}>
      <p>{t('comingSoon')}</p>
    </Panel>
  );
}
