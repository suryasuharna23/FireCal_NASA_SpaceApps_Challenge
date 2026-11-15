import { interpolateRdBu, interpolateRgb, scaleLinear, scaleSequential, scaleSequentialLog } from 'd3';
import type { ColorScale } from '../state/useAppStore';

/**
 * Sequential Solar Flare palette for fire detections & heatmap intensity:
 * Sourced directly from FireCal Design Tokens (design-system/tokens.json):
 * - Zero: #12162B (Zero cell / no thermal anomaly)
 * - Low:  #4A2612 (1 - 50 detections)
 * - Mid:  #8A380A (50 - 200 detections)
 * - Ember: #E04006 (Thermal peak)
 * - Orange: #FF6B1A (High outbreak / Primary CTA)
 * - Amber: #FF9F1C (Warm flame)
 * - Peak: #FFD23F (500+ detections / Solar glow peak)
 *
 * Ordered in lightness and verified for accessibility under protanopia & deuteranopia (NFR-04).
 */
export const ZERO_COLOR = 'var(--zero-cell)';

const FIRE_PALETTE = ['#4A2612', '#8A380A', '#E04006', '#FF6B1A', '#FF9F1C', '#FFD23F'];
const fireScale = scaleLinear<string>()
  .domain([0, 0.2, 0.4, 0.65, 0.85, 1])
  .range(FIRE_PALETTE)
  .interpolate(interpolateRgb);

export const countColor = (t: number) => fireScale(Math.max(0, Math.min(1, t)));

export function countScale(max: number, scale: ColorScale) {
  const top = Math.max(max, 1);
  if (scale === 'log') {
    const s = scaleSequentialLog(countColor).domain([1, top + 1]);
    return (v: number) => (v <= 0 ? ZERO_COLOR : s(v + 1));
  }
  const s = scaleSequential(countColor).domain([0, top]);
  return (v: number) => (v <= 0 ? ZERO_COLOR : s(Math.max(v, top * 0.04)));
}

/**
 * Diverging palette for anomalies (FR-W-10): blue = below median, red = above.
 * RdBu is colour-blind safe; the domain is clipped at +/-100 %.
 */
export function anomalyScale(limit = 100) {
  return (pct: number | null) => {
    if (pct === null || !Number.isFinite(pct)) return ZERO_COLOR;
    const t = Math.max(-1, Math.min(1, pct / limit));
    return interpolateRdBu(0.5 - t / 2);
  };
}

/** Sampled CSS gradient for legends. */
export function gradient(color: (t: number) => string, stops = 9): string {
  const parts = Array.from({ length: stops }, (_, i) => color(i / (stops - 1)));
  return `linear-gradient(to right, ${parts.join(', ')})`;
}

export function formatCount(v: number, lang: string): string {
  const locale = lang;
  if (v >= 100) return Math.round(v).toLocaleString(locale);
  return v.toLocaleString(locale, { maximumFractionDigits: 1 });
}

/** Signed percentage such as "+12%" or "−8%" ("–" when unknown). */
export function formatPct(v: number | null, lang: string): string {
  if (v === null || !Number.isFinite(v)) return '–';
  const abs = Math.abs(v).toLocaleString(lang, { maximumFractionDigits: 0 });
  return `${v > 0 ? '+' : v < 0 ? '−' : '±'}${abs}%`;
}
