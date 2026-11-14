import { useMemo } from 'react';
import { useStats } from '../api/queries';
import { climatologyOption } from '../charts/climatology';
import { EChart } from '../charts/EChart';
import { useChartPng } from '../charts/useChartPng';
import { PngButton } from './PngButton';
import { useT } from '../i18n';
import { formatCount } from '../lib/colors';
import { monthNames } from '../lib/months';
import { useAppStore } from '../state/useAppStore';
import { Panel } from './Panel';

/** Monthly climatology chart with the critical fire season (FR-W-12, FR-W-14). */
export function Climatology() {
  const { t, lang } = useT();
  const aoi = useAppStore((s) => s.aoi);
  const { data, error, isFetching } = useStats();
  const year = data?.end.slice(0, 4) ?? '';
  const png = useChartPng();

  const option = useMemo(() => {
    if (!data) return null;
    return climatologyOption(data, {
      months: monthNames(lang),
      median: t('clim.median', { start: data.reference_years[0], end: data.reference_years[1] }),
      band: t('clim.band'),
      current: data.end.slice(0, 4),
      season: t('clim.season'),
      format: (v) => (v === null ? '–' : formatCount(v, lang)),
    });
  }, [data, lang, t]);

  if (!aoi) {
    return (
      <Panel title={t('panel.climatology')} id="climatology">
        <p className="muted">{t('common.selectAoi')}</p>
      </Panel>
    );
  }

  const months = monthNames(lang);
  const longMonths = monthNames(lang, 'long');
  const season =
    data?.critical_months.map((m) => longMonths[m - 1]).join(', ') || t('kpi.noSeason');

  return (
    <Panel
      title={t('panel.climatology')}
      id="climatology"
      actions={
        data && (
          <PngButton
            label={t('png.climatology')}
            onExport={() => png.exportPng(t('panel.climatology'), data, 'climatology')}
          />
        )
      }
    >
      {error && (
        <p className="form-error" role="alert">
          {(error as Error).message}
        </p>
      )}
      {!data && !error && <div className="skeleton" style={{ height: 260 }} aria-busy="true" />}
      {data && option && (
        <div className={isFetching ? 'is-stale' : ''}>
          <EChart
            option={option}
            ariaLabel={t('clim.aria', { months: season })}
            onReady={png.onReady}
          />
          <p className="muted small">
            {t('clim.note', { threshold: formatCount(data.critical_threshold ?? 0, lang) })}
          </p>
          <details className="table-alt">
            <summary>{t('calendar.asTable')}</summary>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th scope="col">{t('timectl.month')}</th>
                    <th scope="col">{t('clim.medianShort')}</th>
                    <th scope="col">P25</th>
                    <th scope="col">P75</th>
                    <th scope="col">{year}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.climatology.map((m) => (
                    <tr key={m.month}>
                      <th scope="row">
                        {months[m.month - 1]}
                        {m.critical ? ' •' : ''}
                      </th>
                      {[m.median, m.p25, m.p75, m.current].map((v, i) => (
                        <td key={i}>{v === null ? '–' : formatCount(v, lang)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </div>
      )}
    </Panel>
  );
}
