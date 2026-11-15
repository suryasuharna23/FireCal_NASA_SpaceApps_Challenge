import { fireEvent, screen, waitFor } from '@testing-library/react';
import { useAppStore } from '../state/useAppStore';
import { AOI, statsFixture } from '../test/fixtures';
import { META_OK, renderWithQuery } from '../test/render';
import { AiInsight } from './AiInsight';

afterEach(() => vi.unstubAllGlobals());

it('sends a user question with the selected area and displays the answer', async () => {
  useAppStore.setState({ aoi: AOI, scope: 'indonesia' });
  const requests: Record<string, unknown>[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input)).pathname;
      const body =
        path === '/meta'
          ? META_OK
          : path === '/stats'
            ? statsFixture()
            : { text: 'The data cannot establish a cause.', model: 'test', data_version: 'abc123' };
      if (path === '/insights') requests.push(JSON.parse(String(init?.body)));
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }),
  );
  renderWithQuery(<AiInsight />);
  const input = screen.getByRole('textbox', { name: 'Your question' });
  fireEvent.change(input, { target: { value: 'What caused these detections?' } });
  const ask = await screen.findByRole('button', { name: 'Ask FireCal' });
  await waitFor(() => expect(ask).toBeEnabled());
  fireEvent.click(ask);
  expect(await screen.findByText('The data cannot establish a cause.')).toBeInTheDocument();
  await waitFor(() => expect(requests).toHaveLength(1));
  expect(requests[0]).toMatchObject({
    region_name: AOI.label,
    question: 'What caused these detections?',
  });
});
