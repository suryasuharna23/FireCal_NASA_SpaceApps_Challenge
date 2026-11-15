import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import { useAppStore } from '../state/useAppStore';
import { AOI, calendarFixture, statsFixture } from '../test/fixtures';
import { META_OK, mockFetch, renderWithQuery } from '../test/render';
import { Climatology } from './Climatology';

const setOption = vi.fn();
vi.mock('../charts/echarts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../charts/echarts')>();
  return {
    ...actual,
    echarts: { init: () => ({ setOption, resize: vi.fn(), dispose: vi.fn() }) },
  };
});

afterEach(() => vi.unstubAllGlobals());

describe('Climatology', () => {
  it('renders the chart from /stats with an accessible description and table', async () => {
    useAppStore.setState({ aoi: AOI, selected: null });
    mockFetch({ '/meta': META_OK, '/stats': statsFixture(), '/calendar': calendarFixture() });
    renderWithQuery(<Climatology />);
    expect(
      await screen.findByRole('img', { name: /Fire season: August, September, October/ }),
    ).toBeInTheDocument();
    expect(setOption).toHaveBeenCalled();
    expect(screen.getByText(/75th percentile of all months \(100\)/)).toBeInTheDocument();
    expect(screen.getByRole('rowheader', { name: 'Sept •' })).toBeInTheDocument();
  });

  it('compares chosen years and follows the map year when requested', async () => {
    useAppStore.setState({ aoi: AOI, selected: null });
    mockFetch({ '/meta': META_OK, '/stats': statsFixture(), '/calendar': calendarFixture() });
    renderWithQuery(<Climatology />);
    await screen.findByRole('img', { name: /Displayed years: 2021/ });

    fireEvent.change(screen.getByLabelText('Focus year'), { target: { value: '2020' } });
    fireEvent.change(screen.getByLabelText('Compare with'), { target: { value: '2019' } });
    await waitFor(() => {
      expect(screen.getByRole('columnheader', { name: '2020' })).toBeInTheDocument();
      expect(screen.getByRole('columnheader', { name: '2019' })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByLabelText('P25–P75'));
    expect(screen.queryByRole('columnheader', { name: 'P25' })).toBeNull();

    fireEvent.change(screen.getByLabelText('Focus year'), { target: { value: 'follow' } });
    act(() => useAppStore.setState({ selected: { year: 2019, month: 9 } }));
    await screen.findByRole('img', { name: /Displayed years: 2019/ });
  });
});
