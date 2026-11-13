import { useT } from '../i18n';
import { Panel } from './Panel';

/** Placeholder - implemented in T-21. */
export function MapAoi() {
  const t = useT();
  return (
    <Panel title={t('mapAoi')}>
      <p>{t('comingSoon')}</p>
    </Panel>
  );
}
