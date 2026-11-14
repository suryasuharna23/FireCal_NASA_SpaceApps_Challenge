import { useMemo } from 'react';
import { useStats } from '../api/queries';
import { annualOption } from '../charts/annual';
import { EChart } from '../charts/EChart';
import { useChartPng } from '../charts/useChartPng';
import { PngButton } from './PngButton';
import { useT } from '../i18n';
import { formatCount } from '../lib/colors';
import { useAppStore } from '../state/useAppStore';
import { Panel } from './Panel';

/** Annual totals with rank; the highest year is marked (FR-W-13). */
export function AnnualTotals() {
  const { t, lang } = useT();
  const aoi = useAppStore((s) => s.aoi);
  const { data, error, isFetching } = useStats();
  const png = useChartPng();

  const option = useMemo(() => {
    if (!data?.annual.length) return null;
    return annualOption(data.annual, {
      total: t('annual.total'),
      rank: (rank, of) => t('annual.rank', { rank, of }),
      partial: t('annual.partial'),
      format: (v) => formatCount(v, lang),
    });
  }, [data, lang, t]);

  if (!aoi) return null;

  const ranked = data ? [...data.annual].sort((a, b) => a.rank - b.rank) : [];
  const top = ranked[0];

  return (
    <Panel
      title={t('panel.annual')}
      id="annual"
      actions={
        data && (
          <PngButton
            label={t('png.annual')}
            onExport={() => png.exportPng(t('panel.annual'), data, 'annual')}
          />
        )
      }
    >
      {error && (
        <p className="form-error" role="alert">
          {(error as Error).message}
        </p>
      )}
      {!data && !error && <div className="skeleton" style={{ height: 240 }} aria-busy="true" />}
      {data && option && (
        <div className={isFetching ? 'is-stale' : ''}>
          <EChart
            option={option}
            height={240}
            onReady={png.onReady}
            ariaLabel={t('annual.aria', {
              year: top?.year ?? '–',
              total: formatCount(top?.total ?? 0, lang),
            })}
          />
          <details className="table-alt">
            <summary>{t('annual.table')}</summary>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th scope="col">#</th>
                    <th scope="col">{t('calendar.year')}</th>
                    <th scope="col">{t('annual.total')}</th>
                  </tr>
                </thead>
                <tbody>
                  {ranked.map((a) => (
                    <tr key={a.year}>
                      <td>{a.rank}</td>
                      <th scope="row">
                        {a.year}
                        {a.complete ? '' : ' *'}
                      </th>
                      <td>{formatCount(a.total, lang)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {ranked.some((a) => !a.complete) && (
              <p className="muted small">* {t('annual.partial')}</p>
            )}
          </details>
        </div>
      )}
    </Panel>
  );
}
