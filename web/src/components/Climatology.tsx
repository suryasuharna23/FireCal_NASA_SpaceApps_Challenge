import { useT } from '../i18n';
import { Panel } from './Panel';

/** Placeholder - implemented in T-29. */
export function Climatology() {
  const t = useT();
  return (
    <Panel title={t('climatology')}>
      <p>{t('comingSoon')}</p>
    </Panel>
  );
}
