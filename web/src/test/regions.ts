const NAMED = [
  { id: 'NE0-IDN', name: 'Indonesia', lon: 95, lat: -11, level: 0, area: 1_863_875 },
  { id: 'NE1-IDN-1230', name: 'Sumatera Selatan', lon: 104, lat: -3, level: 1, area: 80_000 },
  { id: 'NE1-IDN-492', name: 'Riau', lon: 101, lat: 0, level: 1, area: 80_000 },
  { id: 'NE1-IDN-1931', name: 'Kalimantan Tengah', lon: 113, lat: -2, level: 1, area: 80_000 },
];

const OTHER = Array.from({ length: 30 }, (_, index) => ({
  id: `NE1-IDN-test-${index + 1}`,
  name: `Provinsi ${String(index + 1).padStart(2, '0')}`,
  lon: 95 + (index % 10) * 3,
  lat: -10 + Math.floor(index / 10) * 3,
  level: 1,
  area: 80_000,
}));

export const REGION_FEATURES = [...NAMED, ...OTHER].map(({ id, name, lon, lat, level, area }) => ({
  type: 'Feature',
  id,
  properties: { id, name, country: 'Indonesia', level, area_km2: area, too_large: false },
  geometry: {
    type: 'Polygon',
    coordinates: [
      [
        [lon, lat],
        [lon + 2, lat],
        [lon + 2, lat + 2],
        [lon, lat + 2],
        [lon, lat],
      ],
    ],
  },
}));

export const REGION_ROUTES: Record<string, unknown> = {
  '/regions': { query: 'Indonesia', results: REGION_FEATURES.map((feature) => feature.properties) },
  '/regions/boundaries': { type: 'FeatureCollection', features: REGION_FEATURES },
  ...Object.fromEntries(REGION_FEATURES.map((feature) => [`/regions/${feature.id}`, feature])),
};

export const GLOBAL_COUNTRIES = [
  {
    id: 'NE0-BRA',
    name: 'Brazil',
    country: 'Brazil',
    level: 0,
    area_km2: 8_500_000,
    too_large: true,
  },
  {
    id: 'NE0-PRT',
    name: 'Portugal',
    country: 'Portugal',
    level: 0,
    area_km2: 92_000,
    too_large: false,
  },
];

export const BRAZIL_PROVINCES = [
  {
    id: 'NE1-BRA-592',
    name: 'Amazonas',
    country: 'Brazil',
    level: 1,
    area_km2: 1_500_000,
    too_large: false,
  },
];

function regionFeature(props: (typeof GLOBAL_COUNTRIES)[number]) {
  return {
    type: 'Feature',
    id: props.id,
    properties: props,
    geometry: {
      type: 'Polygon',
      coordinates: [
        [
          [0, 0],
          [2, 0],
          [2, 2],
          [0, 2],
          [0, 0],
        ],
      ],
    },
  };
}

export const GLOBAL_REGION_FEATURES = GLOBAL_COUNTRIES.map(regionFeature);

export const BRAZIL_PROVINCE_FEATURES = BRAZIL_PROVINCES.map(regionFeature);

export const GLOBAL_REGION_ROUTES: Record<string, unknown> = {
  '/regions': { query: '', results: GLOBAL_COUNTRIES },
  '/regions/boundaries': { type: 'FeatureCollection', features: GLOBAL_REGION_FEATURES },
  '/regions/NE0-PRT': GLOBAL_REGION_FEATURES[1],
  '/regions/NE1-BRA-592': BRAZIL_PROVINCE_FEATURES[0],
};
