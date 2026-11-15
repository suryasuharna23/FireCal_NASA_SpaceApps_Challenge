import type { Polygon, MultiPolygon } from 'geojson';
import type {
  CalendarView,
  ColorScale,
  MapDisplay,
  DataScope,
  ViewMode,
  YearMonth,
} from '../state/useAppStore';
import { areaKm2, type Aoi, type AoiKind } from './aoi';
import { circleAoi } from './circle';

/** The part of the app state that is shareable through the URL (FR-W-19, US-08). */
export interface ShareState {
  scope?: DataScope;
  aoi: Aoi | null;
  start: string | null;
  end: string | null;
  referenceYears: [number, number] | null;
  selected: YearMonth | null;
  mode: ViewMode;
  scale: ColorScale;
  calendarView: CalendarView;
  mapDisplay: MapDisplay;
}

const MONTH = /^\d{4}-(0[1-9]|1[0-2])$/;
const round = (v: number) => Math.round(v * 1e4) / 1e4;

function toBase64Url(text: string): string {
  return btoa(text).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function fromBase64Url(text: string): string {
  const b64 = text.replace(/-/g, '+').replace(/_/g, '/');
  return atob(b64 + '='.repeat((4 - (b64.length % 4)) % 4));
}

/** Compact polygon encoding: coordinates rounded to ~10 m, JSON, base64url. */
export function encodeGeometry(geometry: Polygon | MultiPolygon): string {
  const coords =
    geometry.type === 'Polygon'
      ? geometry.coordinates.map((ring) => ring.map(([x, y]) => [round(x!), round(y!)]))
      : geometry.coordinates.map((poly) =>
          poly.map((ring) => ring.map(([x, y]) => [round(x!), round(y!)])),
        );
  return toBase64Url(JSON.stringify({ t: geometry.type === 'Polygon' ? 'P' : 'M', c: coords }));
}

export function decodeGeometry(text: string): Polygon | MultiPolygon | null {
  try {
    const { t, c } = JSON.parse(fromBase64Url(text));
    if (!Array.isArray(c)) return null;
    return t === 'M'
      ? { type: 'MultiPolygon', coordinates: c }
      : { type: 'Polygon', coordinates: c };
  } catch {
    return null;
  }
}

/** State -> query string. Defaults are omitted to keep links short. */
export function encodeState(s: ShareState): URLSearchParams {
  const p = new URLSearchParams();
  if (s.scope === 'global') p.set('scope', 'global');
  const a = s.aoi;
  if (a) {
    if (a.kind === 'region' && a.regionId) {
      p.set('region', a.regionId);
    } else if (a.circle && (a.kind === 'circle' || a.kind === 'globe')) {
      p.set('circle', `${a.circle.lat},${a.circle.lon},${a.circle.radiusKm}`);
      if (a.kind === 'globe') p.set('k', 'globe');
    } else {
      p.set('aoi', encodeGeometry(a.geometry));
      p.set('k', a.kind);
      if (a.regionId) p.set('rid', a.regionId);
    }
    if (a.label && !p.has('region')) p.set('label', a.label);
  }
  if (s.start) p.set('start', s.start);
  if (s.end) p.set('end', s.end);
  if (s.referenceYears) p.set('ref', s.referenceYears.join('-'));
  if (s.selected) p.set('month', `${s.selected.year}-${String(s.selected.month).padStart(2, '0')}`);
  if (s.mode !== 'harmonized') p.set('mode', s.mode);
  if (s.scale !== 'linear') p.set('scale', s.scale);
  if (s.calendarView !== 'count') p.set('view', s.calendarView);
  if (s.mapDisplay !== 'points') p.set('map', s.mapDisplay);
  return p;
}

/** Query string -> state; invalid values are ignored rather than breaking the app. */
export function decodeState(p: URLSearchParams): Partial<ShareState> {
  const out: Partial<ShareState> = {};
  if (p.get('scope') === 'global') {
    out.scope = 'global';
    out.mode = 'raw';
  }
  const label = p.get('label') ?? undefined;
  if (p.get('circle')) {
    const [lat, lon, r] = p.get('circle')!.split(',').map(Number);
    if (
      [lat, lon, r].every(Number.isFinite) &&
      Math.abs(lat!) <= 90 &&
      Math.abs(lon!) <= 180 &&
      r! > 0
    ) {
      out.aoi = circleAoi(lat!, lon!, r!, label, p.get('k') === 'globe' ? 'globe' : 'circle');
    }
  } else if (p.get('aoi')) {
    const geometry = decodeGeometry(p.get('aoi')!);
    if (geometry) {
      const kind = (['draw', 'region', 'upload', 'globe'] as AoiKind[]).includes(
        p.get('k') as AoiKind,
      )
        ? (p.get('k') as AoiKind)
        : 'draw';
      out.aoi = {
        kind,
        geometry,
        areaKm2: areaKm2(geometry),
        label,
        ...(p.get('rid') ? { regionId: p.get('rid')! } : {}),
      };
    }
  }
  if (MONTH.test(p.get('start') ?? '')) out.start = p.get('start');
  if (MONTH.test(p.get('end') ?? '')) out.end = p.get('end');
  const ref = p.get('ref')?.split('-').map(Number);
  if (ref?.length === 2 && ref.every(Number.isInteger) && ref[0]! <= ref[1]!) {
    out.referenceYears = [ref[0]!, ref[1]!];
  }
  if (MONTH.test(p.get('month') ?? '')) {
    const [year, month] = p.get('month')!.split('-').map(Number);
    out.selected = { year: year!, month: month! };
  }
  if (p.get('mode') === 'raw') out.mode = 'raw';
  if (p.get('scale') === 'log') out.scale = 'log';
  if (p.get('view') === 'anomaly') out.calendarView = 'anomaly';
  if (p.get('map') === 'heatmap') out.mapDisplay = 'heatmap';
  return out;
}
