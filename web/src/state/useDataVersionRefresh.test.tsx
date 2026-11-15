import { act, render, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { META_OK } from '../test/render';
import { useDataVersionRefresh } from './useDataVersionRefresh';

function Probe() {
  useDataVersionRefresh();
  return null;
}

it.each([
  { data_version: 'second' },
  { end_month: '2026-12' },
  { last_updated: '2026-11-15T04:38:09Z' },
])('invalidates results after published dataset metadata changes: %j', async (change) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(['meta'], { ...META_OK, data_version: 'first' });
  client.setQueryData(['/calendar', 'area'], { value: 1 });
  render(
    <QueryClientProvider client={client}>
      <Probe />
    </QueryClientProvider>,
  );
  expect(client.getQueryState(['/calendar', 'area'])?.isInvalidated).toBe(false);
  await act(async () => {
    client.setQueryData(['meta'], { ...META_OK, data_version: 'first', ...change });
  });
  await waitFor(() =>
    expect(client.getQueryState(['/calendar', 'area'])?.isInvalidated).toBe(true),
  );
  expect(client.getQueryState(['meta'])?.isInvalidated).toBe(false);
  client.clear();
});
