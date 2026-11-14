import { useState } from 'react';
import { AnnualTotals } from './components/AnnualTotals';
import { ExportPanel } from './components/ExportPanel';
import { Calendar } from './components/Calendar';
import { Climatology } from './components/Climatology';
import { Kpi } from './components/Kpi';
import { GlobeMap } from './components/GlobeMap';
import { StatusBar } from './components/StatusBar';
import { TimePanel } from './components/TimePanel';
import { AoiPanel } from './components/AoiPanel';
import { CircleForm } from './components/CircleForm';
import { RegionSearch } from './components/RegionSearch';
import { GeoJsonUpload } from './components/GeoJsonUpload';
import { Methodology } from './components/Methodology';
import { ShareButton } from './components/ShareButton';
import { useT } from './i18n';
import { useUrlSync } from './state/useUrlSync';

type Page = 'app' | 'methodology';

export default function App() {
  const { t } = useT();
  const [page, setPage] = useState<Page>('app');
  useUrlSync();

  return (
    <div className="app">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="app__header">
        <div className="brand">
          <span className="brand__mark" aria-hidden="true" />
          <div>
            <h1>FireCal</h1>
            <p>{t('app.tagline')}</p>
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
            <AoiPanel>
              <RegionSearch />
              <CircleForm />
              <GeoJsonUpload />
            </AoiPanel>
            <TimePanel />
          </section>
          <section className="layout__results" aria-label={t('region.results')}>
            <Kpi />
            <Calendar />
            <Climatology />
            <AnnualTotals />
            <ExportPanel />
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
