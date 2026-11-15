import { fireEvent, screen, waitFor } from '@testing-library/react';
import { useAppStore } from '../state/useAppStore';
import { META_OK, mockFetch, renderWithQuery } from '../test/render';
import { REGION_ROUTES } from '../test/regions';
import { AoiPanel } from './AoiPanel';
import { EmptyState } from './EmptyState';

beforeEach(() => {
  useAppStore.setState({ aoi: null });
  mockFetch({ '/meta': META_OK, ...REGION_ROUTES });
});
afterEach(() => vi.unstubAllGlobals());

describe('AoiPanel', () => {
  it('offers all saved provinces and highlights the chosen boundary', async () => {
    renderWithQuery(<AoiPanel />);
    await waitFor(() => expect(screen.getAllByRole('button')).toHaveLength(34));
    expect(screen.getByText('33 provinces available')).toBeVisible();
    expect(screen.queryByRole('tab')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Polygon' })).toBeNull();
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'Riau' } });
    expect(screen.getAllByRole('button')).toHaveLength(1);
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
