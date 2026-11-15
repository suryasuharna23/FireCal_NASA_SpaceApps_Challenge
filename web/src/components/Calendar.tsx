import { interpolateRdBu } from 'd3';
import { useMemo, useRef, useState, type FocusEvent, type MouseEvent } from 'react';
import { useCalendar, type MonthValue } from '../api/queries';
import { useT } from '../i18n';
import {
  anomalyScale,
  countColor,
  countScale,
  formatCount,
  formatPct,
  gradient,
} from '../lib/colors';
import { monthNames } from '../lib/months';
import { calendarLayout, drawCalendar, exportFramedPng } from '../lib/png';
import { FONT_BODY } from '../lib/fonts';
import { usePngFrame } from '../lib/usePngFrame';
import { PngButton } from './PngButton';
import { useAppStore } from '../state/useAppStore';
import { Panel } from './Panel';

const anomalyColor = anomalyScale(100);
/** Legend for the diverging anomaly palette: left = far below, right = far above. */
const anomalyRamp = (t: number) => interpolateRdBu(1 - t);

interface Hover {
  m: MonthValue;
  x: number;
  y: number;
}

/**
 * Year x month heatmap of harmonized hotspot counts in the AOI (FR-W-07, FR-W-08), with a
 * per-cell tooltip (FR-W-09) and an anomaly view coloured by % above/below the median of
 * the same calendar month (FR-W-10).
 */
