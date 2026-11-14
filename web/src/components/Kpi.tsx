import { useStats } from '../api/queries';
import { useT } from '../i18n';
import { formatCount, formatPct } from '../lib/colors';
import { monthNames } from '../lib/months';
import { useAppStore } from '../state/useAppStore';
import { Panel } from './Panel';

/**
 * Summary cards (FR-W-11): total hotspots, peak month, highest year and the latest month
 * against its historical median — the quick answer to "is this month worse than usual?"
 * (US-04).
 */
export function Kpi() {
  const { t, lang } = useT();
  const aoi = useAppStore((s) => s.aoi);
  const { data, error, isFetching } = useStats();
  const long = monthNames(lang, 'long');
  const fmt = (v: number | null | undefined) => (v == null ? '–' : formatCount(v, lang));

  if (!aoi) {
    return (
      <Panel title={t('panel.kpi')} id="summary">
        <p className="muted">{t('common.selectAoi')}</p>
      </Panel>
    );
  }
  if (error) {
    return (
      <Panel title={t('panel.kpi')} id="summary">
        <p className="form-error" role="alert">
          {(error as Error).message}
        </p>
      </Panel>
    );
  }
  if (!data) {
    return (
      <Panel title={t('panel.kpi')} id="summary">
        <div className="kpis" aria-busy="true">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="kpi skeleton" style={{ height: 92 }} />
          ))}
        </div>
      </Panel>
    );
  }

  const { summary, critical_months: critical } = data;
  const current = summary.current;
  const [cy, cm] = current ? current.month.split('-').map(Number) : [0, 0];
  const pct = current?.anomaly_pct ?? null;
  const tone = pct === null ? 'neutral' : pct > 10 ? 'hot' : pct < -10 ? 'cool' : 'neutral';
  const verdict =
    pct === null
      ? t('kpi.noMedian')
      : t(tone === 'hot' ? 'kpi.above' : tone === 'cool' ? 'kpi.below' : 'kpi.normal');

  return (
    <Panel title={t('panel.kpi')} id="summary">
      <div className={`kpis ${isFetching ? 'is-stale' : ''}`}>
        <article className={`kpi kpi--current kpi--${tone}`}>
          <h3>{t('kpi.current', { month: current ? `${long[cm! - 1]} ${cy}` : '–' })}</h3>
          <p className="kpi__value">{formatPct(pct, lang)}</p>
          <p className="kpi__sub">
            {verdict} · {fmt(current?.value)} {t('kpi.vs')} {fmt(current?.median)}
            {current?.percentile != null && <> · P{Math.round(current.percentile)}</>}
          </p>
          {current?.provisional && (
            <span className="badge badge--warn">{t('status.provisional')}</span>
          )}
        </article>
        <article className="kpi">
          <h3>{t('kpi.total')}</h3>
          <p className="kpi__value">{fmt(summary.total)}</p>
          <p className="kpi__sub">
            {t('kpi.range', { start: data.start, end: data.end })} ·{' '}
            {t('kpi.perMonth', { v: fmt(summary.monthly_mean) })}
          </p>
        </article>
        <article className="kpi">
          <h3>{t('kpi.peak')}</h3>
          <p className="kpi__value">{summary.peak_month ? long[summary.peak_month - 1] : '–'}</p>
          <p className="kpi__sub">
            {critical.length
              ? t('kpi.season', { months: critical.map((m) => long[m - 1]).join(', ') })
              : t('kpi.noSeason')}
          </p>
        </article>
        <article className="kpi">
          <h3>{t('kpi.maxYear')}</h3>
          <p className="kpi__value">{summary.max_year ?? '–'}</p>
          <p className="kpi__sub">{t('kpi.yearTotal', { v: fmt(summary.max_year_total) })}</p>
        </article>
      </div>
    </Panel>
  );
}
