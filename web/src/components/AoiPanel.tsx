import { useId, useRef, useState, type KeyboardEvent } from 'react';
import { useT, type MessageKey } from '../i18n';
import { formatKm2 } from '../lib/aoi';
import { useAppStore } from '../state/useAppStore';
import { CircleForm } from './CircleForm';
import { GeoJsonUpload } from './GeoJsonUpload';
import { Panel } from './Panel';
import { RegionList } from './RegionList';
import { RegionSearch } from './RegionSearch';

const TABS = [
  { id: 'regions', label: 'aoiTabs.regions', Component: RegionList },
  { id: 'search', label: 'aoiTabs.search', Component: RegionSearch },
  { id: 'circle', label: 'aoiTabs.circle', Component: CircleForm },
  { id: 'upload', label: 'aoiTabs.upload', Component: GeoJsonUpload },
] as const satisfies readonly { id: string; label: MessageKey; Component: () => unknown }[];

type TabId = (typeof TABS)[number]['id'];

/**
 * Current AOI summary plus the ways to choose an area, one at a time in tabs
 * (ARIA tabs pattern: arrow keys, Home and End move between tabs).
 */
export function AoiPanel() {
  const { t, lang } = useT();
  const aoi = useAppStore((s) => s.aoi);
  const setAoi = useAppStore((s) => s.setAoi);
  const [active, setActive] = useState<TabId>('regions');
  const base = useId();
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const i = TABS.findIndex((tab) => tab.id === active);
    const next =
      e.key === 'ArrowRight'
        ? (i + 1) % TABS.length
        : e.key === 'ArrowLeft'
          ? (i - 1 + TABS.length) % TABS.length
          : e.key === 'Home'
            ? 0
            : e.key === 'End'
              ? TABS.length - 1
              : -1;
    if (next < 0) return;
    e.preventDefault();
    setActive(TABS[next]!.id);
    tabRefs.current[next]?.focus();
  };

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
            <strong>{aoi.label ?? t('aoi.drawn')}</strong>
            <span className="muted"> · {formatKm2(aoi.areaKm2, lang)}</span>
          </>
        ) : (
          <span className="muted">{t('aoiTabs.none')}</span>
        )}
      </p>
      <div
        className="tabs-line"
        role="tablist"
        aria-label={t('aoiTabs.label')}
        onKeyDown={onKeyDown}
      >
        {TABS.map((tab, i) => (
          <button
            key={tab.id}
            ref={(el) => {
              tabRefs.current[i] = el;
            }}
            id={`${base}-tab-${tab.id}`}
            type="button"
            role="tab"
            className="tabs-line__tab"
            aria-selected={active === tab.id}
            aria-controls={`${base}-panel-${tab.id}`}
            tabIndex={active === tab.id ? 0 : -1}
            onClick={() => setActive(tab.id)}
          >
            {t(tab.label)}
          </button>
        ))}
      </div>
      {TABS.map(({ id, Component }) => (
        <div
          key={id}
          id={`${base}-panel-${id}`}
          role="tabpanel"
          aria-labelledby={`${base}-tab-${id}`}
          className="tabs-line__panel"
          hidden={active !== id}
        >
          {active === id && <Component />}
        </div>
      ))}
    </Panel>
  );
}
