import { statsFixture } from '../test/fixtures';
import { climatologyOption, monthRuns } from './climatology';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
type Series = { name: string; data: (number | null)[]; markArea?: { data: unknown[] } };

describe('climatology chart', () => {
  it('merges contiguous critical months into runs', () => {
    expect(monthRuns([10, 8, 9, 2])).toEqual([
      [2, 2],
      [8, 10],
    ]);
    expect(monthRuns([])).toEqual([]);
  });

  it('builds a P25-P75 band, median, current year and a fire-season area', () => {
    const option = climatologyOption(statsFixture(), {
      months: MONTHS,
      median: 'Median',
      band: 'P25–P75',
      current: '2021',
      season: 'Fire season',
      format: (v) => String(v),
    }) as unknown as { series: Series[]; tooltip: { formatter: (p: unknown) => string } };
    const [base, band, median, current] = option.series;
    expect(base!.data[8]).toBe(150); // P25 in September
    expect(band!.data[8]).toBe(110); // P75 - P25
    expect(median!.data[8]).toBe(200);
    expect(current!.data[8]).toBe(260);
    expect(median!.markArea!.data).toEqual([
      [{ xAxis: 'Aug', name: 'Fire season' }, { xAxis: 'Oct' }],
    ]);
    const tip = option.tooltip.formatter([{ dataIndex: 8 }]);
    expect(tip).toContain('Median: 200');
    expect(tip).toContain('P25–P75: 150–260');
    expect(tip).toContain('Fire season');
  });
});
