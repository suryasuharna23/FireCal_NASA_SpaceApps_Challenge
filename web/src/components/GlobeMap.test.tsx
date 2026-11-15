import '../test/mapMocks';
import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import { cellsToGeoJSON, spinSpeed } from '../lib/globe';
import { useAppStore } from '../state/useAppStore';
import { FakeMap, mapCalls } from '../test/mapMocks';
import { REGION_ROUTES } from '../test/regions';
import { META_OK, mockFetch, renderWithQuery } from '../test/render';
import { GlobeMap } from './GlobeMap';

const GLOBE = {
  year: 2026,
  month: 11,
  mode: 'harmonized',
  res: 0.5,
  source: 'VIIRS',
  provisional: true,
  count: 3,
  total: 70,
  max: 40,
  truncated: false,
  cells: [
    [102.75, -4.75, 40],
    [113.25, -1.75, 20],
    [-60.25, -9.75, 10],
  ],
  data_version: 'abc123',
};

beforeEach(() => {
  useAppStore.setState({ aoi: null, selected: null, mode: 'harmonized', mapDisplay: 'points' });
  mapCalls.fitBounds.length = 0;
  mapCalls.setData.length = 0;
  mapCalls.layout.length = 0;
  mapCalls.layers.length = 0;
  mockFetch({ '/meta': META_OK, '/globe': GLOBE, ...REGION_ROUTES });
});
afterEach(() => vi.unstubAllGlobals());

describe('globe helpers', () => {
  it('normalizes cell intensity and stops spinning when zoomed in', () => {
    const fc = cellsToGeoJSON(GLOBE.cells as [number, number, number][], 40);
    expect(fc.features).toHaveLength(3);
    expect(fc.features[0]!.properties.t).toBe(1);
    expect(fc.features[2]!.properties.t).toBeCloseTo(0.5);
    expect(spinSpeed(1)).toBeGreaterThan(spinSpeed(3));
    expect(spinSpeed(5)).toBe(0);
  });
});

describe('GlobeMap', () => {
  it('renders NASA Blue Marble imagery on a globe with an atmosphere', async () => {
    renderWithQuery(<GlobeMap />);
    await waitFor(() => expect(FakeMap.last?.projection).toEqual({ type: 'globe' }));

    const style = (
      FakeMap.last?.options as {
        style: {
          sources: Record<string, { tiles: string[] }>;
          layers: { id: string; type: string; source?: string }[];
        };
      }
    ).style;
    expect(style.sources['blue-marble']?.tiles[0]).toContain(
      'gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_NextGeneration',
    );
    expect(style.layers).toContainEqual({
      id: 'blue-marble',
      type: 'raster',
      source: 'blue-marble',
    });
    expect(FakeMap.last?.sky).toMatchObject({ 'horizon-color': '#2d6695' });
  });

  it('shows world hotspots of the latest month with a legend', async () => {
    renderWithQuery(<GlobeMap />);
    expect(await screen.findByText('November 2026')).toBeInTheDocument();
    await waitFor(() =>
      expect(
        mapCalls.setData.some(
          (d) => (d as { features: unknown[] }).features.length === GLOBE.cells.length,
        ),
      ).toBe(true),
    );
    expect(screen.getByText(/Harmonized · VIIRS/)).toBeInTheDocument();
    expect(screen.getByLabelText('Legend')).toHaveTextContent('40');
  });

  it('switches between hotspot points and a heatmap', async () => {
    renderWithQuery(<GlobeMap />);
    const heatmap = await screen.findByRole('button', { name: 'Heatmap' });
    fireEvent.click(heatmap);
    expect(heatmap).toHaveAttribute('aria-pressed', 'true');
    expect(mapCalls.layout).toContainEqual(['hotspots-heatmap', 'visibility', 'visible']);
    expect(mapCalls.layout).toContainEqual(['hotspots', 'visibility', 'none']);
    expect(screen.getByLabelText('Legend')).toHaveTextContent('Relative hotspot density');
    fireEvent.click(screen.getByRole('button', { name: 'Points' }));
    expect(mapCalls.layout.at(-3)).toEqual(['hotspots-heatmap', 'visibility', 'none']);
  });

  it('follows the month selected in the calendar', async () => {
    const fetch = mockFetch({ '/meta': META_OK, '/globe': { ...GLOBE, year: 2019, month: 9 } });
    useAppStore.setState({ selected: { year: 2019, month: 9 } });
    renderWithQuery(<GlobeMap />);
    expect(await screen.findByText('September 2019')).toBeInTheDocument();
    await waitFor(() =>
      expect(fetch.mock.calls.some((c) => String(c[0]).includes('year=2019&month=9'))).toBe(true),
    );
  });

  it('fades hotspot cells between months during playback', async () => {
    renderWithQuery(<GlobeMap />);
    await waitFor(() =>
      expect(
        mapCalls.setData.some(
          (data) => (data as { features?: unknown[] }).features?.length === GLOBE.cells.length,
        ),
      ).toBe(true),
    );
    mapCalls.paint.length = 0;
    act(() => useAppStore.getState().setSelected({ year: 2019, month: 9 }));
    await waitFor(() => expect(mapCalls.paint).toContainEqual(['hotspots', 'circle-opacity', 0]));
    await waitFor(() =>
      expect(mapCalls.paint).toContainEqual(['hotspots', 'circle-opacity', 0.95]),
    );
  });

  it('shades outside the selected province while leaving its colours unchanged', async () => {
    renderWithQuery(<GlobeMap />);
    expect(screen.queryByRole('button', { name: 'Polygon' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Rectangle' })).toBeNull();
    act(() =>
      useAppStore.setState({
        aoi: {
          kind: 'region',
          regionId: 'NE1-IDN-492',
          label: 'Riau, Indonesia',
          areaKm2: 80_000,
          geometry: (
            REGION_ROUTES['/regions/NE1-IDN-492'] as {
              geometry: { type: 'Polygon'; coordinates: number[][][] };
            }
          ).geometry,
        },
      }),
    );
    await waitFor(() => expect(mapCalls.fitBounds.length).toBeGreaterThan(0));
    expect(
      mapCalls.setData.some((data) => {
        const mask = data as { geometry?: { type: string; coordinates: unknown[][][] } };
        return mask.geometry?.type === 'MultiPolygon' && mask.geometry.coordinates[0]?.length === 2;
      }),
    ).toBe(true);
    expect(mapCalls.layers).toContainEqual({
      id: 'aoi-outline',
      type: 'line',
      source: 'aoi-outline',
      paint: { 'line-color': '#ffffff', 'line-width': 0.75, 'line-opacity': 0.8 },
    });
  });

  it('toggles the idle rotation', async () => {
    renderWithQuery(<GlobeMap />);
    const spin = await screen.findByRole('button', { name: 'Stop rotation' });
    await waitFor(() => expect(spin).toBeEnabled());
    fireEvent.click(spin);
    expect(screen.getByRole('button', { name: 'Auto-rotate' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });
});
