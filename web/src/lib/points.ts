import { countColor } from './colors';

export type PointsColor = 'sensor' | 'frp';

export const SENSOR_COLORS = { MODIS: '#ffb347', VIIRS: '#5ee7ff' } as const;

/** FRP (MW) stops for the colour ramp; most detections are below 50 MW. */
export const FRP_STOPS = [0, 5, 15, 40, 100, 300];

/** MapLibre circle colour for raw detections or aggregated cells (FR-W-15). */
export function pointColorExpression(by: PointsColor): unknown[] {
  if (by === 'frp') {
    const stops: (number | string)[] = [];
    FRP_STOPS.forEach((v, i) =>
      stops.push(v, countColor(0.2 + (0.8 * i) / (FRP_STOPS.length - 1))),
    );
    return ['interpolate', ['linear'], ['coalesce', ['get', 'frp'], 0], ...stops];
  }
  return [
    'case',
    ['has', 'count'],
    '#ff7a3d',
    [
      'match',
      ['get', 'sensor'],
      'MODIS',
      SENSOR_COLORS.MODIS,
      'VIIRS',
      SENSOR_COLORS.VIIRS,
      '#ffffff',
    ],
  ];
}

/**
 * Raw points grow gently with zoom; aggregated cells scale with their count.
 * MapLibre only allows `zoom` at the top level, so the zoom ramp wraps the per-feature
 * `case` instead of the other way round.
 */
export function pointRadiusExpression(): unknown[] {
  const cell = (scale: number) => [
    '*',
    scale,
    ['interpolate', ['linear'], ['sqrt', ['get', 'count']], 1, 3, 30, 14],
  ];
  const at = (rawRadius: number, cellScale: number) => [
    'case',
    ['has', 'count'],
    cell(cellScale),
    rawRadius,
  ];
  return ['interpolate', ['linear'], ['zoom'], 3, at(2, 0.6), 7, at(3.5, 1), 11, at(6, 1.4)];
}

const escape = (v: unknown) => String(v ?? '–').replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);

/** Popup body for one detection or aggregated cell. */
export function pointPopupHtml(
  props: Record<string, unknown>,
  labels: Record<'detections' | 'frp' | 'confidence' | 'time' | 'weight', string>,
): string {
  if ('count' in props) {
    return `<strong>${escape(props.count)} ${escape(labels.detections)}</strong><br/>MODIS ${escape(
      props.modis,
    )} · VIIRS ${escape(props.viirs)}<br/>${escape(labels.frp)} ${escape(props.frp)} MW`;
  }
  return [
    `<strong>${escape(props.sensor)} · ${escape(props.satellite)}</strong>`,
    `${escape(labels.time)}: ${escape(props.time)}`,
    `${escape(labels.frp)}: ${escape(props.frp)} MW`,
    `${escape(labels.confidence)}: ${escape(props.confidence)}`,
    `${escape(labels.weight)}: ${escape(props.weight)}`,
  ].join('<br/>');
}
