/// <reference types="node" />
import { readFileSync } from 'node:fs';
import { anomalyScale, countColor } from './colors';
import { contrast, luminance, over, simulate, type Deficiency } from './contrast';
import { SENSOR_COLORS } from './points';

/** Read a CSS custom property from the theme so the test follows the real stylesheet. */
// Vitest runs from the web/ root.
const css = readFileSync(`${process.cwd()}/src/index.css`, 'utf8');
const token = (name: string) => css.match(new RegExp(`--${name}:\\s*([^;]+);`))![1]!.trim();

// Panels are translucent over the page background; test against the composite.
const PANEL = over('#0e1428', 0.78, token('bg'));
const AA_TEXT = 4.5;
const AA_UI = 3;

describe('WCAG 2.1 AA contrast (NFR-03)', () => {
  it.each([
    ['body text on panel', token('fg'), PANEL, AA_TEXT],
    ['muted text on panel', token('muted'), PANEL, AA_TEXT],
    ['muted text on page', token('muted'), token('bg'), AA_TEXT],
    ['primary button text', token('accent-fg'), token('accent'), AA_TEXT],
    ['warning text', token('warn-fg'), over('#facc15', 0.14, '#0e1428'), AA_TEXT],
    ['error text', token('error-fg'), over('#f87171', 0.16, '#0e1428'), AA_TEXT],
    ['focus ring vs page', token('focus'), token('bg'), AA_UI],
    ['orbit accent vs panel', token('orbit'), PANEL, AA_UI],
  ])('%s ≥ %s:1', (_name, fg, bg, min) => {
    expect(contrast(fg as string, bg as never)).toBeGreaterThanOrEqual(min as number);
  });

  it('the calculator matches the WCAG reference values', () => {
    expect(contrast('#000000', '#ffffff')).toBeCloseTo(21, 1);
    expect(contrast('#777777', '#ffffff')).toBeCloseTo(4.48, 1);
  });
});

describe('colour-vision deficiency simulation (NFR-04)', () => {
  const kinds: Deficiency[] = ['deuteranopia', 'protanopia'];
  const stops = Array.from({ length: 9 }, (_, i) => countColor(i / 8));

  it.each(kinds)('the calendar ramp stays ordered in lightness with %s', (kind) => {
    const lum = stops.map((c) => luminance(simulate(c, kind)));
    for (let i = 1; i < lum.length; i++) expect(lum[i]).toBeGreaterThan(lum[i - 1]!);
    // lowest and highest counts remain clearly distinguishable
    expect(contrast(simulate(stops[0]!, kind), simulate(stops[8]!, kind))).toBeGreaterThan(5);
  });

  it.each(kinds)('anomaly blue and red stay distinguishable with %s', (kind) => {
    const color = anomalyScale(100);
    const below = simulate(color(-80), kind);
    const above = simulate(color(80), kind);
    // A diverging palette is symmetric in lightness by design; for red-green deficiencies
    // RdBu keeps a blue vs yellow-brown opposition, so the blue channel separates them.
    expect(Math.abs(below[2] - above[2])).toBeGreaterThan(60);
    // ...and each side stays clearly apart from the neutral midpoint.
    const mid = simulate(color(0), kind);
    expect(contrast(below, mid)).toBeGreaterThan(1.5);
    expect(contrast(above, mid)).toBeGreaterThan(1.5);
  });

  it.each(kinds)('MODIS and VIIRS point colours stay distinguishable with %s', (kind) => {
    const m = simulate(SENSOR_COLORS.MODIS, kind);
    const v = simulate(SENSOR_COLORS.VIIRS, kind);
    expect(Math.abs(m[2] - v[2])).toBeGreaterThan(60);
  });
});
