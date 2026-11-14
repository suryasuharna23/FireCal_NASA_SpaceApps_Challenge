import '../test/mapMocks';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { useAppStore } from '../state/useAppStore';
import { AOI } from '../test/fixtures';
import { META_OK, mockFetch, renderWithQuery } from '../test/render';
import { GlobeMap } from './GlobeMap';

const reducedMotion = (matches: boolean) =>
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => ({ matches, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
  );

beforeEach(() => {
  useAppStore.setState({ aoi: null, selected: { year: 2019, month: 9 }, mode: 'harmonized' });
  mockFetch({ '/meta': META_OK, '/globe': { cells: [], max: 0 }, '/points': { features: [] } });
});
afterEach(() => vi.unstubAllGlobals());

describe('Globe accessibility (T-45)', () => {
  it('labels the globe with month, mode and selected area', async () => {
    renderWithQuery(<GlobeMap />);
    const globe = await screen.findByRole('application');
    expect(globe).toHaveAttribute('tabindex', '0');
    expect(globe).toHaveAccessibleName(/September 2019, harmonized values, no area selected/);

    useAppStore.setState({ aoi: AOI, mode: 'raw' });
    await waitFor(() =>
      expect(globe).toHaveAccessibleName(/September 2019, raw per sensor values, area Area/),
    );
  });

  it('selects the area at the centre with Enter', async () => {
    renderWithQuery(<GlobeMap />);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Polygon' })).toBeEnabled());
    fireEvent.keyDown(screen.getByRole('application'), { key: 'Enter' });
    expect(useAppStore.getState().aoi).toMatchObject({
      kind: 'globe',
      label: 'Area around 0.00, 0.00',
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
