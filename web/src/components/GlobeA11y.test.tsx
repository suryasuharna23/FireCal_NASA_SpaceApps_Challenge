import '../test/mapMocks';
import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import { useAppStore } from '../state/useAppStore';
import { AOI } from '../test/fixtures';
import { FakeMap, mapCalls } from '../test/mapMocks';
import { REGION_ROUTES } from '../test/regions';
import { META_OK, mockFetch, renderWithQuery } from '../test/render';
import { GlobeMap } from './GlobeMap';

const reducedMotion = (matches: boolean) =>
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => ({ matches, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
  );

beforeEach(() => {
  useAppStore.setState({ aoi: null, selected: { year: 2019, month: 9 }, mode: 'harmonized' });
  mapCalls.hits.length = 0;
  mockFetch({
    '/meta': META_OK,
    '/globe': { cells: [], max: 0 },
    '/points': { type: 'FeatureCollection', features: [], count: 0, aggregated: false },
    ...REGION_ROUTES,
  });
});
afterEach(() => vi.unstubAllGlobals());

describe('Globe accessibility (T-45)', () => {
  it('labels the globe with month, mode and selected area', async () => {
    renderWithQuery(<GlobeMap />);
    const globe = await screen.findByRole('application');
    expect(globe).toHaveAttribute('tabindex', '0');
    expect(globe).toHaveAccessibleName(/September 2019, harmonized values, no area selected/);

    act(() => useAppStore.setState({ aoi: AOI, mode: 'raw' }));
    await waitFor(() =>
      expect(globe).toHaveAccessibleName(/September 2019, raw per sensor values, area Area/),
    );
  });

  it('selects the area at the centre with Enter', async () => {
    renderWithQuery(<GlobeMap />);
    await waitFor(() => expect(FakeMap.last?.sources['region-targets']).toBeDefined());
    await waitFor(() =>
      expect(
        mapCalls.setData.some((data) => (data as { features?: unknown[] }).features?.length === 34),
      ).toBe(true),
    );
    mapCalls.hits.push({
      layer: { id: 'region-targets' },
      geometry: {},
      properties: { id: 'NE1-IDN-492' },
    });
    fireEvent.keyDown(screen.getByRole('application'), { key: 'Enter' });
    expect(useAppStore.getState().aoi).toMatchObject({
      kind: 'region',
      regionId: 'NE1-IDN-492',
    });
  });

  it('never auto-rotates when the user prefers reduced motion', async () => {
    reducedMotion(true);
    mockFetch({ '/meta': META_OK, '/globe': { cells: [], max: 0 } });
    renderWithQuery(<GlobeMap />);
    const spin = await screen.findByRole('button', { name: 'Auto-rotate' });
    expect(spin).toHaveAttribute('aria-pressed', 'false');
    expect(spin).toBeDisabled();
  });
});
