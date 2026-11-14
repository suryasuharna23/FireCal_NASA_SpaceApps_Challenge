import { screen } from '@testing-library/react';
import { useAppStore } from '../state/useAppStore';
import { AOI, statsFixture } from '../test/fixtures';
import { META_OK, mockFetch, renderWithQuery } from '../test/render';
import { Kpi } from './Kpi';

afterEach(() => vi.unstubAllGlobals());

describe('Kpi', () => {
  it('asks for an AOI first', () => {
    useAppStore.setState({ aoi: null });
    mockFetch({ '/meta': META_OK });
    renderWithQuery(<Kpi />);
    expect(screen.getByText(/Select an area/)).toBeInTheDocument();
  });

  it('shows total, peak month, highest year and the latest month vs median', async () => {
    useAppStore.setState({ aoi: AOI });
    mockFetch({ '/meta': META_OK, '/stats': statsFixture() });
    renderWithQuery(<Kpi />);

    const current = await screen.findByRole('heading', { name: 'December 2021 vs usual' });
    const card = current.closest('article')!;
    expect(card).toHaveTextContent('+20%');
    expect(card).toHaveTextContent('Above usual');
    expect(card).toHaveTextContent('18 vs median 15');
    expect(card).toHaveTextContent('P70');
    expect(card).toHaveClass('kpi--hot');
    expect(card).toHaveTextContent('NRT data not final');

    expect(screen.getByText('3,900')).toBeInTheDocument();
    expect(screen.getByText('September')).toBeInTheDocument();
    expect(screen.getByText(/Fire season: August, September, October/)).toBeInTheDocument();
    expect(screen.getByText('2019')).toBeInTheDocument();
    expect(screen.getByText(/1,800 hotspots that year/)).toBeInTheDocument();
  });

  it('labels months close to the median as normal', async () => {
    const stats = statsFixture();
    stats.summary.current = { ...stats.summary.current!, anomaly_pct: -4, provisional: false };
    useAppStore.setState({ aoi: AOI });
    mockFetch({ '/meta': META_OK, '/stats': stats });
    renderWithQuery(<Kpi />);
    const card = (await screen.findByText(/Close to usual/)).closest('article')!;
    expect(card).toHaveClass('kpi--neutral');
  });
});
