import { useEffect, useRef, useState } from 'react';
import { useMeta } from './api/client';
import { AnnualTotals } from './components/AnnualTotals';
import { ExportPanel } from './components/ExportPanel';
import { Calendar } from './components/Calendar';
import { Climatology } from './components/Climatology';
import { Kpi } from './components/Kpi';
import { AiInsight } from './components/AiInsight';
import { GlobeMap } from './components/GlobeMap';
import { StatusBar } from './components/StatusBar';
import { TimePanel } from './components/TimePanel';
import { AoiPanel } from './components/AoiPanel';
import { EmptyState } from './components/EmptyState';
import { Methodology } from './components/Methodology';
import { ShareButton } from './components/ShareButton';
import { useT } from './i18n';
import { useAppStore } from './state/useAppStore';
import { useUrlSync } from './state/useUrlSync';
import { useDataVersionRefresh } from './state/useDataVersionRefresh';

type Page = 'app' | 'methodology';

export default function App() {
  const { t } = useT();
  const [page, setPage] = useState<Page>('app');
  const aoi = useAppStore((s) => s.aoi);
  const scope = useAppStore((s) => s.scope);
  const setScope = useAppStore((s) => s.setScope);
  const meta = useMeta().data;
  const globalPointsAvailable = meta?.global?.points_available !== false;
  const initialScopeChecked = useRef(false);
  useUrlSync();
  useDataVersionRefresh();

  useEffect(() => {
    if (!meta || initialScopeChecked.current) return;
    initialScopeChecked.current = true;
    if (meta.global?.status === 'ok' && scope === 'indonesia' && !aoi && !window.location.search) {
      setScope('global');
    }
  }, [meta, scope, aoi, setScope]);

  return (
    <div className="app">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="app__header">
        <div className="brand">
          <div>
            <h1>
              <img className="brand__logo" src="/logo/firecal-logo.svg" alt="FireCal" />
            </h1>
          </div>
        </div>
        <nav className="tabs" aria-label="FireCal">
          {(['app', 'methodology'] as const).map((p) => (
            <button
              key={p}
              type="button"
              className="tabs__tab"
              aria-current={page === p ? 'page' : undefined}
              onClick={() => setPage(p)}
            >
              {t(p === 'app' ? 'nav.app' : 'nav.methodology')}
            </button>
          ))}
          <ShareButton />
        </nav>
      </header>
      <StatusBar />

      {page === 'app' ? (
        <main id="main" className="layout">
          <section className="layout__view" aria-label={t('region.view')}>
            <GlobeMap />
          </section>
          <section className="layout__side" aria-label={t('region.controls')}>
            <AoiPanel />
            {scope === 'indonesia' && <TimePanel />}
          </section>
          <section className="layout__results" aria-label={t('region.results')}>
            {scope === 'global' ? (
              <div className="results__summary">
                <h2>Worldwide observations · last three months</h2>
                <p>
                  Explore monthly, daily, or hourly detections on the globe.
                  {aoi && ` Selected area: ${aoi.label}.`}
                  {globalPointsAvailable && ' Select an area to inspect its points.'}
                </p>
                {!globalPointsAvailable && (
                  <p>Detailed detection points are unavailable in this deployment.</p>
                )}
                <p>
                  The historical calendar and comparisons with earlier years are available in the
                  Indonesia view. No global historical comparison or sensor correction is available.
                </p>
                <button
                  type="button"
                  className="btn btn--primary btn--small"
                  onClick={() => setScope('indonesia')}
                >
                  Indonesia history · {meta?.start_month} to {meta?.end_month}
                </button>
              </div>
            ) : aoi ? (
              <>
                <div className="results__summary">
                  <Kpi />
                  <AiInsight />
                </div>
                <div className="results__calendar">
                  <Calendar />
                </div>
                <div className="results__charts">
                  <Climatology />
                  <AnnualTotals />
                  <ExportPanel />
                </div>
              </>
            ) : (
              <div className="results__summary">
                <EmptyState />
              </div>
            )}
          </section>
        </main>
      ) : (
        <main id="main" className="page">
          <Methodology />
        </main>
      )}

      <footer className="app__footer">{t('footer.attribution')}</footer>
    </div>
  );
}
