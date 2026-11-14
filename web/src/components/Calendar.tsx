import { useMemo } from 'react';
import { useCalendar, type MonthValue } from '../api/queries';
import { useT } from '../i18n';
import { countColor, countScale, formatCount, gradient } from '../lib/colors';
import { monthNames } from '../lib/months';
import { useAppStore } from '../state/useAppStore';
import { Panel } from './Panel';

/** Year x month heatmap of harmonized hotspot counts in the AOI (FR-W-07, FR-W-08). */
export function Calendar() {
  const { t, lang } = useT();
  const aoi = useAppStore((s) => s.aoi);
  const scale = useAppStore((s) => s.scale);
  const setScale = useAppStore((s) => s.setScale);
  const mode = useAppStore((s) => s.mode);
  const selected = useAppStore((s) => s.selected);
  const setSelected = useAppStore((s) => s.setSelected);
  const { data, error, isFetching } = useCalendar();

  const valueOf = (m: MonthValue) => (mode === 'raw' ? m.raw : m.value);
  const grid = useMemo(() => {
    if (!data) return null;
    const byYear = new Map<number, (MonthValue | undefined)[]>();
    for (const m of data.months) {
      if (!byYear.has(m.year)) byYear.set(m.year, Array(12).fill(undefined));
      byYear.get(m.year)![m.month - 1] = m;
    }
    return [...byYear.entries()].sort((a, b) => a[0] - b[0]);
  }, [data]);

  const months = monthNames(lang);
  const longMonths = monthNames(lang, 'long');
  const max = data ? Math.max(0, ...data.months.map(valueOf)) : 0;
  const color = countScale(max, scale);

  const actions = (
    <div className="segmented" role="group" aria-label={t('calendar.scale')}>
      {(['linear', 'log'] as const).map((s) => (
        <button
          key={s}
          type="button"
          className="btn btn--small"
          aria-pressed={scale === s}
          onClick={() => setScale(s)}
        >
          {t(s === 'linear' ? 'calendar.linear' : 'calendar.log')}
        </button>
      ))}
    </div>
  );

  if (!aoi) {
    return (
      <Panel title={t('panel.calendar')} id="calendar">
        <p className="muted">{t('common.selectAoi')}</p>
      </Panel>
    );
  }

  const label = (m: MonthValue) =>
    t('calendar.cellLabel', {
      month: `${longMonths[m.month - 1]} ${m.year}`,
      value: formatCount(valueOf(m), lang),
    });

  return (
    <Panel title={t('panel.calendar')} id="calendar" actions={actions}>
      {error && (
        <p className="form-error" role="alert">
          {(error as Error).message}
        </p>
      )}
      {!grid && !error && <div className="skeleton skeleton--calendar" aria-busy="true" />}
      {grid && (
        <div className={`calendar-wrap ${isFetching ? 'is-stale' : ''}`} aria-busy={isFetching}>
          <div
            className="calendar"
            role="grid"
            aria-label={t('calendar.aria', { start: data!.start, end: data!.end })}
            aria-rowcount={grid.length + 1}
          >
            <div className="calendar__row" role="row">
              <span className="calendar__corner" role="columnheader" />
              {months.map((name) => (
                <span key={name} className="calendar__month" role="columnheader">
                  {name}
                </span>
              ))}
            </div>
            {grid.map(([year, row]) => (
              <div className="calendar__row" role="row" key={year}>
                <span className="calendar__year" role="rowheader">
                  {year}
                </span>
                {row.map((m, i) =>
                  m ? (
                    <button
                      key={i}
                      type="button"
                      role="gridcell"
                      className={[
                        'calendar__cell',
                        m.provisional ? 'calendar__cell--nrt' : '',
                        selected?.year === m.year && selected.month === m.month
                          ? 'calendar__cell--selected'
                          : '',
                      ].join(' ')}
                      style={{ background: color(valueOf(m)) }}
                      aria-label={label(m)}
                      aria-selected={selected?.year === m.year && selected.month === m.month}
                      title={label(m)}
                      onClick={() => setSelected({ year: m.year, month: m.month })}
                    />
                  ) : (
                    <span
                      key={i}
                      className="calendar__cell calendar__cell--empty"
                      role="gridcell"
                    />
                  ),
                )}
              </div>
            ))}
          </div>
        </div>
      )}
      {grid && (
        <div className="legend" aria-label={t('calendar.legend')}>
          <div className="legend__bar" style={{ background: gradient(countColor) }} />
          <div className="legend__ticks">
            <span>{scale === 'log' ? '1' : '0'}</span>
            <span>
              {formatCount(scale === 'log' ? Math.sqrt(Math.max(max, 1)) : max / 2, lang)}
            </span>
            <span>{formatCount(max, lang)}</span>
          </div>
          <p className="muted small">
            {t(mode === 'raw' ? 'calendar.unitRaw' : 'calendar.unit')}
            {data!.months.some((m) => m.provisional) && <> · {t('calendar.nrtNote')}</>}
          </p>
        </div>
      )}
      {grid && (
        <details className="table-alt">
          <summary>{t('calendar.asTable')}</summary>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">{t('calendar.year')}</th>
                  {months.map((n) => (
                    <th key={n} scope="col">
                      {n}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {grid.map(([year, row]) => (
                  <tr key={year}>
                    <th scope="row">{year}</th>
                    {row.map((m, i) => (
                      <td key={i}>{m ? formatCount(valueOf(m), lang) : ''}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </Panel>
  );
}
