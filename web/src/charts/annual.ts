import type { StatsResponse } from '../api/queries';
import { countColor } from '../lib/colors';
import { baseOption, THEME, type EChartsOption } from './echarts';

export interface AnnualLabels {
  total: string;
  rank: (rank: number, of: number) => string;
  partial: string;
  format: (v: number) => string;
}

/**
 * Annual totals with rank (FR-W-13). Bars use the calendar's inferno ramp by rank so the
 * worst years glow; the highest year is labelled, incomplete years are hatched lighter.
 */
export function annualOption(annual: StatsResponse['annual'], labels: AnnualLabels): EChartsOption {
  const n = annual.length;
  const top = annual.reduce((best, a) => (a.rank < best.rank ? a : best), annual[0]!);
  return {
    ...baseOption,
    legend: { show: false },
    grid: { ...baseOption.grid, top: 24, bottom: 36 },
    tooltip: {
      ...baseOption.tooltip,
      formatter: (params: unknown) => {
        const i = (params as { dataIndex: number }[])[0]?.dataIndex ?? 0;
        const a = annual[i]!;
        return [
          `<b>${a.year}</b>`,
          `${labels.total}: ${labels.format(a.total)}`,
          labels.rank(a.rank, n),
          a.complete ? '' : `<span style="color:#9aa6c8">${labels.partial}</span>`,
        ]
          .filter(Boolean)
          .join('<br/>');
      },
    },
    xAxis: {
      type: 'category',
      data: annual.map((a) => String(a.year)),
      axisLine: { lineStyle: { color: THEME.grid } },
      axisLabel: { color: THEME.text, interval: n > 16 ? 'auto' : 0, rotate: n > 16 ? 45 : 0 },
    },
    yAxis: {
      type: 'value',
      min: 0,
      splitLine: { lineStyle: { color: THEME.grid } },
      axisLabel: { color: THEME.text },
    },
    series: [
      {
        name: labels.total,
        type: 'bar',
        barMaxWidth: 28,
        data: annual.map((a) => ({
          value: a.total,
          itemStyle: {
            color: countColor(n > 1 ? 1 - (a.rank - 1) / (n - 1) : 1),
            opacity: a.complete ? 1 : 0.45,
            borderRadius: [3, 3, 0, 0],
          },
          label:
            a.year === top?.year
              ? {
                  show: true,
                  position: 'top',
                  color: THEME.strong,
                  formatter: `#1 ${labels.format(a.total)}`,
                }
              : undefined,
        })),
      },
    ],
  };
}
