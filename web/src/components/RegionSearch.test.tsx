import { fireEvent, screen, waitFor } from '@testing-library/react';
import { useAppStore } from '../state/useAppStore';
import { META_OK, mockFetch, renderWithQuery } from '../test/render';
import { RegionSearch } from './RegionSearch';

const RIAU = {
  id: 'NE1-IDN-1',
  name: 'Riau',
  level: 1,
  country: 'Indonesia',
  parent: 'Indonesia',
  area_km2: 89_000,
  bbox: [100, -1, 104, 2],
  too_large: false,
};
const INDONESIA = {
  ...RIAU,
  id: 'NE0-IDN',
  name: 'Indonesia',
  level: 0,
  area_km2: 1_860_000,
  too_large: true,
};

beforeEach(() => {
  useAppStore.setState({ aoi: null });
  mockFetch({
    '/meta': META_OK,
    '/regions': { query: 'ri', results: [RIAU, INDONESIA] },
    '/regions/NE1-IDN-1': {
      type: 'Feature',
      id: 'NE1-IDN-1',
      properties: RIAU,
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [100, -1],
            [104, -1],
            [104, 2],
            [100, 2],
            [100, -1],
          ],
        ],
      },
    },
  });
});
afterEach(() => vi.unstubAllGlobals());

describe('RegionSearch', () => {
  it('searches regions and uses the selected boundary as the AOI', async () => {
    renderWithQuery(<RegionSearch />);
    fireEvent.change(screen.getByLabelText('Find a country or province'), {
      target: { value: 'ri' },
    });
    const riau = await screen.findByRole('button', { name: /Riau/ });
    expect(riau).toHaveTextContent('Province / state · Indonesia');
    fireEvent.click(riau);
    await waitFor(() => expect(useAppStore.getState().aoi).not.toBeNull());
    expect(useAppStore.getState().aoi).toMatchObject({
      kind: 'region',
      regionId: 'NE1-IDN-1',
      label: 'Riau, Indonesia',
      areaKm2: 89_000,
    });
  });

  it('disables regions above the AOI limit', async () => {
    renderWithQuery(<RegionSearch />);
    fireEvent.change(screen.getByLabelText('Find a country or province'), {
      target: { value: 'ri' },
    });
    const country = await screen.findByRole('button', { name: /^Indonesia/ });
    expect(country).toBeDisabled();
    expect(country).toHaveTextContent('Too large to analyse');
  });

  it('waits for at least two characters', () => {
    renderWithQuery(<RegionSearch />);
    fireEvent.change(screen.getByLabelText('Find a country or province'), {
      target: { value: 'r' },
    });
    expect(screen.queryByRole('list')).toBeNull();
  });
});
