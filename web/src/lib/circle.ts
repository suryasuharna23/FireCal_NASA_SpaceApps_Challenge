import { circle as turfCircle } from '@turf/circle';
import type { MessageKey } from '../i18n';
import { areaKm2, type Aoi } from './aoi';

export type CircleErrors = Partial<Record<'lat' | 'lon' | 'radius', MessageKey>>;

/** Largest radius whose circle stays within ``maxKm2``. */
export function maxRadiusKm(maxKm2: number): number {
  return Math.sqrt(maxKm2 / Math.PI);
}

function parse(value: string): number {
  const normalized = value.trim().replace(',', '.').replace('−', '-');
  return normalized === '' ? Number.NaN : Number(normalized);
}

export function validateCircle(
  input: { lat: string; lon: string; radius: string },
  maxKm2: number,
): { errors: CircleErrors; value?: { lat: number; lon: number; radiusKm: number } } {
  const lat = parse(input.lat);
  const lon = parse(input.lon);
  const radiusKm = parse(input.radius);
  const errors: CircleErrors = {};
  if (!Number.isFinite(lat) || lat < -90 || lat > 90) errors.lat = 'circle.err.lat';
  if (!Number.isFinite(lon) || lon < -180 || lon > 180) errors.lon = 'circle.err.lon';
  if (!Number.isFinite(radiusKm) || radiusKm < 1) errors.radius = 'circle.err.radius';
  else if (radiusKm > maxRadiusKm(maxKm2)) errors.radius = 'circle.err.radiusMax';
  return Object.keys(errors).length ? { errors } : { errors, value: { lat, lon, radiusKm } };
}

export function circleAoi(
  lat: number,
  lon: number,
  radiusKm: number,
  label?: string,
  kind: Aoi['kind'] = 'circle',
  regionId?: string,
): Aoi {
  const geometry = turfCircle([lon, lat], radiusKm, { units: 'kilometers', steps: 72 }).geometry;
  return {
    kind,
    geometry,
    areaKm2: areaKm2(geometry),
    label,
    circle: { lat, lon, radiusKm },
    ...(regionId ? { regionId } : {}),
  };
}
