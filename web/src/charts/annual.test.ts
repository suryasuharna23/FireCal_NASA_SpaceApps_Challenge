import { statsFixture } from '../test/fixtures';
import { annualOption } from './annual';

type Bar = {
  value: number;
  itemStyle: { color: string; opacity: number };
  label?: { formatter: string };
};

describe('annual totals chart', () => {
  it('orders bars by year, colours them by rank and labels the highest year', () => {
    const annual = statsFixture().annual;
    annual[2] = { ...annual[2]!, complete: false };
    const option = annualOption(annual, {
      total: 'Total',
      rank: (r, n) => `Rank ${r} of ${n}`,
      partial: 'Incomplete year',
      format: (v) => String(v),
    }) as unknown as {
      xAxis: { data: string[] };
      series: { data: Bar[] }[];
      tooltip: { formatter: (p: unknown) => string };
    };
    expect(option.xAxis.data).toEqual(['2019', '2020', '2021']);
    const bars = option.series[0]!.data;
    expect(bars.map((b) => b.value)).toEqual([1800, 900, 1200]);
    expect(bars[0]!.label?.formatter).toBe('#1 1800');
    expect(bars[1]!.label).toBeUndefined();
    expect(bars[0]!.itemStyle.color).not.toBe(bars[1]!.itemStyle.color);
    expect(bars[2]!.itemStyle.opacity).toBeLessThan(1);
    const tip = option.tooltip.formatter([{ dataIndex: 2 }]);
    expect(tip).toContain('Rank 2 of 3');
    expect(tip).toContain('Incomplete year');
  });
});
