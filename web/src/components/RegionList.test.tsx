import '../test/mapMocks';
import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import { listFireRegions, loadRegionAoi } from '../lib/regions';
import { useAppStore } from '../state/useAppStore';
import { FakeMap, mapCalls } from '../test/mapMocks';
import { REGION_ROUTES } from '../test/regions';
import { META_OK, mockFetch, renderWithQuery } from '../test/render';
import { GlobeMap } from './GlobeMap';
import { RegionList } from './RegionList';

beforeEach(() => {
  useAppStore.setState({ aoi: null, selected: null });
  mapCalls.fitBounds.length = 0;
  mapCalls.hits.length = 0;
  mockFetch({ '/meta': META_OK, '/globe': { cells: [], max: 0 }, ...REGION_ROUTES });
});
afterEach(() => vi.unstubAllGlobals());

describe('fire regions', () => {
  it('lists all 33 provinces returned by the API', async () => {
    const regions = await listFireRegions();
    expect(regions).toHaveLength(34);
    expect(regions[0]).toMatchObject({ name: 'Indonesia', level: 0 });
    expect(regions.some((region) => region.name === 'Riau')).toBe(true);
  });

  it('loads the actual boundary as the area', async () => {
    const aoi = await loadRegionAoi('NE1-IDN-492');
    expect(aoi).toMatchObject({ kind: 'region', regionId: 'NE1-IDN-492', areaKm2: 80_000 });
    expect(aoi.geometry.type).toBe('Polygon');
    expect(aoi.circle).toBeUndefined();
    expect((await loadRegionAoi('id-riau')).regionId).toBe('NE1-IDN-492');
  });
});

describe('RegionList', () => {
  it('selects a province boundary and marks it pressed', async () => {
    renderWithQuery(<RegionList />);
    fireEvent.click(await screen.findByRole('button', { name: /Riau/ }));
    await waitFor(() => expect(useAppStore.getState().aoi?.regionId).toBe('NE1-IDN-492'));
    expect(useAppStore.getState().aoi?.kind).toBe('region');
    expect(screen.getByRole('button', { name: /Riau/ })).toHaveAttribute('aria-pressed', 'true');
  });

  it('selects Indonesia as a country AOI', async () => {
    renderWithQuery(<RegionList />);
    fireEvent.click(await screen.findByRole('button', { name: /IndonesiaCountry/ }));
    await waitFor(() => expect(useAppStore.getState().aoi?.regionId).toBe('NE0-IDN'));
    expect(useAppStore.getState().aoi?.label).toBe('Indonesia');
  });
});

describe('GlobeMap click', () => {
  it('selects only a mapped province and frames its boundary', async () => {
    renderWithQuery(<GlobeMap />);
    await waitFor(() => expect(FakeMap.last?.sources['region-targets']).toBeDefined());
    await waitFor(() =>
      expect(
        mapCalls.setData.some((data) => (data as { features?: unknown[] }).features?.length === 34),
      ).toBe(true),
    );

    act(() =>
      FakeMap.last!.handlers.click!.forEach((h) => h({ point: {}, lngLat: { lng: 10, lat: 10 } })),
    );
    expect(useAppStore.getState().aoi).toBeNull();

    mapCalls.hits.push({
      layer: { id: 'region-targets' },
      geometry: REGION_ROUTES['/regions/NE1-IDN-492'] as unknown,
      properties: { id: 'NE1-IDN-492' },
    });
    act(() =>
      FakeMap.last!.handlers.click!.forEach((h) => h({ point: {}, lngLat: { lng: 102, lat: 1 } })),
    );
    expect(useAppStore.getState().aoi?.regionId).toBe('NE1-IDN-492');
    expect(mapCalls.fitBounds.length).toBeGreaterThan(0);
  });
});
