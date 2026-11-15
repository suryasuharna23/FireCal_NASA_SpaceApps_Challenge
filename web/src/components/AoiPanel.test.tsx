import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { useAppStore } from '../state/useAppStore';
import { META_OK, mockFetch, renderWithQuery } from '../test/render';
import { REGION_ROUTES } from '../test/regions';
import { AoiPanel } from './AoiPanel';
import { EmptyState } from './EmptyState';

beforeEach(() => {
  useAppStore.setState({ aoi: null, scope: 'indonesia' });
  mockFetch({ '/meta': META_OK, ...REGION_ROUTES });
});
afterEach(() => vi.unstubAllGlobals());

describe('AoiPanel', () => {
  it('lets the global view inspect a location outside Indonesia', async () => {
    useAppStore.setState({ scope: 'global' });
    renderWithQuery(<AoiPanel />);
    // The worldwide scope shows the region list with its own coordinate form
    // (main's UI) plus the circle form, so scope the queries to the circle form.
    const circleForm = screen.getByRole('form', { name: 'Circular area from coordinates' });
    fireEvent.change(within(circleForm).getByLabelText('Latitude'), { target: { value: '-12' } });
    fireEvent.change(within(circleForm).getByLabelText('Longitude'), { target: { value: '17' } });
    fireEvent.click(within(circleForm).getByRole('button', { name: 'Use circle' }));
    await waitFor(() => expect(useAppStore.getState().aoi?.circle?.lon).toBe(17));
    expect(useAppStore.getState().aoi?.circle?.lat).toBe(-12);
  });

  it('offers all saved provinces and highlights the chosen boundary', async () => {
    renderWithQuery(<AoiPanel />);
    await waitFor(() => expect(screen.getAllByRole('button', { pressed: false })).toHaveLength(34));
    expect(screen.getByText('33 provinces available')).toBeVisible();
    expect(screen.queryByRole('tab')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Polygon' })).toBeNull();
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'Riau' } });
    expect(screen.getAllByRole('button', { pressed: false })).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: /Riau/ }));
    await waitFor(() => expect(useAppStore.getState().aoi?.regionId).toBe('NE1-IDN-492'));
    expect(screen.getByText('Riau, Indonesia')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Clear area' }));
    expect(useAppStore.getState().aoi).toBeNull();
  });
});

describe('EmptyState', () => {
  it('starts with the same three province choices', async () => {
    renderWithQuery(<EmptyState />);
    expect(screen.getAllByRole('listitem')).toHaveLength(3);
    await waitFor(() => expect(screen.getAllByRole('button')).toHaveLength(3));
    fireEvent.click(screen.getByRole('button', { name: /Riau/ }));
    await waitFor(() => expect(useAppStore.getState().aoi?.regionId).toBe('NE1-IDN-492'));
  });
});
