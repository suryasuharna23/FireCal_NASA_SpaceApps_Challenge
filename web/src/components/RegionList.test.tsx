import '../test/mapMocks';
import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import { aoiForClick, CLICK_RADIUS_KM, FIRE_REGIONS, regionAt } from '../lib/regions';
import { useAppStore } from '../state/useAppStore';
import { FakeMap, mapCalls } from '../test/mapMocks';
import { META_OK, mockFetch, renderWithQuery } from '../test/render';
import { GlobeMap } from './GlobeMap';
import { RegionList } from './RegionList';

beforeEach(() => {
  useAppStore.setState({ aoi: null, selected: null });
  mapCalls.fitBounds.length = 0;
  mockFetch({ '/meta': META_OK, '/globe': { cells: [], max: 0, source: 'VIIRS' } });
});
afterEach(() => vi.unstubAllGlobals());

describe('fire regions', () => {
  it('stay under the AOI limit', () => {
    for (const region of FIRE_REGIONS) {
      expect(Math.PI * region.radiusKm ** 2).toBeLessThan(1_000_000);
    }
  });

  it('finds the region under a point and falls back to a circle elsewhere', () => {
    expect(regionAt(104.4, -3.2)?.id).toBe('id-sumsel');
    expect(regionAt(0, -60)).toBeNull();
    const inRegion = aoiForClick(113.9, -2.2, 'x');
    expect(inRegion).toMatchObject({ kind: 'globe', regionId: 'id-kalteng' });
    const open = aoiForClick(10.123, 50.456, 'Area around 50.46, 10.12');
    expect(open.regionId).toBeUndefined();
    expect(open.circle).toEqual({ lat: 50.46, lon: 10.12, radiusKm: CLICK_RADIUS_KM });
  });
});

describe('RegionList', () => {
  it('selects a region as the AOI and marks it pressed', () => {
    renderWithQuery(<RegionList />);
    fireEvent.click(screen.getByRole('button', { name: /Cerrado/ }));
    expect(useAppStore.getState().aoi).toMatchObject({ kind: 'globe', regionId: 'br-cerrado' });
    expect(screen.getByRole('button', { name: /Cerrado/ })).toHaveAttribute('aria-pressed', 'true');
  });
});

describe('GlobeMap click', () => {
  it('selects the clicked region and flies to it, but not while drawing', async () => {
    renderWithQuery(<GlobeMap />);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Polygon' })).toBeEnabled());

    act(() =>
      FakeMap.last!.handlers.click!.forEach((h) => h({ lngLat: { lng: 101.8, lat: 0.5 } })),
    );
    expect(useAppStore.getState().aoi?.regionId).toBe('id-riau');
    expect(mapCalls.fitBounds.length).toBeGreaterThan(0);

    useAppStore.setState({ aoi: null });
    fireEvent.click(screen.getByRole('button', { name: 'Polygon' }));
    act(() =>
      FakeMap.last!.handlers.click!.forEach((h) => h({ lngLat: { lng: 101.8, lat: 0.5 } })),
    );
    expect(useAppStore.getState().aoi).toBeNull();
  });
});
