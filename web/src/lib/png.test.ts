import { calendarLayout, canvasColor, drawCalendar, EXPORT_SCALE, frameSize } from './png';

describe('PNG export helpers', () => {
  it('exports at least 2x and frames the body with header and footer', () => {
    expect(EXPORT_SCALE).toBeGreaterThanOrEqual(2);
    const f = frameSize(400, 300);
    expect(f.width).toBeGreaterThan(400);
    expect(f.height).toBeGreaterThan(300);
  });

  it('maps CSS variables to canvas colours', () => {
    expect(canvasColor('var(--zero-cell)')).toMatch(/^#/);
    expect(canvasColor('rgb(1, 2, 3)')).toBe('rgb(1, 2, 3)');
  });

  it('draws one rectangle per month at the grid position', () => {
    const rects: [number, number, number, number, string][] = [];
    const fake = {
      fillStyle: '',
      font: '',
      textAlign: 'left',
      fillText: vi.fn(),
      fillRect: (x: number, y: number, w: number, h: number) => {
        rects.push([x, y, w, h, fake.fillStyle]);
      },
    };
    const ctx = fake as unknown as CanvasRenderingContext2D;
    drawCalendar(
      ctx,
      [
        { year: 2020, month: 1, color: 'red' },
        { year: 2021, month: 12, color: 'var(--zero-cell)' },
      ],
      ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'],
    );
    const L = calendarLayout(2);
    expect(rects[0]).toEqual([L.label, L.header, L.cellW, L.cellH, 'red']);
    expect(rects[1]![0]).toBe(L.label + 11 * (L.cellW + L.gap));
    expect(rects[1]![1]).toBe(L.header + L.cellH + L.gap);
    expect(rects[1]![4]).toMatch(/^#/);
  });
});
