import type { Geometry } from 'geojson';
import type { MessageKey } from '../i18n';
import { checkAoi, type Aoi, type AoiGeometry } from './aoi';

/** FR-W-04: at most 5 MB and one polygon. */
export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;

export type UploadResult =
  { ok: true; aoi: Aoi } | { ok: false; error: MessageKey; vars?: Record<string, string | number> };

function inRange(coords: unknown): boolean {
  if (!Array.isArray(coords)) return false;
  if (typeof coords[0] === 'number') {
    const [x, y] = coords as number[];
    return Number.isFinite(x) && Number.isFinite(y) && Math.abs(x!) <= 180 && Math.abs(y!) <= 90;
  }
  return coords.length > 0 && coords.every(inRange);
}

/** Pull exactly one polygon geometry out of a GeoJSON object. */
function extractGeometry(obj: unknown): AoiGeometry | MessageKey {
  if (!obj || typeof obj !== 'object') return 'upload.err.notGeojson';
  const o = obj as { type?: string; features?: unknown[]; geometry?: Geometry };
  let geometry: Geometry | undefined;
  if (o.type === 'FeatureCollection') {
    const features = Array.isArray(o.features) ? o.features : [];
    if (features.length !== 1) return 'upload.err.count';
    geometry = (features[0] as { geometry?: Geometry })?.geometry;
  } else if (o.type === 'Feature') {
    geometry = o.geometry;
  } else if (typeof o.type === 'string') {
    geometry = o as Geometry;
  } else {
    return 'upload.err.notGeojson';
  }
  if (!geometry || (geometry.type !== 'Polygon' && geometry.type !== 'MultiPolygon')) {
    return 'upload.err.type';
  }
  if (!inRange(geometry.coordinates)) return 'upload.err.coords';
  return geometry;
}

/** Validate an uploaded file's text and turn it into an AOI (FR-W-04). */
export function parseUpload(
  text: string,
  filename: string,
  sizeBytes: number,
  maxKm2: number,
): UploadResult {
  if (sizeBytes > MAX_UPLOAD_BYTES) return { ok: false, error: 'upload.err.size' };
  let json: unknown;
  try {
    json = JSON.parse(text);
  } catch {
    return { ok: false, error: 'upload.err.json' };
  }
  const geometry = extractGeometry(json);
  if (typeof geometry === 'string') return { ok: false, error: geometry };
  const check = checkAoi(geometry, maxKm2);
  if (!check.ok) {
    return check.reason === 'too_large'
      ? { ok: false, error: 'upload.err.tooLarge', vars: { area: Math.round(check.areaKm2) } }
      : { ok: false, error: 'upload.err.coords' };
  }
  return {
    ok: true,
    aoi: {
      kind: 'upload',
      geometry,
      areaKm2: check.areaKm2,
      label: filename.replace(/\.(geo)?json$/i, ''),
    },
  };
}
