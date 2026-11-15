import type { GeoJSONSource, Map as MapLibreMap, StyleSpecification } from 'maplibre-gl';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useEffect, useRef, useState } from 'react';
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
import { aoiBbox, outsideAoiMask, toFeature } from '../lib/aoi';
import { countColor, formatCount, gradient } from '../lib/colors';
import {
  cellsToGeoJSON,
  intensityColorExpression,
  prefersReducedMotion,
  radiusExpression,
  spinSpeed,
} from '../lib/globe';
import { monthNames } from '../lib/months';
import { frameFor } from '../lib/playback';
import { useAppStore } from '../state/useAppStore';
import { useGlobeMonth } from '../state/useGlobeMonth';
import { loadRegionBoundaries, regionFeatureAoi } from '../lib/regions';
import { TimeControls } from './TimeControls';
import { Panel } from './Panel';

// NASA's cloud-free Blue Marble mosaic gives the globe natural land, ocean,
// desert, and ice colours. Keep an optional style override for deployments.
const EARTH_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    'blue-marble': {
      type: 'raster',
      tiles: [
        'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_NextGeneration/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg',
      ],
      tileSize: 256,
      maxzoom: 8,
      attribution:
        '<a href="https://earthobservatory.nasa.gov/features/BlueMarble">NASA Blue Marble</a>',
    },
  },
  layers: [
    { id: 'space', type: 'background', paint: { 'background-color': '#030914' } },
    { id: 'blue-marble', type: 'raster', source: 'blue-marble' },
  ],
};
const STYLE = import.meta.env.VITE_BASEMAP_STYLE || EARTH_STYLE;
const EMPTY = { type: 'FeatureCollection' as const, features: [] };
const SHADOW_COLOR = '#020611';

/**
 * Interactive 3D globe (MapLibre globe projection) that is also the AOI map
 * (FR-W-23): monthly hotspot cells, province boundaries, drag to rotate and zoom.
 */
