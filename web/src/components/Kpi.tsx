import { useT } from '../i18n';
import { Panel } from './Panel';

/** Placeholder - implemented in T-28. */
export function Kpi() {
  const t = useT();
  return (
    <Panel title={t('kpi')}>
      <p>{t('comingSoon')}</p>
    </Panel>
  );
}
