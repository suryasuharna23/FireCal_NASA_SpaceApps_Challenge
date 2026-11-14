import { fireEvent, screen } from '@testing-library/react';
import { useAppStore } from '../state/useAppStore';
import { META_OK, mockFetch, renderWithQuery } from '../test/render';
import { AoiPanel } from './AoiPanel';
import { EmptyState } from './EmptyState';

beforeEach(() => {
  useAppStore.setState({ aoi: null });
  mockFetch({ '/meta': META_OK });
});
afterEach(() => vi.unstubAllGlobals());

describe('AoiPanel tabs', () => {
  it('shows one way to choose an area at a time, fire regions first', () => {
    renderWithQuery(<AoiPanel />);
    expect(screen.getByRole('tab', { name: 'Fire regions' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    expect(screen.getByRole('button', { name: /South Sumatra/ })).toBeVisible();
    expect(screen.queryByLabelText('Latitude')).toBeNull();

    fireEvent.click(screen.getByRole('tab', { name: 'Circle' }));
    expect(screen.getByLabelText('Latitude')).toBeVisible();
    expect(screen.queryByRole('button', { name: /South Sumatra/ })).toBeNull();
  });

  it('moves between tabs with the arrow keys (ARIA tabs pattern)', () => {
    renderWithQuery(<AoiPanel />);
    const first = screen.getByRole('tab', { name: 'Fire regions' });
    first.focus();
    fireEvent.keyDown(first, { key: 'ArrowRight' });
    const search = screen.getByRole('tab', { name: 'Search' });
    expect(search).toHaveAttribute('aria-selected', 'true');
    expect(search).toHaveFocus();
    fireEvent.keyDown(search, { key: 'End' });
    expect(screen.getByRole('tab', { name: 'Upload' })).toHaveAttribute('aria-selected', 'true');
    fireEvent.keyDown(screen.getByRole('tab', { name: 'Upload' }), { key: 'ArrowRight' });
    expect(screen.getByRole('tab', { name: 'Fire regions' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
  });
});

describe('EmptyState', () => {
  it('explains the three steps and starts with one click', () => {
    renderWithQuery(<EmptyState />);
    expect(
      screen.getByRole('heading', { name: 'Pick an area to see its fire calendar' }),
    ).toBeVisible();
    expect(screen.getAllByRole('listitem')).toHaveLength(3);
    fireEvent.click(screen.getByRole('button', { name: /Cerrado/ }));
    expect(useAppStore.getState().aoi?.regionId).toBe('br-cerrado');
  });
});
