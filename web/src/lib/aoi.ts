import { area as turfArea } from '@turf/area';
import { bbox as turfBbox } from '@turf/bbox';
import type { Feature, MultiPolygon, Polygon, Position } from 'geojson';

export type AoiGeometry = Polygon | MultiPolygon;
export type AoiKind = 'draw' | 'circle' | 'region' | 'upload' | 'globe';

export interface Aoi {
  kind: AoiKind;
  geometry: AoiGeometry;
  areaKm2: number;
  label?: string;
  circle?: { lat: number; lon: number; radiusKm: number };
  regionId?: string;
}

export const DEFAULT_MAX_AOI_KM2 = 2_000_000;

export function areaKm2(geometry: AoiGeometry): number {
  return turfArea({ type: 'Feature', properties: {}, geometry }) / 1e6;
}

export function aoiBbox(geometry: AoiGeometry): [number, number, number, number] {
  return turfBbox({ type: 'Feature', properties: {}, geometry }) as [
    number,
    number,
    number,
    number,
  ];
}

export type AoiCheck =
  | { ok: true; areaKm2: number }
  | { ok: false; reason: 'too_large' | 'empty' | 'invalid'; areaKm2: number };

/** Client-side guard mirroring the API limits (FR-W-01: max area). */
export function checkAoi(geometry: AoiGeometry | null | undefined, maxKm2: number): AoiCheck {
  if (!geometry || !['Polygon', 'MultiPolygon'].includes(geometry.type)) {
    return { ok: false, reason: 'invalid', areaKm2: 0 };
  }
  const km2 = areaKm2(geometry);
  if (!Number.isFinite(km2) || km2 <= 0) return { ok: false, reason: 'empty', areaKm2: 0 };
  if (km2 > maxKm2) return { ok: false, reason: 'too_large', areaKm2: km2 };
  return { ok: true, areaKm2: km2 };
}

export function toFeature(aoi: Aoi): Feature<AoiGeometry> {
  return { type: 'Feature', properties: { kind: aoi.kind }, geometry: aoi.geometry };
}

/** A dark world overlay with the selected polygon(s) cut out. */
export function outsideAoiMask(geometry: AoiGeometry): Feature<MultiPolygon> {
  const world: Position[] = [
    [-180, -85],
    [180, -85],
    [180, 85],
    [-180, 85],
    [-180, -85],
  ];
  const signedArea = (ring: Position[]) =>
    ring.reduce((sum, point, index) => {
      const next = ring[(index + 1) % ring.length]!;
      return sum + point[0]! * next[1]! - next[0]! * point[1]!;
    }, 0);
  const orient = (ring: Position[], positive: boolean) =>
    signedArea(ring) > 0 === positive ? ring : [...ring].reverse();
  const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
  const holes = polygons.map((polygon) => orient(polygon[0]!, false));
  const interiorIslands = polygons.flatMap((polygon) =>
    polygon.slice(1).map((ring) => [orient(ring, true)]),
  );
  return {
    type: 'Feature',
    properties: {},
    geometry: { type: 'MultiPolygon', coordinates: [[world, ...holes], ...interiorIslands] },
  };
}

export function formatKm2(km2: number, lang = 'en-GB'): string {
  return `${Math.round(km2).toLocaleString(lang)} km²`;
}