export function GlobeMap({ children }: { children?: React.ReactNode }) {
  const { t, lang } = useT();
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const regionAoisRef = useRef(new Map<string, ReturnType<typeof regionFeatureAoi>>());
  const hasGlobeDataRef = useRef(false);
  const detailedRef = useRef(false);
  const [ready, setReady] = useState(false);
  const [spinning, setSpinning] = useState(() => !prefersReducedMotion());
  // The legend starts folded on phones so it does not cover the globe.
  const [legendOpen, setLegendOpen] = useState(
    () =>
      typeof window.matchMedia !== 'function' || !window.matchMedia('(max-width: 600px)').matches,
  );
  const aoi = useAppStore((s) => s.aoi);
  const previousAoi = useRef(aoi);
  const setAoi = useAppStore((s) => s.setAoi);
  const mode = useAppStore((s) => s.mode);
  const scope = useAppStore((s) => s.scope);
  const previousScope = useRef(scope);
  const meta = useMeta().data;
  const month = useGlobeMonth();
  const playbackPeriod = useAppStore((s) => s.playbackPeriod);
  const playbackDay = useAppStore((s) => s.playbackDay);
  const playbackHour = useAppStore((s) => s.playbackHour);
  const frame = month ? frameFor(month, playbackPeriod, playbackDay, playbackHour) : null;
  const globe = useGlobe(meta?.status === 'ok' ? frame : null, mode);
  const hasObservedGlobalPoints = scope !== 'global' || Boolean(globe.data?.points?.length);
  const pointsAvailable = scope !== 'global' || meta?.global?.points_available !== false;
  const canInspectAoi = aoi && aoi.areaKm2 <= (meta?.max_aoi_km2 ?? Infinity);
  const points = usePoints(canInspectAoi && pointsAvailable ? frame : null);
  const pointsColor = useAppStore((s) => s.pointsColor);
  const setPointsColor = useAppStore((s) => s.setPointsColor);
  const mapDisplay = useAppStore((s) => s.mapDisplay);
  const setMapDisplay = useAppStore((s) => s.setMapDisplay);
  const tRef = useRef(t);
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
      map.setSky({
        'sky-color': '#020610',
        'horizon-color': '#2d6695',
        'fog-color': '#102b4a',
        'sky-horizon-blend': 0.45,
        'horizon-fog-blend': 0.5,
        'fog-ground-blend': 0.25,
        'atmosphere-blend': ['interpolate', ['linear'], ['zoom'], 0, 1, 5, 1, 7, 0],
      });
    });

    map.on('style.load', () => {
      map.addSource('hotspots', { type: 'geojson', data: EMPTY });
      map.addSource('hotspots-density', { type: 'geojson', data: EMPTY });
      map.addLayer({
        id: 'hotspots-glow',
        type: 'circle',
        source: 'hotspots',
        paint: {
          'circle-radius': radiusExpression(2.4) as never,
          'circle-color': intensityColorExpression() as never,
          'circle-blur': 1,
          'circle-opacity': 0.35,
          'circle-opacity-transition': { duration: 250 },
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
          'circle-opacity-transition': { duration: 250 },
        },
      });
      map.addLayer({
        id: 'hotspots-heatmap',
        type: 'heatmap',
        source: 'hotspots-density',
        layout: { visibility: 'none' },
        paint: {
          'heatmap-weight': ['max', 0.05, ['get', 't']],
          'heatmap-intensity': 1,
          'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 0, 9, 3, 20, 7, 36],
          'heatmap-opacity': 0.8,
          'heatmap-opacity-transition': { duration: 250 },
          'heatmap-color': [
            'interpolate',
            ['linear'],
            ['heatmap-density'],
            0,
            'rgba(0, 0, 0, 0)',
            0.15,
            '#4a2612',
            0.35,
            '#8a380a',
            0.55,
            '#e04006',
            0.75,
            '#ff6b1a',
            0.9,
            '#ff9f1c',
            1,
            '#ffd23f',
          ],
        },
      });
      map.addSource('aoi-shadow', { type: 'geojson', data: EMPTY });
      map.addSource('aoi-outline', { type: 'geojson', data: EMPTY });
      map.addSource('region-targets', { type: 'geojson', data: EMPTY });
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
      map.addLayer({
        id: 'points-heatmap',
        type: 'heatmap',
        source: 'points',
        layout: { visibility: 'none' },
        paint: {
          'heatmap-weight': ['case', ['has', 'count'], ['min', 5, ['sqrt', ['get', 'count']]], 1],
          'heatmap-intensity': 1,
          'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 3, 11, 7, 25, 11, 40],
          'heatmap-opacity': 0.85,
          'heatmap-color': [
            'interpolate',
            ['linear'],
            ['heatmap-density'],
            0,
            'rgba(0, 0, 0, 0)',
            0.15,
            '#4a2612',
            0.35,
            '#8a380a',
            0.55,
            '#e04006',
            0.75,
            '#ff6b1a',
            0.9,
            '#ff9f1c',
            1,
            '#ffd23f',
          ],
        },
      });
      map.addLayer({
        id: 'region-targets',
        type: 'fill',
        source: 'region-targets',
        paint: { 'fill-color': SHADOW_COLOR, 'fill-opacity': 0.01 },
      });
      map.addLayer({
        id: 'aoi-shadow',
        type: 'fill',
        source: 'aoi-shadow',
        paint: { 'fill-color': SHADOW_COLOR, 'fill-opacity': 0.55 },
      });
      map.addLayer({
        id: 'aoi-outline',
        type: 'line',
        source: 'aoi-outline',
        paint: { 'line-color': '#ffffff', 'line-width': 0.75, 'line-opacity': 0.8 },
      });

      // A click selects a province only when it falls within its saved boundary.
      map.on('click', (e) => {
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
        const regions = map.queryRenderedFeatures(e.point, { layers: ['region-targets'] });
        const region = regions.find((feature) => feature.properties?.level === 1) ?? regions[0];
        const aoi = regionAoisRef.current.get(String(region?.properties?.id ?? ''));
        if (aoi) useAppStore.getState().setAoi(aoi);
      });
      setReady(true);
    });

    // Any direct interaction stops the idle spin (FR-W-27).
    const stop = () => setSpinning(false);
    for (const evt of ['mousedown', 'touchstart', 'wheel', 'keydown'] as const) {
      container.current.addEventListener(evt, stop, { passive: true });
    }

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    let cancelled = false;
    void loadRegionBoundaries(scope)
      .then((features) => {
        if (cancelled) return;
        regionAoisRef.current.clear();
        for (const feature of features) {
          regionAoisRef.current.set(feature.id, regionFeatureAoi(feature));
        }
        (map.getSource('region-targets') as GeoJSONSource | undefined)?.setData({
          type: 'FeatureCollection',
          features,
        });
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [ready, scope]);

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
    if (!map || !ready) return;
    if (previousScope.current !== scope || globe.error) {
      (map.getSource('hotspots') as GeoJSONSource | undefined)?.setData(EMPTY);
      (map.getSource('hotspots-density') as GeoJSONSource | undefined)?.setData(EMPTY);
      (map.getSource('points') as GeoJSONSource | undefined)?.setData(EMPTY);
      hasGlobeDataRef.current = false;
    }
    previousScope.current = scope;
  }, [scope, globe.error, ready]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !globe.data) return;
    const source = map.getSource('hotspots') as GeoJSONSource | undefined;
    const densitySource = map.getSource('hotspots-density') as GeoJSONSource | undefined;
    const density = cellsToGeoJSON(globe.data.cells, globe.data.max);
    const data =
      scope === 'global'
        ? globe.data.points?.length
          ? cellsToGeoJSON(globe.data.points, 1)
          : EMPTY
        : density;
    map.setPaintProperty(
      'hotspots',
      'circle-color',
      scope === 'global' && globe.data.points?.length
        ? '#ff7a3d'
        : (intensityColorExpression() as never),
    );
    map.setPaintProperty(
      'hotspots',
      'circle-radius',
      radiusExpression(scope === 'global' ? 0.45 : 1) as never,
    );
    if (!hasGlobeDataRef.current) {
      hasGlobeDataRef.current = true;
      source?.setData(data);
      densitySource?.setData(density);
      return;
    }
    map.setPaintProperty('hotspots', 'circle-opacity', 0);
    map.setPaintProperty('hotspots-glow', 'circle-opacity', 0);
    map.setPaintProperty('hotspots-heatmap', 'heatmap-opacity', 0);
    let restore: number | undefined;
    const swap = window.setTimeout(() => {
      source?.setData(data);
      densitySource?.setData(density);
      restore = window.setTimeout(() => {
        map.setPaintProperty('hotspots', 'circle-opacity', detailedRef.current ? 0.25 : 0.95);
        map.setPaintProperty('hotspots-glow', 'circle-opacity', detailedRef.current ? 0.1 : 0.35);
        map.setPaintProperty('hotspots-heatmap', 'heatmap-opacity', 0.8);
      }, 70);
    }, 210);
    return () => {
      window.clearTimeout(swap);
      window.clearTimeout(restore);
    };
  }, [globe.data, ready, scope]);

  useEffect(() => {
    if (scope === 'global' && globe.data && !hasObservedGlobalPoints && mapDisplay === 'points') {
      setMapDisplay('heatmap');
    }
  }, [scope, globe.data, hasObservedGlobalPoints, mapDisplay, setMapDisplay]);

  // --- raw points of the selected month (FR-W-15) ------------------------------------------
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const source = map.getSource('points') as GeoJSONSource | undefined;
    const shown = Boolean(aoi && points.data);
    detailedRef.current = shown;
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

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const heatmap = mapDisplay === 'heatmap';
    const detail = Boolean(aoi && points.data);
    map.setLayoutProperty(
      'hotspots-glow',
      'visibility',
      heatmap || scope === 'global' ? 'none' : 'visible',
    );
    map.setLayoutProperty('hotspots', 'visibility', heatmap ? 'none' : 'visible');
    map.setLayoutProperty(
      'hotspots-heatmap',
      'visibility',
      heatmap && !detail ? 'visible' : 'none',
    );
    map.setLayoutProperty('points', 'visibility', heatmap ? 'none' : 'visible');
    map.setLayoutProperty('points-heatmap', 'visibility', heatmap && detail ? 'visible' : 'none');
  }, [mapDisplay, aoi, points.data, ready, scope]);

  // --- Selected administrative boundary and framing ---------------------------------------
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const cleared = previousAoi.current !== null && aoi === null;
    previousAoi.current = aoi;
    const source = map.getSource('aoi-shadow') as GeoJSONSource | undefined;
    source?.setData(aoi ? outsideAoiMask(aoi.geometry) : EMPTY);
    (map.getSource('aoi-outline') as GeoJSONSource | undefined)?.setData(
      aoi ? toFeature(aoi) : EMPTY,
    );
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
    } else if (cleared) {
      map.flyTo({ zoom: 1.9, duration: 1400 });
      setSpinning(!prefersReducedMotion());
    }
  }, [aoi, ready]);

  const backToOrbit = () => {
    mapRef.current?.flyTo({ zoom: 1.9, duration: 1400 });
  };

  const monthLabel = month
    ? playbackPeriod === 'year'
      ? `${month.year}`
      : `${playbackPeriod === 'day' || playbackPeriod === 'hour' ? `${frame?.day} ` : ''}${monthNames(lang, 'long')[month.month - 1]} ${month.year}${playbackPeriod === 'hour' ? `, ${String(frame?.hour).padStart(2, '0')}:00 UTC` : ''}`
    : '';

  return (
    <Panel title={t('panel.globe')} className="panel--globe">
      <div className="globe">
        <div
          ref={container}
          className="map map--globe"
          role="application"
          tabIndex={0}
          aria-label={t('globe.aria', {
            month: monthLabel,
            mode: t(mode === 'raw' ? 'globe.raw' : 'globe.harmonized').toLowerCase(),
            region: aoi?.label ? t('globe.regionLabel', { name: aoi.label }) : t('globe.noRegion'),
          })}
          onKeyDown={(e) => {
            // Enter selects a region when the centre of the globe is inside its boundary.
            if (e.key !== 'Enter' || !mapRef.current) return;
            e.preventDefault();
            const map = mapRef.current;
            const hits = map.queryRenderedFeatures(map.project(map.getCenter()), {
              layers: ['region-targets'],
            });
            const hit = hits.find((feature) => feature.properties?.level === 1) ?? hits[0];
            const region = regionAoisRef.current.get(String(hit?.properties?.id ?? ''));
            if (region) setAoi(region);
          }}
          aria-describedby="globe-help"
          data-testid="globe-map"
        />
        <div className="globe__hud globe__hud--top">
          <span className="globe__month">{monthLabel}</span>
          <span className="globe__chip">
            {scope === 'global'
              ? 'NASA detection counts'
              : t(mode === 'raw' ? 'globe.raw' : 'globe.harmonized')}
            {globe.data ? ` · ${globe.data.source}` : ''}
          </span>
          {globe.data?.provisional && (
            <span className="badge badge--warn">{t('status.provisional')}</span>
          )}
        </div>
        <div className="globe__hud globe__hud--bottom">
          <div className="segmented" role="group" aria-label={t('map.display')}>
            {(['points', 'heatmap'] as const).map((display) => (
              <button
                key={display}
                type="button"
                className="btn btn--small"
                aria-pressed={mapDisplay === display}
                disabled={display === 'points' && !hasObservedGlobalPoints && Boolean(globe.data)}
                onClick={() => setMapDisplay(display)}
              >
                {t(display === 'points' ? 'map.displayPoints' : 'map.displayHeatmap')}
              </button>
            ))}
          </div>
          <details
            className="globe__legend"
            aria-label={t('calendar.legend')}
            open={legendOpen}
            onToggle={(e) => setLegendOpen((e.currentTarget as HTMLDetailsElement).open)}
          >
            <summary>
              {t('globe.legend')}
              {aoi && points.data ? ` · ${formatCount(points.data.count, lang)}` : ''}
            </summary>
            {scope === 'global' && mapDisplay === 'points' ? (
              <small>
                {formatCount(globe.data?.points?.length ?? 0, lang)} observed locations shown. One
                real detection sampled per occupied grid cell; the full detection count is in
                Heatmap.
              </small>
            ) : (
              <>
                <div
                  className="legend__bar"
                  style={{
                    background: gradient(countColor),
                  }}
                />
                <div className="legend__ticks">
                  <span>0</span>
                  <span>
                    {mapDisplay === 'heatmap'
                      ? t('map.highDensity')
                      : formatCount(globe.data?.max ?? 0, lang)}
                  </span>
                </div>
                <small>
                  {mapDisplay === 'heatmap' ? t('map.relativeDensity') : t('globe.unit')}
                </small>
              </>
            )}
            {mapDisplay === 'heatmap' && <small>{t('map.heatmapHint')}</small>}
            {aoi && points.data && mapDisplay === 'points' && (
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
          </details>
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
      {scope === 'global' && (
        <p className="hint">
          Worldwide NASA observations · {meta?.global?.start_date} to {meta?.global?.last_acq_date}.{' '}
          Earlier worldwide years are not installed, so they are unavailable rather than zero. MODIS
          and all three VIIRS platforms. Counts are satellite detections; several satellites may see
          the same fire.
          {meta?.global?.lagging_sources?.map((s) => (
            <span key={s.source}>
              {' '}
              {s.source.replace('VIIRS_', '').replace('_NRT', '')} available through{' '}
              {s.available_through}.
            </span>
          ))}
        </p>
      )}
      <p id="globe-help" className="hint">
        {scope === 'global'
          ? pointsAvailable
            ? 'Drag to rotate and scroll to zoom. Use Area to inspect detections anywhere in the world.'
            : 'Drag to rotate and scroll to zoom. Select a country to focus the globe; detailed detections are unavailable in this deployment.'
          : t('globe.help')}
      </p>
      {globe.error && (
        <p className="form-error" role="alert">
          {(globe.error as Error).message}
        </p>
      )}
      {points.error && (
        <p className="form-error" role="alert">
          {(points.error as Error).message}
        </p>
      )}
      {children}
    </Panel>
  );
}
