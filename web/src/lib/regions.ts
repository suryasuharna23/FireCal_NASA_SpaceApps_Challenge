import { distance } from '@turf/turf';
import type { Aoi } from './aoi';
import { circleAoi } from './circle';

/** A named fire-prone region used for quick selection on the globe (FR-W-24). */
export interface FireRegion {
  id: string;
  name: string;
  country: string;
  lat: number;
  lon: number;
  radiusKm: number;
}

/**
 * Well-known fire regions. Every circle stays below the 1,000,000 km² AOI limit
 * (radius ≤ 560 km) so a region opens its calendar immediately.
 */
export const FIRE_REGIONS: FireRegion[] = [
  {
    id: 'id-sumsel',
    name: 'South Sumatra',
    country: 'Indonesia',
    lat: -3.3,
    lon: 104.5,
    radiusKm: 300,
  },
  { id: 'id-riau', name: 'Riau', country: 'Indonesia', lat: 0.5, lon: 101.8, radiusKm: 250 },
  {
    id: 'id-kalteng',
    name: 'Central Kalimantan',
    country: 'Indonesia',
    lat: -2.2,
    lon: 113.9,
    radiusKm: 300,
  },
  { id: 'au-topend', name: 'Top End', country: 'Australia', lat: -14.5, lon: 132.5, radiusKm: 450 },
  {
    id: 'th-north',
    name: 'Northern Thailand & Myanmar',
    country: 'Thailand',
    lat: 19.0,
    lon: 99.0,
    radiusKm: 400,
  },
  {
    id: 'br-rondonia',
    name: 'Rondônia & Acre',
    country: 'Brazil',
    lat: -10.0,
    lon: -63.0,
    radiusKm: 450,
  },
  { id: 'br-cerrado', name: 'Cerrado', country: 'Brazil', lat: -12.5, lon: -47.0, radiusKm: 450 },
  {
    id: 'cf-north',
    name: 'Central African savanna',
    country: 'Central African Republic',
    lat: 6.5,
    lon: 21.0,
    radiusKm: 500,
  },
  {
    id: 'ao-miombo',
    name: 'Miombo woodlands',
    country: 'Angola & Zambia',
    lat: -12.0,
    lon: 20.0,
    radiusKm: 500,
  },
  { id: 'ru-yakutia', name: 'Yakutia', country: 'Russia', lat: 62.0, lon: 129.0, radiusKm: 500 },
  {
    id: 'ca-west',
    name: 'Western Canada',
    country: 'Canada',
    lat: 55.0,
    lon: -118.0,
    radiusKm: 450,
  },
  {
    id: 'us-california',
    name: 'Northern California',
    country: 'United States',
    lat: 38.5,
    lon: -121.5,
    radiusKm: 350,
  },
  {
    id: 'pt-iberia',
    name: 'Western Iberia',
    country: 'Portugal & Spain',
    lat: 40.5,
    lon: -7.5,
    radiusKm: 350,
  },
];

/** Default radius of the circle created by clicking an arbitrary point on the globe. */
export const CLICK_RADIUS_KM = 250;

/** The curated region whose circle contains the point, nearest first. */
export function regionAt(lon: number, lat: number): FireRegion | null {
  let best: { region: FireRegion; d: number } | null = null;
  for (const region of FIRE_REGIONS) {
    const d = distance([lon, lat], [region.lon, region.lat], { units: 'kilometers' });
    if (d <= region.radiusKm && (!best || d < best.d)) best = { region, d };
  }
  return best?.region ?? null;
}

export function regionAoi(region: FireRegion): Aoi {
  return circleAoi(
    region.lat,
    region.lon,
    region.radiusKm,
    `${region.name}, ${region.country}`,
    'globe',
    region.id,
  );
}

/** AOI for a click on the globe: the curated region there, or a circle around the point. */
export function aoiForClick(lon: number, lat: number, label: string): Aoi {
  const region = regionAt(lon, lat);
  if (region) return regionAoi(region);
  const round = (v: number) => Math.round(v * 100) / 100;
  return circleAoi(round(lat), round(lon), CLICK_RADIUS_KM, label, 'globe');
}
