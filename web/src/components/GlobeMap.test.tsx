import '../test/mapMocks';
import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import { checkAoi } from '../lib/aoi';
import { cellsToGeoJSON, spinSpeed } from '../lib/globe';
import { useAppStore } from '../state/useAppStore';
import { FakeDraw, mapCalls } from '../test/mapMocks';
import { META_OK, mockFetch, renderWithQuery } from '../test/render';
import { GlobeMap } from './GlobeMap';

const square = (size: number) => ({
  type: 'Polygon' as const,
  coordinates: [
    [
      [110, 0],
      [110 + size, 0],
      [110 + size, size],
      [110, size],
      [110, 0],
    ],
  ],
});

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
  useAppStore.setState({ aoi: null, selected: null, mode: 'harmonized' });
  mapCalls.fitBounds.length = 0;
  mapCalls.setData.length = 0;
  mockFetch({ '/meta': META_OK, '/globe': GLOBE });
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

  it('accepts areas under the limit and rejects larger or empty ones', () => {
    expect(checkAoi(square(1), 1_000_000)).toMatchObject({ ok: true });
    expect(checkAoi(square(12), 1_000_000)).toMatchObject({ ok: false, reason: 'too_large' });
    expect(checkAoi(square(0), 1_000_000)).toMatchObject({ ok: false, reason: 'empty' });
  });
});

describe('GlobeMap', () => {
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
    expect(screen.getByText(/Terharmonisasi · VIIRS/)).toBeInTheDocument();
    expect(screen.getByLabelText('Legenda')).toHaveTextContent('40');
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

  it('stores a drawn polygon as the AOI and can delete it', async () => {
    renderWithQuery(<GlobeMap />);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Poligon' })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: 'Poligon' }));
    expect(FakeDraw.last?.mode).toBe('polygon');

    act(() => FakeDraw.last!.finish({ id: 'a', geometry: square(2), properties: {} }));
    const aoi = useAppStore.getState().aoi;
    expect(aoi?.kind).toBe('draw');
    expect(aoi!.areaKm2).toBeGreaterThan(40_000);
    expect(mapCalls.fitBounds.length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole('button', { name: 'Hapus' }));
    expect(useAppStore.getState().aoi).toBeNull();
  });

  it('rejects an AOI that is too large with a message', async () => {
    renderWithQuery(<GlobeMap />);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Persegi' })).toBeEnabled());
    act(() => FakeDraw.last!.finish({ id: 'big', geometry: square(15), properties: {} }));
    expect(await screen.findByRole('alert')).toHaveTextContent('terlalu luas');
    expect(useAppStore.getState().aoi).toBeNull();
    expect(FakeDraw.last!.features).toHaveLength(0);
  });

  it('toggles the idle rotation', async () => {
    renderWithQuery(<GlobeMap />);
    const spin = await screen.findByRole('button', { name: 'Hentikan putaran' });
    await waitFor(() => expect(spin).toBeEnabled());
    fireEvent.click(spin);
    expect(screen.getByRole('button', { name: 'Putar otomatis' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });
});
