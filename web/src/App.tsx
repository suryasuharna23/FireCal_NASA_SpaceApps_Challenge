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
import { Methodology } from './components/Methodology';
import { ShareButton } from './components/ShareButton';
import { EmptyState } from './components/EmptyState';
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
          <img
            src="/firecal-logomark.svg"
            alt="FireCal Logo"
            className="brand__logo-img"
            width={38}
            height={48}
          />
          <div>
            <h1>FireCal</h1>
          </div>
        </div>
        <nav className="pill-navbar tabs" aria-label="FireCal">
          {(['app', 'methodology'] as const).map((p) => (
            <button
              key={p}
              type="button"
              className={`pill-navbar__tab tabs__tab ${page === p ? 'pill-navbar__tab--active' : ''}`}
              aria-current={page === p ? 'page' : undefined}
              onClick={() => setPage(p)}
            >
              {t(p === 'app' ? 'nav.app' : 'nav.methodology')}
            </button>
          ))}
        </nav>
      </header>
      <StatusBar />

      {page === 'app' ? (
        <main id="main" className={scope === 'global' ? 'layout layout--global' : 'layout'}>
          <div className="layout__top">
            <section className="layout__view-wrapper" aria-label={t('region.view')}>
              <div className="view-header">
                <h2 className="view-header__title">{t('app.hotspotTitle')}</h2>
                <div className="view-header__action">
                  <ShareButton />
                </div>
              </div>
              <div className="layout__view">
                <GlobeMap />
              </div>
              <ExportPanel />
            </section>
            <section className="layout__side" aria-label={t('region.controls')}>
              <AoiPanel />
              {scope === 'indonesia' && <TimePanel />}
            </section>
          </div>
          {scope === 'indonesia' && (
            <section className="layout__results" aria-label={t('region.results')}>
              {aoi ? (
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
                  </div>
                </>
              ) : (
                <div className="results__summary">
                  <EmptyState />
                </div>
              )}
            </section>
          )}
        </main>
      ) : (
        <main id="main" className="page">
          <Methodology />
        </main>
      )}

      <footer className="app__footer">
        <div className="footer__simple">
          <div className="footer__brand">
            <img src="/firecal-logomark.svg" alt="FireCal" width={20} height={26} />
            <span className="footer__name">FireCal</span>
            <span className="footer__dot">·</span>
            <span className="footer__note">NASA Space Apps Challenge</span>
          </div>
          <div className="footer__attr">
            <span>{t('footer.attribution')}</span>
            <span className="footer__dot">·</span>
            <span>Harmonized Wildfire Analytics</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
