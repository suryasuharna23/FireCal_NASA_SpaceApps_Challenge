import type { Feature, MultiPolygon, Polygon } from 'geojson';
import { apiGet } from '../api/client';
import type { Aoi } from './aoi';

/** Provinces available in the current Indonesia snapshot. */
export interface FireRegion {
  id: string;
  name: string;
  country: string;
  level: number;
}

export const FEATURED_REGION_IDS = ['NE1-IDN-1230', 'NE1-IDN-492', 'NE1-IDN-1931'];

const LEGACY_IDS: Record<string, string> = {
  'id-sumsel': 'NE1-IDN-1230',
  'id-riau': 'NE1-IDN-492',
  'id-kalteng': 'NE1-IDN-1931',
};

export interface RegionFeature extends Feature<Polygon | MultiPolygon> {
  id: string;
  properties: {
    id: string;
    name: string;
    country: string;
    level: number;
    area_km2: number;
    too_large: boolean;
  };
}

/** The API lists Indonesia and every province present in regions.parquet. */
export async function listFireRegions(): Promise<FireRegion[]> {
  const response = await apiGet<{ results: RegionFeature['properties'][] }>('/regions', {
    q: 'Indonesia',
    limit: 100,
  });
  return response.results
    .filter((region) => !region.too_large)
    .map(({ id, name, country, level }) => ({
      id,
      name,
      country,
      level,
    }))
    .sort((a, b) => a.level - b.level || a.name.localeCompare(b.name, 'id'));
}

export function regionFeatureAoi(feature: RegionFeature): Aoi {
  return {
    kind: 'region',
    geometry: feature.geometry,
    areaKm2: feature.properties.area_km2,
    label:
      feature.properties.level === 0
        ? feature.properties.name
        : `${feature.properties.name}, ${feature.properties.country}`,
    regionId: feature.id,
  };
}

export async function loadIndonesiaBoundaries(): Promise<RegionFeature[]> {
  const response = await apiGet<{ features: RegionFeature[] }>('/regions/boundaries');
  return response.features;
}

function inRing(lon: number, lat: number, ring: number[][]): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const a = ring[i]!;
    const b = ring[j]!;
    if (
      a[1]! > lat !== b[1]! > lat &&
      lon < ((b[0]! - a[0]!) * (lat - a[1]!)) / (b[1]! - a[1]!) + a[0]!
    ) {
      inside = !inside;
    }
  }
  return inside;
}

function inPolygon(lon: number, lat: number, rings: number[][][]): boolean {
  return Boolean(
    rings[0] &&
    inRing(lon, lat, rings[0]) &&
    !rings.slice(1).some((hole) => inRing(lon, lat, hole)),
  );
}

/** Find the province containing a coordinate, falling back to the country. */
export function regionAtCoordinate(
  features: RegionFeature[],
  lat: number,
  lon: number,
): RegionFeature | null {
  return (
    [...features]
      .sort((a, b) => b.properties.level - a.properties.level)
      .find((feature) => {
        const geometry = feature.geometry;
        return geometry.type === 'Polygon'
          ? inPolygon(lon, lat, geometry.coordinates)
          : geometry.coordinates.some((polygon) => inPolygon(lon, lat, polygon));
      }) ?? null
  );
}

/** Use the saved administrative boundary, never an approximate selection circle. */
export async function loadRegionAoi(region: FireRegion | string): Promise<Aoi> {
  const requestedId = typeof region === 'string' ? region : region.id;
  const id = LEGACY_IDS[requestedId] ?? requestedId;
  const feature = await apiGet<RegionFeature>(`/regions/${encodeURIComponent(id)}`);
  return regionFeatureAoi(feature);
}
