import { useMemo, useState } from 'react';
import { useCalendar, useStats } from '../api/queries';
import { climatologyOption, type YearProfile } from '../charts/climatology';
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
  const playbackYear = useAppStore((s) => s.selected?.year);
  const { data, error, isFetching } = useStats();
  const { data: calendar, error: calendarError, isFetching: calendarFetching } = useCalendar();
  const [yearChoice, setYearChoice] = useState<number | 'follow'>('follow');
  const [compareChoice, setCompareChoice] = useState<number | null>(null);
  const [showBand, setShowBand] = useState(true);
  const [showSeason, setShowSeason] = useState(true);
  const png = useChartPng();

  const years = useMemo(
    () => [...new Set(calendar?.months.map((m) => m.year) ?? [])].sort((a, b) => b - a),
    [calendar],
  );
  const latestYear = years[0] ?? null;
  const focusYear =
    yearChoice === 'follow'
      ? playbackYear && years.includes(playbackYear)
        ? playbackYear
        : latestYear
      : years.includes(yearChoice)
        ? yearChoice
        : latestYear;
  const compareYear =
    compareChoice !== null && years.includes(compareChoice) && compareChoice !== focusYear
      ? compareChoice
      : null;
  const profiles = useMemo<YearProfile[]>(() => {
    if (!calendar || focusYear === null) return [];
    return [focusYear, compareYear]
      .filter((year): year is number => year !== null)
      .map((year) => {
        const rows = calendar.months.filter((m) => m.year === year);
        const values: (number | null)[] = Array(12).fill(null);
        for (const row of rows) values[row.month - 1] = row.value;
        return { year, values, partial: rows.length < 12 };
      });
  }, [calendar, focusYear, compareYear]);

  const matched =
    data &&
    calendar &&
    data.data_version === calendar.data_version &&
    data.start === calendar.start &&
    data.end === calendar.end &&
    data.reference_years[0] === calendar.reference_years[0] &&
    data.reference_years[1] === calendar.reference_years[1] &&
    data.aoi.cells === calendar.aoi.cells;

  const option = useMemo(() => {
    if (!data || !matched || !profiles.length) return null;
    return climatologyOption(
      data,
      {
        months: monthNames(lang),
        median: t('clim.median', { start: data.reference_years[0], end: data.reference_years[1] }),
        band: t('clim.band'),
        season: t('clim.season'),
        year: (year, partial) => `${year}${partial ? ` ${t('clim.partial')}` : ''}`,
        format: (v) => (v === null ? '–' : formatCount(v, lang)),
      },
      { years: profiles, showBand, showSeason },
    );
  }, [data, lang, matched, profiles, showBand, showSeason, t]);

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
  const failure = error ?? calendarError;

  return (
    <Panel
      title={t('panel.climatology')}
      id="climatology"
      actions={
        data &&
        option && (
          <PngButton
            label={t('png.climatology')}
            onExport={() =>
              png.exportPng(
                `${t('panel.climatology')} · ${profiles.map((profile) => profile.year).join(' vs ')}`,
                data,
                'climatology',
              )
            }
          />
        )
      }
    >
      {failure && (
        <p className="form-error" role="alert">
          {(failure as Error).message}
        </p>
      )}
      {!option && !failure && <div className="skeleton" style={{ height: 260 }} aria-busy="true" />}
      {data && option && (
        <div className={isFetching || calendarFetching ? 'is-stale' : ''}>
          <div className="climatology-controls" role="group" aria-label={t('clim.controls')}>
            <label>
              {t('clim.focusYear')}
              <select
                value={yearChoice}
                onChange={(event) =>
                  setYearChoice(
                    event.target.value === 'follow' ? 'follow' : Number(event.target.value),
                  )
                }
              >
                <option value="follow">
                  {t('clim.followPlayback', { year: focusYear ?? '–' })}
                </option>
                {years.map((year) => (
                  <option value={year} key={year}>
                    {year}
                    {calendar?.months.filter((m) => m.year === year).length === 12
                      ? ''
                      : ` ${t('clim.partial')}`}
                  </option>
                ))}
              </select>
            </label>
            <label>
              {t('clim.compareYear')}
              <select
                value={compareYear ?? ''}
                onChange={(event) =>
                  setCompareChoice(event.target.value ? Number(event.target.value) : null)
                }
              >
                <option value="">{t('clim.none')}</option>
                {years
                  .filter((year) => year !== focusYear)
                  .map((year) => (
                    <option value={year} key={year}>
                      {year}
                    </option>
                  ))}
              </select>
            </label>
            <label className="climatology-controls__toggle">
              <input
                type="checkbox"
                checked={showBand}
                onChange={(event) => setShowBand(event.target.checked)}
              />
              {t('clim.band')}
            </label>
            <label className="climatology-controls__toggle">
              <input
                type="checkbox"
                checked={showSeason}
                onChange={(event) => setShowSeason(event.target.checked)}
              />
              {t('clim.season')}
            </label>
          </div>
          <EChart
            option={option}
            height={profiles.length > 1 ? 290 : 260}
            ariaLabel={`${showSeason ? `${t('clim.aria', { months: season })} ` : ''}${t('clim.chartYears', { years: profiles.map((profile) => profile.year).join(', ') })}`}
            onReady={png.onReady}
          />
          <p className="clim-note muted small">
            {t('clim.referenceHint', {
              start: data.reference_years[0],
              end: data.reference_years[1],
            })}
            {showSeason && (
              <>
                {' '}
                · {t('clim.note', { threshold: formatCount(data.critical_threshold ?? 0, lang) })}
              </>
            )}
            {profiles.some((profile) => profile.partial) && <> · {t('clim.partialHint')}</>}
          </p>
          <details className="table-alt">
            <summary>{t('calendar.asTable')}</summary>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th scope="col">{t('timectl.month')}</th>
                    <th scope="col">{t('clim.medianShort')}</th>
                    {showBand && <th scope="col">P25</th>}
                    {showBand && <th scope="col">P75</th>}
                    {profiles.map((profile) => (
                      <th scope="col" key={profile.year}>
                        {profile.year}
                        {profile.partial ? ` ${t('clim.partial')}` : ''}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.climatology.map((m) => (
                    <tr key={m.month}>
                      <th scope="row">
                        {months[m.month - 1]}
                        {showSeason && m.critical ? ' •' : ''}
                      </th>
                      {[
                        m.median,
                        ...(showBand ? [m.p25, m.p75] : []),
                        ...profiles.map((profile) => profile.values[m.month - 1] ?? null),
                      ].map((v, i) => (
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
