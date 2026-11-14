import './test/mapMocks';
import { fireEvent, screen } from '@testing-library/react';
import App from './App';
import { META_OK, mockFetch, renderWithQuery } from './test/render';

afterEach(() => vi.unstubAllGlobals());

describe('App shell', () => {
  it('renders header, map/control/result regions and FIRMS attribution', async () => {
    mockFetch({ '/meta': META_OK });
    renderWithQuery(<App />);
    expect(screen.getByRole('heading', { level: 1, name: 'FireCal' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Globe dan peta area' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Pengaturan area dan waktu' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Kalender dan analitik' })).toBeInTheDocument();
    expect(screen.getByText(/NASA FIRMS/)).toBeInTheDocument();
  });

  it('shows data freshness and the provisional NRT badge', async () => {
    mockFetch({ '/meta': META_OK });
    renderWithQuery(<App />);
    expect(await screen.findByText('Data NRT belum final')).toBeInTheDocument();
    expect(screen.getByText(/abc123/)).toBeInTheDocument();
  });

  it('warns when the last FIRMS update failed', async () => {
    mockFetch({ '/meta': { ...META_OK, nrt: { ...META_OK.nrt, ok: false } } });
    renderWithQuery(<App />);
    expect(await screen.findByText(/Pembaruan FIRMS terakhir gagal/)).toBeInTheDocument();
  });

  it('shows an alert when the API is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    renderWithQuery(<App />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Server data tidak dapat dihubungi');
  });

  it('switches to the methodology page', () => {
    mockFetch({ '/meta': META_OK });
    renderWithQuery(<App />);
    fireEvent.click(screen.getByRole('button', { name: 'Metodologi' }));
    expect(screen.getByRole('heading', { level: 2, name: 'Metodologi' })).toBeInTheDocument();
  });
});
