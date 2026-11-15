import '../test/mapMocks';
import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import { listFireRegions, loadRegionAoi } from '../lib/regions';
import { useAppStore } from '../state/useAppStore';
import { FakeMap, mapCalls } from '../test/mapMocks';
import {
  BRAZIL_PROVINCE_FEATURES,
  BRAZIL_PROVINCES,
  GLOBAL_COUNTRIES,
  GLOBAL_REGION_FEATURES,
  REGION_ROUTES,
} from '../test/regions';
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

describe('RegionList worldwide coverage', () => {
  beforeEach(() => {
    useAppStore.setState({ scope: 'global', aoi: null, selected: null, mode: 'raw' });
  });

  const stubWorldwide = () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(typeof input === 'string' ? input : input.toString());
      let body: unknown;
      if (url.pathname === '/meta') body = META_OK;
      else if (url.pathname === '/globe') body = { cells: [], max: 0 };
      else if (url.searchParams.get('country') === 'Brazil') body = { results: BRAZIL_PROVINCES };
      else if (url.pathname === '/regions') body = { results: GLOBAL_COUNTRIES };
      else if (url.pathname === '/regions/NE0-PRT') body = GLOBAL_REGION_FEATURES[1];
      else if (url.pathname === '/regions/boundaries')
        body = { type: 'FeatureCollection', features: GLOBAL_REGION_FEATURES };
      else if (url.pathname === '/regions/NE1-BRA-592') body = BRAZIL_PROVINCE_FEATURES[0];
      else return new Response('{"detail":"not found"}', { status: 404 });
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    });
    vi.stubGlobal('fetch', fetchMock);
    return fetchMock;
  };

  it('lists countries and expands the provinces of a large one', async () => {
    stubWorldwide();
    renderWithQuery(<RegionList />);
    const brazil = await screen.findByRole('button', { name: /BrazilToo large to analyse/ });
    expect(screen.queryByRole('button', { name: /Amazonas/ })).toBeNull();
    fireEvent.click(brazil);
    fireEvent.click(await screen.findByRole('button', { name: /AmazonasProvince \/ state/ }));
    await waitFor(() => expect(useAppStore.getState().aoi?.regionId).toBe('NE1-BRA-592'));
    expect(useAppStore.getState().aoi?.label).toBe('Amazonas, Brazil');
  });

  it('uses a small country boundary directly as the area', async () => {
    stubWorldwide();
    renderWithQuery(<RegionList />);
    fireEvent.click(await screen.findByRole('button', { name: /PortugalCountry/ }));
    await waitFor(() => expect(useAppStore.getState().aoi?.regionId).toBe('NE0-PRT'));
    expect(useAppStore.getState().aoi?.label).toBe('Portugal');
  });

  it('maps every world country as a globe selection target', async () => {
    stubWorldwide();
    renderWithQuery(<GlobeMap />);
    await waitFor(() =>
      expect(
        mapCalls.setData.some(
          (data) => (data as { features?: unknown[] }).features?.length === GLOBAL_COUNTRIES.length,
        ),
      ).toBe(true),
    );
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
