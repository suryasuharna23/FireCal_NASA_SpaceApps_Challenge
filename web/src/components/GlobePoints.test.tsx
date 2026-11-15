import '../test/mapMocks';
import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import { pointColorExpression, pointPopupHtml, pointRadiusExpression } from '../lib/points';
import { useAppStore } from '../state/useAppStore';
import { AOI } from '../test/fixtures';
import { FakeMap, mapCalls } from '../test/mapMocks';
import { META_OK, mockFetch, renderWithQuery } from '../test/render';
import { GlobeMap } from './GlobeMap';

const POINTS = {
  type: 'FeatureCollection',
  year: 2019,
  month: 9,
  count: 2,
  aggregated: false,
  features: [
    {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [105, 0] },
      properties: { sensor: 'MODIS', satellite: 'Terra', frp: 12.5, time: '2019-09-03T03:20Z' },
    },
    {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [106, 1] },
      properties: { sensor: 'VIIRS', satellite: 'S-NPP', frp: 3.1, time: '2019-09-04T18:10Z' },
    },
  ],
};

beforeEach(() => {
  useAppStore.setState({
    aoi: AOI,
    selected: { year: 2019, month: 9 },
    pointsColor: 'sensor',
    mapDisplay: 'points',
  });
  for (const k of ['setData', 'paint', 'layout', 'popups', 'hits', 'fitBounds'] as const)
    mapCalls[k].length = 0;
  mockFetch({ '/meta': META_OK, '/globe': { cells: [], max: 0 }, '/points': POINTS });
});
afterEach(() => vi.unstubAllGlobals());

describe('point helpers', () => {
  it('keeps the zoom ramp at the top level of the radius expression (MapLibre rule)', () => {
    const expr = pointRadiusExpression();
    expect(expr[0]).toBe('interpolate');
    expect(expr[2]).toEqual(['zoom']);
    expect(JSON.stringify(expr.slice(3))).not.toContain('"zoom"');
  });

  it('colours by sensor or by FRP and escapes popup text', () => {
    expect(JSON.stringify(pointColorExpression('sensor'))).toContain('MODIS');
    expect(pointColorExpression('frp')[0]).toBe('interpolate');
    const html = pointPopupHtml(
      {
        sensor: '<b>VIIRS</b>',
        satellite: 'S-NPP',
        frp: 3,
        time: 't',
        confidence: 'n',
        weight: 0.3,
      },
      { detections: 'd', frp: 'FRP', confidence: 'C', time: 'T', weight: 'W' },
    );
    expect(html).not.toContain('<b>VIIRS</b>');
    expect(
      pointPopupHtml(
        { count: 7, modis: 2, viirs: 5, frp: 40 },
        {
          detections: 'detections',
          frp: 'FRP',
          confidence: 'C',
          time: 'T',
          weight: 'W',
        },
      ),
    ).toContain('7 detections');
  });
});

describe('GlobeMap points', () => {
  it('shows AOI detection density when heatmap is selected', async () => {
    renderWithQuery(<GlobeMap />);
    await screen.findByText('2 detections in this area');
    fireEvent.click(screen.getByRole('button', { name: 'Heatmap' }));
    expect(mapCalls.layout).toContainEqual(['points-heatmap', 'visibility', 'visible']);
    expect(mapCalls.layout).toContainEqual(['points', 'visibility', 'none']);
    expect(screen.queryByRole('group', { name: 'Colour points by' })).not.toBeInTheDocument();
  });

  it('loads the selected month inside the AOI and dims the world cells', async () => {
    const fetch = mockFetch({
      '/meta': META_OK,
      '/globe': { cells: [], max: 0 },
      '/points': POINTS,
    });
    renderWithQuery(<GlobeMap />);
    expect(await screen.findByText('2 detections in this area')).toBeInTheDocument();
    const call = (fetch.mock.calls as unknown as [string, RequestInit][]).find((c) =>
      String(c[0]).endsWith('/points'),
    )!;
    expect(JSON.parse(call[1].body as string)).toMatchObject({ year: 2019, month: 9 });
    await waitFor(() =>
      expect(
        mapCalls.setData.some((d) => (d as { features: unknown[] }).features.length === 2),
      ).toBe(true),
    );
    expect(mapCalls.paint).toContainEqual(['hotspots', 'circle-opacity', 0.25]);
  });

  it('switches the colour mode and shows a popup for a clicked point', async () => {
    renderWithQuery(<GlobeMap />);
    fireEvent.click(await screen.findByRole('button', { name: 'FRP' }));
    expect(useAppStore.getState().pointsColor).toBe('frp');
    expect(
      mapCalls.paint.some(
        ([l, p, v]) =>
          l === 'points' && p === 'circle-color' && (v as unknown[])[0] === 'interpolate',
      ),
    ).toBe(true);

    mapCalls.hits.push({
      geometry: POINTS.features[0]!.geometry,
      properties: POINTS.features[0]!.properties,
    });
    act(() =>
      FakeMap.last!.handlers.click!.forEach((h) => h({ point: {}, lngLat: { lng: 105, lat: 0 } })),
    );
    expect(mapCalls.popups[0]).toContain('MODIS · Terra');
    expect(useAppStore.getState().aoi).toBe(AOI); // a point click does not replace the AOI
  });
});