export function Calendar() {
  const { t, lang } = useT();
  const aoi = useAppStore((s) => s.aoi);
  const scale = useAppStore((s) => s.scale);
  const setScale = useAppStore((s) => s.setScale);
  const view = useAppStore((s) => s.calendarView);
  const setView = useAppStore((s) => s.setCalendarView);
  const mode = useAppStore((s) => s.mode);
  const selected = useAppStore((s) => s.selected);
  const setSelected = useAppStore((s) => s.setSelected);
  const { data, error, isFetching } = useCalendar();
  const area = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<Hover | null>(null);
  const pngFrame = usePngFrame();

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
  const cellColor = (m: MonthValue) =>
    view === 'anomaly' ? anomalyColor(m.anomaly_pct) : color(valueOf(m));
  const fmt = (v: number) => formatCount(v, lang);

  // PNG export (FR-W-18): redraw the grid with the on-screen colours on a 2x canvas.
  const exportPng = async () => {
    if (!data) return;
    const cells = data.months.map((m) => ({ year: m.year, month: m.month, color: cellColor(m) }));
    const layout = calendarLayout(new Set(cells.map((c) => c.year)).size);
    const unit =
      view === 'anomaly'
        ? t('calendar.anomalyUnit', {
            start: data.reference_years[0],
            end: data.reference_years[1],
          })
        : t(mode === 'raw' ? 'calendar.unitRaw' : 'calendar.unit');
    const { frame, filename } = pngFrame(
      view === 'anomaly'
        ? `${t('panel.calendar')} · ${t('calendar.anomaly')}`
        : t('panel.calendar'),
      data,
      view === 'anomaly' ? 'calendar-anomaly' : 'calendar',
    );
    await exportFramedPng(
      frame,
      {
        width: layout.width,
        height: layout.height + 22,
        draw: (ctx) => {
          drawCalendar(ctx, cells, months);
          ctx.fillStyle = '#9aa6c8';
          ctx.font = `11px ${FONT_BODY}`;
          ctx.fillText(unit, 0, layout.height + 16);
        },
      },
      filename,
    );
  };

  const actions = (
    <>
      <div className="segmented" role="group" aria-label={t('calendar.view')}>
        {(['count', 'anomaly'] as const).map((v) => (
          <button
            key={v}
            type="button"
            className="btn btn--small"
            aria-pressed={view === v}
            onClick={() => setView(v)}
          >
            {t(v === 'count' ? 'calendar.count' : 'calendar.anomaly')}
          </button>
        ))}
      </div>
      {view === 'count' && (
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
      )}
      {data && <PngButton label={t('png.calendar')} onExport={exportPng} />}
    </>
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
      value: fmt(valueOf(m)),
    }) +
    (m.anomaly_pct === null ? '' : `, ${formatPct(m.anomaly_pct, lang)} ${t('tip.vsMedianShort')}`);

  const show = (m: MonthValue) => (e: MouseEvent<HTMLElement> | FocusEvent<HTMLElement>) => {
    const box = area.current?.getBoundingClientRect();
    const cell = e.currentTarget.getBoundingClientRect();
    if (!box) return;
    setHover({ m, x: cell.left - box.left + cell.width / 2, y: cell.top - box.top });
  };

  return (
    <Panel title={t('panel.calendar')} id="calendar" actions={actions}>
      {error && (
        <p className="form-error" role="alert">
          {(error as Error).message}
        </p>
      )}
      {!grid && !error && <div className="skeleton skeleton--calendar" aria-busy="true" />}
      {grid && (
        <div className="calendar-area" ref={area}>
          <div className={`calendar-wrap ${isFetching ? 'is-stale' : ''}`} aria-busy={isFetching}>
            <div
              className="calendar"
              role="grid"
              aria-label={t('calendar.aria', { start: data!.start, end: data!.end })}
              aria-rowcount={grid.length + 1}
              onMouseLeave={() => setHover(null)}
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
                        style={{ background: cellColor(m) }}
                        aria-label={label(m)}
                        aria-selected={selected?.year === m.year && selected.month === m.month}
                        aria-describedby={hover?.m === m ? 'calendar-tooltip' : undefined}
                        onMouseEnter={show(m)}
                        onFocus={show(m)}
                        onBlur={() => setHover(null)}
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
          {hover && <CellTooltip hover={hover} longMonths={longMonths} lang={lang} t={t} />}
        </div>
      )}
      {grid && view === 'count' && (
        <div className="legend" aria-label={t('calendar.legend')}>
          <div className="legend__bar" style={{ background: gradient(countColor) }} />
          <div className="legend__ticks">
            <span>{scale === 'log' ? '1' : '0'}</span>
            <span>{fmt(scale === 'log' ? Math.sqrt(Math.max(max, 1)) : max / 2)}</span>
            <span>{fmt(max)}</span>
          </div>
          <p className="muted small">
            {t(mode === 'raw' ? 'calendar.unitRaw' : 'calendar.unit')}
            {data!.months.some((m) => m.provisional) && <> · {t('calendar.nrtNote')}</>}
          </p>
        </div>
      )}
      {grid && view === 'anomaly' && (
        <div className="legend" aria-label={t('calendar.legend')}>
          <div className="legend__bar" style={{ background: gradient(anomalyRamp) }} />
          <div className="legend__ticks">
            <span>−100%</span>
            <span>±0</span>
            <span>+100%</span>
          </div>
          <p className="muted small">
            {t('calendar.anomalyUnit', {
              start: data!.reference_years[0],
              end: data!.reference_years[1],
            })}
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
                      <td key={i}>
                        {m
                          ? view === 'anomaly'
                            ? formatPct(m.anomaly_pct, lang)
                            : fmt(valueOf(m))
                          : ''}
                      </td>
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

function CellTooltip({
  hover,
  longMonths,
  lang,
  t,
}: {
  hover: Hover;
  longMonths: string[];
  lang: string;
  t: ReturnType<typeof useT>['t'];
}) {
  const { m } = hover;
  const fmt = (v: number) => formatCount(v, lang);
  return (
    <div
      id="calendar-tooltip"
      className="cal-tooltip"
      role="tooltip"
      style={{ left: hover.x, top: hover.y }}
    >
      <strong>
        {longMonths[m.month - 1]} {m.year}
      </strong>
      <dl>
        <dt>{t('tip.harmonized')}</dt>
        <dd>{fmt(m.value)}</dd>
        <dt>{t('tip.ci')}</dt>
        <dd>
          {fmt(m.ci_low)}–{fmt(m.ci_high)}
        </dd>
        <dt>MODIS</dt>
        <dd>{fmt(m.n_modis)}</dd>
        <dt>VIIRS</dt>
        <dd>{fmt(m.n_viirs)}</dd>
        <dt>{t('tip.anomaly')}</dt>
        <dd>
          {formatPct(m.anomaly_pct, lang)}
          {m.median !== null && (
            <span className="muted"> ({t('tip.vsMedian', { median: fmt(m.median) })})</span>
          )}
        </dd>
        <dt>{t('tip.percentile')}</dt>
        <dd>{m.percentile === null ? '–' : `P${Math.round(m.percentile)}`}</dd>
      </dl>
      <small>
        {t('tip.source', { source: m.source })}
        {m.provisional && <> · {t('status.provisional')}</>}
      </small>
    </div>
  );
}
