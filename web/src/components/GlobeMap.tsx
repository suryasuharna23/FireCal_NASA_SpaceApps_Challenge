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
import { useGlobe, usePoints } from '../api/queries';
import {
  FRP_STOPS,
  pointColorExpression,
  pointPopupHtml,
  pointRadiusExpression,
  SENSOR_COLORS,
} from '../lib/points';
import { useT } from '../i18n';
import {
  aoiBbox,
  checkAoi,
  DEFAULT_MAX_AOI_KM2,
  formatKm2,
  toFeature,
  type AoiGeometry,
} from '../lib/aoi';
import { countColor, formatCount, gradient } from '../lib/colors';
import {
  cellsToGeoJSON,
  intensityColorExpression,
  prefersReducedMotion,
  radiusExpression,
  spinSpeed,
} from '../lib/globe';
import { monthNames } from '../lib/months';
import { useAppStore } from '../state/useAppStore';
import { useGlobeMonth } from '../state/useGlobeMonth';
import { aoiForClick } from '../lib/regions';
import { RegionList } from './RegionList';
import { TimeControls } from './TimeControls';
import { Panel } from './Panel';

const STYLE = import.meta.env.VITE_BASEMAP_STYLE || 'https://tiles.openfreemap.org/styles/dark';
const EMPTY = { type: 'FeatureCollection' as const, features: [] };
const DRAW_COLOR = '#ff7a3d';
type Tool = 'polygon' | 'rectangle' | 'select' | 'static';

/**
 * Interactive 3D globe (MapLibre globe projection) that is also the AOI map
 * (FR-W-01, FR-W-23): world hotspots for one month, drag to rotate, scroll/pinch to
 * zoom from orbit down to province level, and polygon/rectangle drawing.
 */
