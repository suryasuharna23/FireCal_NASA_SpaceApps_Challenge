import { fireEvent, screen } from '@testing-library/react';
import { filenameFrom } from '../lib/download';
import { useAppStore } from '../state/useAppStore';
import { AOI } from '../test/fixtures';
import { META_OK, mockFetch, renderWithQuery } from '../test/render';
import { ExportPanel } from './ExportPanel';

const CSV =
  '# FireCal export\n# Data: NASA FIRMS\n# v\n# g\nyear,month,n_harmonized\n2019,1,3\n2019,2,4\n';

beforeEach(() => {
  useAppStore.setState({ aoi: AOI, start: '2019-01', end: '2019-02', referenceYears: null });
  vi.stubGlobal(
    'URL',
    Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:x'), revokeObjectURL: vi.fn() }),
  );
});
afterEach(() => vi.unstubAllGlobals());

describe('filenameFrom', () => {
  it('reads the attachment filename', () => {
    expect(filenameFrom('attachment; filename="firecal_monthly_2019-01_2019-02.csv"', 'x')).toBe(
      'firecal_monthly_2019-01_2019-02.csv',
    );
    expect(filenameFrom(null, 'fallback.csv')).toBe('fallback.csv');
  });
});

describe('ExportPanel', () => {
  it('downloads the monthly CSV for the active AOI and range with a dated filename', async () => {
    const fetch = mockFetch({
      '/meta': META_OK,
      '/export': new Response(CSV, {
        headers: {
          'Content-Type': 'text/csv',
          'Content-Disposition': 'attachment; filename="firecal_monthly_2019-01_2019-02.csv"',
        },
      }),
    });
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    renderWithQuery(<ExportPanel />);
    fireEvent.click(screen.getByRole('button', { name: 'Monthly CSV' }));

    expect(await screen.findByText(/firecal_monthly_2019-01_2019-02.csv/)).toBeInTheDocument();
    expect(click).toHaveBeenCalled();
    const anchor = click.mock.contexts[0] as HTMLAnchorElement;
    expect(anchor.download).toBe('firecal_monthly_2019-01_2019-02.csv');
    const body = JSON.parse(
      (fetch.mock.calls as unknown as [string, RequestInit][]).find((c) =>
        String(c[0]).endsWith('/export'),
      )![1].body as string,
    );
    expect(body).toMatchObject({ kind: 'monthly', start: '2019-01', end: '2019-02' });
    expect(body.aoi.type).toBe('Polygon');
  });

  it('requests raw points and shows API errors', async () => {
    mockFetch({
      '/meta': META_OK,
      '/export': new Response('{"detail":"Date range is outside the available data"}', {
        status: 422,
      }),
    });
    renderWithQuery(<ExportPanel />);
    fireEvent.click(screen.getByRole('button', { name: 'Raw points CSV' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('outside the available data');
  });

  it('is hidden without an AOI', () => {
    useAppStore.setState({ aoi: null });
    mockFetch({ '/meta': META_OK });
    const { container } = renderWithQuery(<ExportPanel />);
    expect(container).toBeEmptyDOMElement();
  });
});
