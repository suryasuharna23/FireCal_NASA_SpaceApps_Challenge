import type { FeatureCollection, Point } from 'geojson';
import { countColor } from './colors';

/** Hotspot cells -> GeoJSON points with value ``v`` and normalized intensity ``t`` (0..1). */
export function cellsToGeoJSON(
  cells: [number, number, number][],
  max: number,
): FeatureCollection<Point, { v: number; t: number }> {
  const top = Math.max(max, 1);
  return {
    type: 'FeatureCollection',
    features: cells.map(([lon, lat, v]) => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [lon, lat] },
      properties: { v, t: Math.sqrt(v / top) },
    })),
  };
}

/** MapLibre colour ramp matching the calendar's inferno palette. */
export function intensityColorExpression(): unknown[] {
  const stops: (number | string)[] = [];
  for (let i = 0; i <= 6; i++) {
    const t = i / 6;
    stops.push(t, countColor(0.25 + 0.75 * t));
  }
  return ['interpolate', ['linear'], ['get', 't'], ...stops];
}

/** Circle radius grows with intensity and zoom so hotspots stay legible from orbit. */
export function radiusExpression(scale = 1): unknown[] {
  return [
    'interpolate',
    ['linear'],
    ['zoom'],
    0,
    ['*', scale, ['+', 1, ['*', 3, ['get', 't']]]],
    3,
    ['*', scale, ['+', 2, ['*', 6, ['get', 't']]]],
    7,
    ['*', scale, ['+', 4, ['*', 14, ['get', 't']]]],
  ];
}

export function prefersReducedMotion(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );
}

/** Degrees of longitude per second for the idle spin at a given zoom (0 when zoomed in). */
export function spinSpeed(zoom: number): number {
  if (zoom >= 3.5) return 0;
  return 6 * (1 - zoom / 3.5) + 1.5;
}
