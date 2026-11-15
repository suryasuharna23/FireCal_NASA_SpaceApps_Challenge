import { screen } from '@testing-library/react';
import { META_OK, mockFetch, renderWithQuery } from '../test/render';
import { StatusBar } from './StatusBar';

it('shows checked time and a lagging source without claiming every platform is current', async () => {
  mockFetch({
    '/meta': {
      ...META_OK,
      live: {
        status: 'updated',
        checked_at: '2026-11-15T04:38:09Z',
        lagging_sources: [{ source: 'VIIRS_SNPP_NRT', available_through: '2026-11-02' }],
      },
    },
  });
  renderWithQuery(<StatusBar />);
  expect(await screen.findByText(/NASA checked/)).toBeVisible();
  expect(screen.getByText(/available through 2026-11-02/)).toBeVisible();
});
