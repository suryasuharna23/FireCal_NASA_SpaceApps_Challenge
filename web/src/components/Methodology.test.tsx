import { screen } from '@testing-library/react';
import { META_OK, mockFetch, renderWithQuery } from '../test/render';
import { Methodology } from './Methodology';

afterEach(() => vi.unstubAllGlobals());

describe('Methodology', () => {
  it('explains sources, filters and harmonization with the live validation results', async () => {
    mockFetch({
      '/meta': {
        ...META_OK,
        calibration_period: '2013-01:2021-12',
        validation: {
          test_years: [2016, 2019],
          r: 0.9987,
          bias: 0.0123,
          mae: 27.9,
          meets_target: true,
          limitations: ['lat:boreal: r=0.71 misses the target'],
        },
      },
    });
    renderWithQuery(<Methodology />);
    expect(screen.getByRole('heading', { level: 2, name: 'Methodology' })).toBeInTheDocument();
    for (const name of [
      '1. Data sources',
      '2. Cleaning',
      '4. Harmonization',
      '5. Validation',
      '7. Limitations',
    ]) {
      expect(screen.getByRole('heading', { name })).toBeInTheDocument();
    }
    expect(await screen.findByText('0.999')).toBeInTheDocument();
    expect(screen.getByText('+1.23%')).toBeInTheDocument();
    expect(screen.getByText('Yes')).toBeInTheDocument();
    expect(screen.getByText(/lat:boreal/)).toBeInTheDocument();
    expect(screen.getAllByText(/2016, 2019/).length).toBeGreaterThan(0);
    expect(screen.getByRole('link', { name: 'FIRMS' })).toHaveAttribute(
      'href',
      'https://firms.modaps.eosdis.nasa.gov',
    );
  });
});
