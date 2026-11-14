import { fireEvent, screen } from '@testing-library/react';
import { circleAoi, maxRadiusKm, validateCircle } from '../lib/circle';
import { useAppStore } from '../state/useAppStore';
import { META_OK, mockFetch, renderWithQuery } from '../test/render';
import { CircleForm } from './CircleForm';

beforeEach(() => {
  useAppStore.setState({ aoi: null });
  mockFetch({ '/meta': META_OK });
});
afterEach(() => vi.unstubAllGlobals());

describe('validateCircle', () => {
  it('validates coordinate ranges and radius', () => {
    expect(validateCircle({ lat: '91', lon: '0', radius: '10' }, 1e6).errors.lat).toBeDefined();
    expect(validateCircle({ lat: '0', lon: '-181', radius: '10' }, 1e6).errors.lon).toBeDefined();
    expect(validateCircle({ lat: '0', lon: '0', radius: '0' }, 1e6).errors.radius).toBe(
      'circle.err.radius',
    );
    expect(validateCircle({ lat: '0', lon: '0', radius: '600' }, 1e6).errors.radius).toBe(
      'circle.err.radiusMax',
    );
    expect(validateCircle({ lat: '-1,5', lon: '113.9', radius: '50' }, 1e6).value).toEqual({
      lat: -1.5,
      lon: 113.9,
      radiusKm: 50,
    });
  });

  it('builds a circle whose area matches pi r^2', () => {
    const aoi = circleAoi(0, 110, 100);
    expect(aoi.areaKm2).toBeGreaterThan(Math.PI * 100 ** 2 * 0.98);
    expect(aoi.areaKm2).toBeLessThan(Math.PI * 100 ** 2 * 1.01);
    expect(maxRadiusKm(1e6)).toBeCloseTo(564.19, 1);
  });
});

describe('CircleForm', () => {
  it('sets a circular AOI from valid input', () => {
    renderWithQuery(<CircleForm />);
    fireEvent.change(screen.getByLabelText('Radius (km)'), { target: { value: '75' } });
    fireEvent.click(screen.getByRole('button', { name: 'Pakai lingkaran' }));
    const aoi = useAppStore.getState().aoi;
    expect(aoi?.kind).toBe('circle');
    expect(aoi?.circle).toEqual({ lat: -1.5, lon: 113.9, radiusKm: 75 });
  });

  it('shows field errors and keeps the AOI unchanged for invalid input', () => {
    renderWithQuery(<CircleForm />);
    fireEvent.change(screen.getByLabelText('Lintang'), { target: { value: '120' } });
    fireEvent.click(screen.getByRole('button', { name: 'Pakai lingkaran' }));
    expect(screen.getByText(/Lintang harus/)).toBeInTheDocument();
    expect(screen.getByLabelText('Lintang')).toHaveAttribute('aria-invalid', 'true');
    expect(useAppStore.getState().aoi).toBeNull();
  });
});
