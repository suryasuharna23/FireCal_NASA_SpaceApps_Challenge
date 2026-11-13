import { Calendar } from './components/Calendar';
import { Climatology } from './components/Climatology';
import { Globe } from './components/Globe';
import { Kpi } from './components/Kpi';
import { MapAoi } from './components/MapAoi';
import { useT } from './i18n';

export default function App() {
  const t = useT();
  return (
    <div className="app">
      <header className="app__header">
        <h1>FireCal</h1>
        <p>{t('tagline')}</p>
      </header>
      <main className="app__main">
        <section className="app__view" aria-label={t('viewRegion')}>
          <Globe />
          <MapAoi />
        </section>
        <section className="app__results" aria-label={t('resultsRegion')}>
          <Kpi />
          <Calendar />
          <Climatology />
        </section>
      </main>
      <footer className="app__footer">{t('attribution')}</footer>
    </div>
  );
}
