import '../test/mapMocks';
import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import { checkAoi } from '../lib/aoi';
import { useAppStore } from '../state/useAppStore';
import { FakeDraw, mapCalls } from '../test/mapMocks';
import { META_OK, mockFetch, renderWithQuery } from '../test/render';
import { MapAoi } from './MapAoi';

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

beforeEach(() => {
  useAppStore.setState({ aoi: null });
  mapCalls.fitBounds.length = 0;
  mockFetch({ '/meta': META_OK });
});
afterEach(() => vi.unstubAllGlobals());

describe('checkAoi', () => {
  it('accepts areas under the limit and rejects larger or empty ones', () => {
    expect(checkAoi(square(1), 1_000_000)).toMatchObject({ ok: true });
    expect(checkAoi(square(12), 1_000_000)).toMatchObject({ ok: false, reason: 'too_large' });
    expect(checkAoi(square(0), 1_000_000)).toMatchObject({ ok: false, reason: 'empty' });
  });
});

describe('MapAoi', () => {
  it('stores a drawn polygon as the AOI and can delete it', async () => {
    renderWithQuery(<MapAoi />);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Poligon' })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: 'Poligon' }));
    expect(FakeDraw.last?.mode).toBe('polygon');

    act(() => FakeDraw.last!.finish({ id: 'a', geometry: square(2), properties: {} }));
    const aoi = useAppStore.getState().aoi;
    expect(aoi?.kind).toBe('draw');
    expect(aoi!.areaKm2).toBeGreaterThan(40_000);
    expect(screen.getByText(/Area yang digambar/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Hapus' }));
    expect(useAppStore.getState().aoi).toBeNull();
  });

  it('rejects an AOI that is too large with a message', async () => {
    renderWithQuery(<MapAoi />);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Persegi' })).toBeEnabled());
    act(() => FakeDraw.last!.finish({ id: 'big', geometry: square(15), properties: {} }));
    expect(await screen.findByRole('alert')).toHaveTextContent('terlalu luas');
    expect(useAppStore.getState().aoi).toBeNull();
    expect(FakeDraw.last!.features).toHaveLength(0);
  });

  it('frames AOIs chosen elsewhere', async () => {
    renderWithQuery(<MapAoi />);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Poligon' })).toBeEnabled());
    act(() =>
      useAppStore.getState().setAoi({ kind: 'region', geometry: square(1), areaKm2: 12_000 }),
    );
    expect(mapCalls.fitBounds.length).toBeGreaterThan(0);
  });
});