export function GlobeMap({ children }: { children?: React.ReactNode }) {
  const { t, lang } = useT();
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const drawRef = useRef<TerraDraw | null>(null);
  const drawnId = useRef<string | number | null>(null);
  const toolRef = useRef<Tool>('static');
  const [ready, setReady] = useState(false);
  const [tool, setTool] = useState<Tool>('static');
  const [error, setError] = useState<string | null>(null);
  const [spinning, setSpinning] = useState(() => !prefersReducedMotion());
  const aoi = useAppStore((s) => s.aoi);
  const setAoi = useAppStore((s) => s.setAoi);
  const mode = useAppStore((s) => s.mode);
  const meta = useMeta().data;
  const maxKm2 = meta?.max_aoi_km2 ?? DEFAULT_MAX_AOI_KM2;
  const month = useGlobeMonth();
  const globe = useGlobe(meta?.status === 'ok' ? month : null, mode);
  const points = usePoints(aoi ? month : null);
  const pointsColor = useAppStore((s) => s.pointsColor);
  const setPointsColor = useAppStore((s) => s.setPointsColor);
  const maxRef = useRef(maxKm2);
  const tRef = useRef(t);
  maxRef.current = maxKm2;
  tRef.current = t;

  // --- map + draw setup -------------------------------------------------------------
  useEffect(() => {
    if (!container.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: STYLE,
      center: [112, -2],
      zoom: 1.9,
      minZoom: 0.8,
      attributionControl: { compact: true },
      dragRotate: false,
      renderWorldCopies: false,
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    mapRef.current = map;

    map.on('style.load', () => {
      map.setProjection({ type: 'globe' });
      // Tint the dark basemap so oceans read as a blue planet from orbit.
      for (const layer of map.getStyle().layers ?? []) {
        if (layer.type === 'background')
          map.setPaintProperty(layer.id, 'background-color', '#141a2b');
        if (layer.type === 'fill' && layer.id.includes('water'))
          map.setPaintProperty(layer.id, 'fill-color', '#0a1a3d');
      }
      map.setSky({
        'sky-color': '#060914',
        'horizon-color': '#24407f',
        'fog-color': '#0b1430',
        'sky-horizon-blend': 0.6,
        'horizon-fog-blend': 0.6,
        'fog-ground-blend': 0.4,
        'atmosphere-blend': ['interpolate', ['linear'], ['zoom'], 0, 1, 5, 1, 7, 0],
      });
    });

    map.on('load', () => {
      map.addSource('hotspots', { type: 'geojson', data: EMPTY });
      map.addLayer({
        id: 'hotspots-glow',
        type: 'circle',
        source: 'hotspots',
        paint: {
          'circle-radius': radiusExpression(2.4) as never,
          'circle-color': intensityColorExpression() as never,
          'circle-blur': 1,
          'circle-opacity': 0.35,
        },
      });
      map.addLayer({
        id: 'hotspots',
        type: 'circle',
        source: 'hotspots',
        paint: {
          'circle-radius': radiusExpression(1) as never,
          'circle-color': intensityColorExpression() as never,
          'circle-blur': 0.25,
          'circle-opacity': 0.95,
        },
      });
      map.addSource('aoi', { type: 'geojson', data: EMPTY });
      map.addLayer({
        id: 'aoi-fill',
        type: 'fill',
        source: 'aoi',
        paint: { 'fill-color': DRAW_COLOR, 'fill-opacity': 0.1 },
      });
      map.addLayer({
        id: 'aoi-line',
        type: 'line',
        source: 'aoi',
        paint: { 'line-color': DRAW_COLOR, 'line-width': 2 },
      });
      // Raw detections of the selected month inside the AOI (FR-W-15).
      map.addSource('points', { type: 'geojson', data: EMPTY });
      map.addLayer({
        id: 'points',
        type: 'circle',
        source: 'points',
        paint: {
          'circle-radius': pointRadiusExpression() as never,
          'circle-color': pointColorExpression(useAppStore.getState().pointsColor) as never,
          'circle-opacity': 0.9,
          'circle-stroke-color': 'rgba(4, 6, 13, 0.8)',
          'circle-stroke-width': 0.5,
        },
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
      // Clicking the globe (outside drawing) selects the fire region there, or a
      // circle around the point, and flies to it (FR-W-24).
      map.on('click', (e) => {
        if (toolRef.current !== 'static') return;
        const hit = map.queryRenderedFeatures(e.point, { layers: ['points'] })[0];
        if (hit) {
          const tr = tRef.current;
          new maplibregl.Popup({ closeButton: true, className: 'globe-popup' })
            .setLngLat((hit.geometry as unknown as { coordinates: [number, number] }).coordinates)
            .setHTML(
              pointPopupHtml(hit.properties ?? {}, {
                detections: tr('points.detections'),
                frp: tr('points.frp'),
                confidence: tr('points.confidence'),
                time: tr('points.time'),
                weight: tr('points.weight'),
              }),
            )
            .addTo(map);
          return;
        }
        const { lng, lat } = e.lngLat;
        const label = tRef.current('regions.clicked', { lat: lat.toFixed(2), lon: lng.toFixed(2) });
        useAppStore.getState().setAoi(aoiForClick(lng, lat, label));
      });
      setReady(true);
    });

    // Any direct interaction stops the idle spin (FR-W-27).
    const stop = () => setSpinning(false);
    for (const evt of ['mousedown', 'touchstart', 'wheel', 'keydown'] as const) {
      container.current.addEventListener(evt, stop, { passive: true });
    }

    return () => {
      drawRef.current?.stop();
      drawRef.current = null;
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // --- idle auto-rotation ----------------------------------------------------------------
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !spinning || prefersReducedMotion()) return;
    let frame = 0;
    let last = performance.now();
    const step = (now: number) => {
      const dt = Math.min((now - last) / 1000, 0.1);
      last = now;
      const speed = spinSpeed(map.getZoom());
      if (speed > 0 && !map.isMoving()) {
        const c = map.getCenter();
        map.setCenter([c.lng + speed * dt, c.lat]);
      }
      frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [ready, spinning]);

  // --- hotspot layer ---------------------------------------------------------------------
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !globe.data) return;
    const source = map.getSource('hotspots') as GeoJSONSource | undefined;
    source?.setData(cellsToGeoJSON(globe.data.cells, globe.data.max));
  }, [globe.data, ready]);

  // --- raw points of the selected month (FR-W-15) ------------------------------------------
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const source = map.getSource('points') as GeoJSONSource | undefined;
    const shown = Boolean(aoi && points.data);
    source?.setData(shown ? (points.data as never) : EMPTY);
    // Dim the coarse world cells while the detailed points are visible.
    map.setPaintProperty('hotspots', 'circle-opacity', shown ? 0.25 : 0.95);
    map.setPaintProperty('hotspots-glow', 'circle-opacity', shown ? 0.1 : 0.35);
  }, [points.data, aoi, ready]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    map.setPaintProperty('points', 'circle-color', pointColorExpression(pointsColor) as never);
  }, [pointsColor, ready]);

  // --- AOI from other sources (circle, region, upload) + framing ----------------------------
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
      setSpinning(false);
      const [w, s, e, n] = aoiBbox(aoi.geometry);
      map.fitBounds(
        [
          [w, s],
          [e, n],
        ],
        { padding: 40, maxZoom: 8, duration: 1200 },
      );
    }
  }, [aoi, ready]);

  const choose = (next: Tool) => {
    const draw = drawRef.current;
    if (!draw) return;
    setSpinning(false);
    setTool(next);
    toolRef.current = next;
    draw.setMode(next);
    if (next === 'select' && drawnId.current != null) draw.selectFeature(drawnId.current);
  };

  const remove = () => {
    drawRef.current?.clear();
    drawRef.current?.setMode('static');
    drawnId.current = null;
    setTool('static');
    toolRef.current = 'static';
    setError(null);
    setAoi(null);
  };

  const backToOrbit = () => {
    mapRef.current?.flyTo({ zoom: 1.9, duration: 1400 });
  };

  const tools: { id: Tool; label: string }[] = [
    { id: 'polygon', label: t('map.polygon') },
    { id: 'rectangle', label: t('map.rectangle') },
    { id: 'select', label: t('map.edit') },
  ];
  const monthLabel = month ? `${monthNames(lang, 'long')[month.month - 1]} ${month.year}` : '';

  return (
    <Panel
      title={t('panel.globe')}
      className="panel--globe"
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
      <div className="globe">
        <div
          ref={container}
          className="map map--globe"
          role="application"
          tabIndex={0}
          aria-label={t('globe.aria', { month: monthLabel })}
          aria-describedby="globe-help"
          data-testid="globe-map"
        />
        <div className="globe__hud globe__hud--top">
          <span className="globe__month">{monthLabel}</span>
          <span className="globe__chip">
            {t(mode === 'raw' ? 'globe.raw' : 'globe.harmonized')}
            {globe.data ? ` · ${globe.data.source}` : ''}
          </span>
          {globe.data?.provisional && (
            <span className="badge badge--warn">{t('status.provisional')}</span>
          )}
        </div>
        <div className="globe__hud globe__hud--bottom">
          <div className="globe__legend" aria-label={t('calendar.legend')}>
            <div className="legend__bar" style={{ background: gradient(countColor) }} />
            <div className="legend__ticks">
              <span>0</span>
              <span>{formatCount(globe.data?.max ?? 0, lang)}</span>
            </div>
            <small>{t('globe.unit')}</small>
            {aoi && points.data && (
              <div className="points-legend">
                <div className="points-legend__head">
                  <span>
                    {t(points.data.aggregated ? 'points.cells' : 'points.count', {
                      n: formatCount(points.data.count, lang),
                    })}
                  </span>
                  <div className="segmented" role="group" aria-label={t('points.colorBy')}>
                    {(['sensor', 'frp'] as const).map((by) => (
                      <button
                        key={by}
                        type="button"
                        className="btn btn--small"
                        aria-pressed={pointsColor === by}
                        onClick={() => setPointsColor(by)}
                      >
                        {t(by === 'sensor' ? 'points.bySensor' : 'points.byFrp')}
                      </button>
                    ))}
                  </div>
                </div>
                {pointsColor === 'sensor' ? (
                  <div className="points-legend__keys">
                    <span>
                      <i style={{ background: SENSOR_COLORS.MODIS }} /> MODIS
                    </span>
                    <span>
                      <i style={{ background: SENSOR_COLORS.VIIRS }} /> VIIRS
                    </span>
                  </div>
                ) : (
                  <>
                    <div
                      className="legend__bar"
                      style={{ background: gradient((x) => countColor(0.2 + 0.8 * x)) }}
                    />
                    <div className="legend__ticks">
                      <span>0</span>
                      <span>{FRP_STOPS[FRP_STOPS.length - 1]}+ MW</span>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
          <div className="globe__buttons">
            <button
              type="button"
              className="btn btn--small"
              aria-pressed={spinning}
              disabled={!ready || prefersReducedMotion()}
              onClick={() => setSpinning((s) => !s)}
            >
              {t(spinning ? 'globe.stopSpin' : 'globe.spin')}
            </button>
            <button type="button" className="btn btn--small" onClick={backToOrbit}>
              {t('globe.orbit')}
            </button>
          </div>
        </div>
        {globe.isFetching && <div className="globe__loading" aria-hidden="true" />}
      </div>
      <TimeControls />
      <p id="globe-help" className="hint">
        {tool !== 'static' ? t(`map.hint.${tool}` as const) : t('globe.help')}
      </p>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {globe.error && (
        <p className="form-error" role="alert">
          {(globe.error as Error).message}
        </p>
      )}
      <RegionList />
      {children}
    </Panel>
  );
}
