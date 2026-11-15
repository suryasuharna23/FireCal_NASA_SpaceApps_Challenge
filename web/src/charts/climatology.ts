import type { StatsResponse } from '../api/queries';
import { baseOption, THEME, type EChartsOption } from './echarts';

/** Contiguous runs of critical months, e.g. [8, 9, 10] -> [[8, 10]]. */
export function monthRuns(months: number[]): [number, number][] {
  const sorted = [...new Set(months)].sort((a, b) => a - b);
  const runs: [number, number][] = [];
  for (const m of sorted) {
    const last = runs[runs.length - 1];
    if (last && m === last[1] + 1) last[1] = m;
    else runs.push([m, m]);
  }
  return runs;
}

export interface ClimatologyLabels {
  months: string[];
  median: string;
  band: string;
  season: string;
  year: (year: number, partial: boolean) => string;
  format: (v: number | null) => string;
}

export interface YearProfile {
  year: number;
  values: (number | null)[];
  partial: boolean;
}

export interface ClimatologyView {
  years: YearProfile[];
  showBand: boolean;
  showSeason: boolean;
}

/**
 * Monthly climatology (FR-W-12, FR-W-14): median and P25–P75 band over the reference
 * years, up to two chosen years on top, and optional critical months as shaded bands.
 * The band is drawn as a stacked area: an invisible P25 base plus (P75 − P25).
 */
export function climatologyOption(
  stats: StatsResponse,
  labels: ClimatologyLabels,
  view: ClimatologyView,
): EChartsOption {
  const c = stats.climatology;
  const p25 = c.map((m) => m.p25 ?? 0);
  const width = c.map((m) => Math.max((m.p75 ?? 0) - (m.p25 ?? 0), 0));
  const areas = monthRuns(stats.critical_months).map(([a, b]) => [
    { xAxis: labels.months[a - 1], name: labels.season },
    { xAxis: labels.months[b - 1] },
  ]);
  return {
    ...baseOption,
    grid: { ...baseOption.grid, top: view.years.length > 1 ? 56 : 40 },
    legend: {
      ...baseOption.legend,
      data: [
        labels.median,
        ...(view.showBand ? [labels.band] : []),
        ...view.years.map((y) => labels.year(y.year, y.partial)),
      ],
    },
    tooltip: {
      ...baseOption.tooltip,
      formatter: (params: unknown) => {
        const i = (params as { dataIndex: number }[])[0]?.dataIndex ?? 0;
        const m = c[i]!;
        const f = labels.format;
        return [
          `<b>${labels.months[i]}</b>`,
          `${labels.median}: ${f(m.median)}`,
          view.showBand ? `${labels.band}: ${f(m.p25)}–${f(m.p75)}` : '',
          ...view.years.map(
            (year) => `${labels.year(year.year, year.partial)}: ${f(year.values[i] ?? null)}`,
          ),
          view.showSeason && m.critical
            ? `<span style="color:#ffb08a">${labels.season}</span>`
            : '',
        ]
          .filter(Boolean)
          .join('<br/>');
      },
    },
    xAxis: {
      type: 'category',
      data: labels.months,
      boundaryGap: false,
      axisLine: { lineStyle: { color: THEME.grid } },
      axisLabel: { color: THEME.text },
    },
    yAxis: {
      type: 'value',
      min: 0,
      splitLine: { lineStyle: { color: THEME.grid } },
      axisLabel: { color: THEME.text },
    },
    series: [
      ...(view.showBand
        ? [
            {
              name: 'p25-base',
              type: 'line',
              stack: 'band',
              data: p25,
              symbol: 'none',
              lineStyle: { opacity: 0 },
              tooltip: { show: false },
              silent: true,
            },
            {
              name: labels.band,
              type: 'line',
              stack: 'band',
              data: width,
              symbol: 'none',
              lineStyle: { opacity: 0 },
              areaStyle: { color: THEME.band },
              itemStyle: { color: THEME.amber },
            },
          ]
        : []),
      {
        name: labels.median,
        type: 'line',
        data: c.map((m) => m.median),
        smooth: false,
        symbolSize: 5,
        lineStyle: { width: 2.5, color: THEME.amber },
        itemStyle: { color: THEME.amber },
        markArea: view.showSeason
          ? {
              silent: true,
              itemStyle: { color: THEME.critical },
              label: { color: '#ffb08a', fontSize: 11, position: 'insideTop' },
              data: areas,
            }
          : undefined,
      },
      ...view.years.map((year, index) => ({
        name: labels.year(year.year, year.partial),
        type: 'line',
        data: year.values,
        smooth: false,
        connectNulls: false,
        symbolSize: 6,
        lineStyle: {
          width: 2,
          color: index === 0 ? THEME.orbit : THEME.fire,
          type: index === 0 ? 'dashed' : 'solid',
        },
        itemStyle: { color: index === 0 ? THEME.orbit : THEME.fire },
      })),
    ],
  };
}
