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
  current: string;
  season: string;
  format: (v: number | null) => string;
}

/**
 * Monthly climatology (FR-W-12, FR-W-14): median and P25–P75 band over the reference
 * years, the last year of the range on top, and critical months as shaded bands.
 * The band is drawn as a stacked area: an invisible P25 base plus (P75 − P25).
 */
export function climatologyOption(stats: StatsResponse, labels: ClimatologyLabels): EChartsOption {
  const c = stats.climatology;
  const p25 = c.map((m) => m.p25 ?? 0);
  const width = c.map((m) => Math.max((m.p75 ?? 0) - (m.p25 ?? 0), 0));
  const areas = monthRuns(stats.critical_months).map(([a, b]) => [
    { xAxis: labels.months[a - 1], name: labels.season },
    { xAxis: labels.months[b - 1] },
  ]);
  return {
    ...baseOption,
    legend: {
      ...baseOption.legend,
      data: [labels.median, labels.band, labels.current],
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
          `${labels.band}: ${f(m.p25)}–${f(m.p75)}`,
          `${labels.current}: ${f(m.current)}`,
          m.critical ? `<span style="color:${THEME.amber}">${labels.season}</span>` : '',
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
      {
        name: labels.median,
        type: 'line',
        data: c.map((m) => m.median),
        smooth: true,
        symbolSize: 5,
        lineStyle: { width: 2.5, color: THEME.amber },
        itemStyle: { color: THEME.amber },
        markArea: {
          silent: true,
          itemStyle: { color: THEME.critical },
          label: { color: THEME.amber, fontSize: 11, position: 'insideTop' },
          data: areas,
        },
      },
      {
        name: labels.current,
        type: 'line',
        data: c.map((m) => m.current),
        smooth: true,
        symbolSize: 6,
        lineStyle: { width: 2, color: THEME.orbit, type: 'dashed' },
        itemStyle: { color: THEME.orbit },
      },
    ],
  };
}
