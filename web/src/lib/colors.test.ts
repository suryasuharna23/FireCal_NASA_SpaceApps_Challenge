import { anomalyScale } from './colors';

describe('anomalyScale', () => {
  it('is blue below the median, red above and neutral for missing values', () => {
    const color = anomalyScale(100);
    const rgb = (c: string) => c.match(/\d+/g)!.map(Number);
    const [rLow, , bLow] = rgb(color(-80));
    const [rHigh, , bHigh] = rgb(color(80));
    expect(bLow).toBeGreaterThan(rLow!);
    expect(rHigh).toBeGreaterThan(bHigh!);
    expect(color(null)).toBe('var(--zero-cell)');
  });
});
