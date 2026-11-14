import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useEffect, useRef, useState } from 'react';
import {
  TerraDraw,
  TerraDrawPolygonMode,
  TerraDrawRectangleMode,
  TerraDrawSelectMode,
  type GeoJSONStoreFeatures,
} from 'terra-draw';
import { TerraDrawMapLibreGLAdapter } from 'terra-draw-maplibre-gl-adapter';
import { useMeta } from '../api/client';
import { useT } from '../i18n';
import {
  aoiBbox,
  checkAoi,
  DEFAULT_MAX_AOI_KM2,
  formatKm2,
  toFeature,
  type AoiGeometry,
} from '../lib/aoi';
import { useAppStore } from '../state/useAppStore';
import { Panel } from './Panel';

const STYLE = import.meta.env.VITE_BASEMAP_STYLE || 'https://tiles.openfreemap.org/styles/positron';
const EMPTY = { type: 'FeatureCollection' as const, features: [] };
type Tool = 'polygon' | 'rectangle' | 'select' | 'static';

const DRAW_COLOR = '#c2410c';

/** MapLibre AOI map with polygon/rectangle drawing, editing and deletion (FR-W-01). */
export function MapAoi({ children }: { children?: React.ReactNode }) {
  const { t, lang } = useT();
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const drawRef = useRef<TerraDraw | null>(null);
  const drawnId = useRef<string | number | null>(null);
  const [ready, setReady] = useState(false);
  const [tool, setTool] = useState<Tool>('static');
  const [error, setError] = useState<string | null>(null);
  const aoi = useAppStore((s) => s.aoi);
  const setAoi = useAppStore((s) => s.setAoi);
  const maxKm2 = useMeta().data?.max_aoi_km2 ?? DEFAULT_MAX_AOI_KM2;
  const maxRef = useRef(maxKm2);
  const tRef = useRef(t);
  maxRef.current = maxKm2;
  tRef.current = t;

  useEffect(() => {
    if (!container.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: STYLE,
      center: [113, -1],
      zoom: 3.4,
      attributionControl: { compact: true },
      dragRotate: false,
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    mapRef.current = map;

    map.on('load', () => {
      map.addSource('aoi', { type: 'geojson', data: EMPTY });
      map.addLayer({
        id: 'aoi-fill',
        type: 'fill',
        source: 'aoi',
        paint: { 'fill-color': DRAW_COLOR, 'fill-opacity': 0.12 },
      });
      map.addLayer({
        id: 'aoi-line',
        type: 'line',
        source: 'aoi',
        paint: { 'line-color': DRAW_COLOR, 'line-width': 2 },
      });

      const draw = new TerraDraw({
        adapter: new TerraDrawMapLibreGLAdapter({ map }),
        modes: [
          new TerraDrawPolygonMode({
            styles: { fillColor: DRAW_COLOR, outlineColor: DRAW_COLOR, fillOpacity: 0.15 },
          }),
          new TerraDrawRectangleMode({
            styles: { fillColor: DRAW_COLOR, outlineColor: DRAW_COLOR, fillOpacity: 0.15 },
          }),
          new TerraDrawSelectMode({
            flags: {
              polygon: {
                feature: {
                  draggable: true,
                  coordinates: { midpoints: true, draggable: true, deletable: true },
                },
              },
              rectangle: {
                feature: {
                  draggable: true,
                  coordinates: { draggable: true, resizable: 'opposite' },
                },
              },
            },
          }),
        ],
      });
      draw.start();
      draw.setMode('static');
      drawRef.current = draw;

      draw.on('finish', (id) => {
        const feature = draw.getSnapshotFeature(id) as GeoJSONStoreFeatures | undefined;
        if (!feature || feature.geometry.type !== 'Polygon') return;
        // Keep a single drawn AOI.
        const stale = draw
          .getSnapshot()
          .filter((f) => f.id !== id && f.geometry.type === 'Polygon')
          .map((f) => f.id as string);
        if (stale.length) draw.removeFeatures(stale);

        const geometry = feature.geometry as AoiGeometry;
        const check = checkAoi(geometry, maxRef.current);
        if (!check.ok) {
          setError(
            check.reason === 'too_large'
              ? tRef.current('map.tooLarge', {
                  area: formatKm2(check.areaKm2),
                  max: formatKm2(maxRef.current),
                })
              : tRef.current('map.invalid'),
          );
          draw.removeFeatures([id as string]);
          drawnId.current = null;
          return;
        }
        setError(null);
        drawnId.current = id as string;
        useAppStore.getState().setAoi({
          kind: 'draw',
          geometry,
          areaKm2: check.areaKm2,
          label: tRef.current('aoi.drawn'),
        });
      });
      setReady(true);
    });

    return () => {
      drawRef.current?.stop();
      drawRef.current = null;
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Show non-drawn AOIs (circle, region, upload, globe) and frame every AOI.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const source = map.getSource('aoi') as GeoJSONSource | undefined;
    source?.setData(aoi && aoi.kind !== 'draw' ? toFeature(aoi) : EMPTY);
    if (aoi && aoi.kind !== 'draw') {
      drawRef.current?.clear();
      drawnId.current = null;
    }
    if (aoi) {
      const [w, s, e, n] = aoiBbox(aoi.geometry);
      map.fitBounds(
        [
          [w, s],
          [e, n],
        ],
        { padding: 40, maxZoom: 9, duration: 600 },
      );
    }
  }, [aoi, ready]);

  const choose = (next: Tool) => {
    const draw = drawRef.current;
    if (!draw) return;
    setTool(next);
    draw.setMode(next);
    if (next === 'select' && drawnId.current != null) draw.selectFeature(drawnId.current);
  };

  const remove = () => {
    drawRef.current?.clear();
    drawRef.current?.setMode('static');
    drawnId.current = null;
    setTool('static');
    setError(null);
    setAoi(null);
  };

  const tools: { id: Tool; label: string }[] = [
    { id: 'polygon', label: t('map.polygon') },
    { id: 'rectangle', label: t('map.rectangle') },
    { id: 'select', label: t('map.edit') },
  ];

  return (
    <Panel
      title={t('panel.map')}
      actions={
        <div className="toolbar" role="toolbar" aria-label={t('map.tools')}>
          {tools.map((item) => (
            <button
              key={item.id}
              type="button"
              className="btn btn--small"
              aria-pressed={tool === item.id}
              disabled={!ready || (item.id === 'select' && aoi?.kind !== 'draw')}
              onClick={() => choose(tool === item.id ? 'static' : item.id)}
            >
              {item.label}
            </button>
          ))}
          <button
            type="button"
            className="btn btn--small btn--danger"
            disabled={!aoi}
            onClick={remove}
          >
            {t('map.delete')}
          </button>
        </div>
      }
    >
      <div
        ref={container}
        className="map"
        role="application"
        aria-label={t('map.aria')}
        data-testid="aoi-map"
      />
      {tool !== 'static' && <p className="hint">{t(`map.hint.${tool}` as const)}</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {aoi && (
        <p className="muted small">
          {aoi.label ?? t('aoi.drawn')} · {formatKm2(aoi.areaKm2, lang)}
        </p>
      )}
      {children}
    </Panel>
  );
}
