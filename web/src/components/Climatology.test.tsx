import { screen } from '@testing-library/react';
import { useAppStore } from '../state/useAppStore';
import { AOI, statsFixture } from '../test/fixtures';
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
    useAppStore.setState({ aoi: AOI });
    mockFetch({ '/meta': META_OK, '/stats': statsFixture() });
    renderWithQuery(<Climatology />);
    expect(
      await screen.findByRole('img', { name: /Fire season: August, September, October/ }),
    ).toBeInTheDocument();
    expect(setOption).toHaveBeenCalled();
    expect(screen.getByText(/75th percentile of all months \(100\)/)).toBeInTheDocument();
    expect(screen.getByRole('rowheader', { name: 'Sept •' })).toBeInTheDocument();
  });
});
