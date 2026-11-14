import { fireEvent, screen, within } from '@testing-library/react';
import { countScale } from '../lib/colors';
import { useAppStore } from '../state/useAppStore';
import { AOI, calendarFixture } from '../test/fixtures';
import { META_OK, mockFetch, renderWithQuery } from '../test/render';
import { Calendar } from './Calendar';

beforeEach(() => {
  useAppStore.setState({
    aoi: AOI,
    scale: 'linear',
    mode: 'harmonized',
    selected: null,
    calendarView: 'count',
  });
});
afterEach(() => vi.unstubAllGlobals());

describe('countScale', () => {
  it('maps zero to the neutral colour and grows with the value', () => {
    const color = countScale(100, 'linear');
    expect(color(0)).toBe('var(--zero-cell)');
    expect(color(10)).not.toBe(color(100));
    expect(countScale(100, 'log')(10)).not.toBe(color(10));
  });
});

describe('Calendar', () => {
  it('asks for an AOI first', () => {
    useAppStore.setState({ aoi: null });
    mockFetch({ '/meta': META_OK });
    renderWithQuery(<Calendar />);
    expect(screen.getByText(/Select an area/)).toBeInTheDocument();
  });

  it('renders a year x month grid from /calendar with a legend', async () => {
    const fetch = mockFetch({ '/meta': META_OK, '/calendar': calendarFixture(2019, 2021, 6) });
    renderWithQuery(<Calendar />);
    const grid = await screen.findByRole('grid');
    expect(
      within(grid)
        .getAllByRole('rowheader')
        .map((r) => r.textContent),
    ).toEqual(['2019', '2020', '2021']);
    expect(grid.querySelectorAll('button[role="gridcell"]')).toHaveLength(12 + 12 + 6);
    expect(screen.getByLabelText(/September 2019: 200 hotspots/)).toBeInTheDocument();
    expect(screen.getByLabelText('Legend')).toBeInTheDocument();

    const body = JSON.parse(
      (fetch.mock.calls as unknown as [string, RequestInit][]).find((c) =>
        String(c[0]).endsWith('/calendar'),
      )![1].body as string,
    );
    expect(body.aoi.type).toBe('Polygon');
  });

  it('switches to log scale and selects a month on click', async () => {
    mockFetch({ '/meta': META_OK, '/calendar': calendarFixture() });
    renderWithQuery(<Calendar />);
    const cell = await screen.findByLabelText(/March 2020/);
    const linear = cell.style.background;
    fireEvent.click(screen.getByRole('button', { name: 'Log' }));
    expect(screen.getByLabelText(/March 2020/).style.background).not.toBe(linear);

    fireEvent.click(screen.getByLabelText(/March 2020/));
    expect(useAppStore.getState().selected).toEqual({ year: 2020, month: 3 });
  });

  it('shows a tooltip with harmonized, per-sensor, interval and anomaly values', async () => {
    mockFetch({ '/meta': META_OK, '/calendar': calendarFixture() });
    renderWithQuery(<Calendar />);
    fireEvent.mouseEnter(await screen.findByLabelText(/^September 2020/));
    const tip = screen.getByRole('tooltip');
    expect(tip).toHaveTextContent('September 2020');
    expect(tip).toHaveTextContent('Harmonized205');
    expect(tip).toHaveTextContent('MODIS205');
    expect(tip).toHaveTextContent('VIIRS615');
    expect(tip).toHaveTextContent('90% interval205–205');
    expect(tip).toHaveTextContent('+3%');
    expect(tip).toHaveTextContent('median 200');
    expect(tip).toHaveTextContent('Source: MODIS');
  });

  it('switches to the diverging anomaly view', async () => {
    mockFetch({ '/meta': META_OK, '/calendar': calendarFixture() });
    renderWithQuery(<Calendar />);
    const cell = await screen.findByLabelText(/^September 2021/);
    const before = cell.style.background;
    fireEvent.click(screen.getByRole('button', { name: 'Anomaly' }));
    expect(useAppStore.getState().calendarView).toBe('anomaly');
    expect(screen.getByLabelText(/^September 2021/).style.background).not.toBe(before);
    expect(screen.getByText(/red = above, blue = below/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Log' })).toBeNull();
  });

  it('shows API errors', async () => {
    mockFetch({
      '/meta': META_OK,
      '/calendar': new Response('{"detail":"AOI is too large"}', { status: 422 }),
    });
    renderWithQuery(<Calendar />);
    expect(await screen.findByRole('alert')).toHaveTextContent('AOI is too large');
  });
});
