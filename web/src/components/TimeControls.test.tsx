import { act, fireEvent, screen } from '@testing-library/react';
import { useAppStore } from '../state/useAppStore';
import { META_OK, mockFetch, renderWithQuery } from '../test/render';
import { STEP_MS, TimeControls } from './TimeControls';

beforeEach(() => {
  useAppStore.setState({
    scope: 'indonesia',
    selected: null,
    mode: 'harmonized',
    playbackPeriod: 'month',
    playbackDay: 1,
    playbackHour: 0,
  });
  mockFetch({ '/meta': META_OK, '/globe': { cells: [], max: 0 } });
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('TimeControls', () => {
  it('switches to the real global window and prevents unavailable corrections and dates', async () => {
    mockFetch({
      '/meta': {
        ...META_OK,
        global: {
          status: 'ok',
          start_date: '2026-08-15',
          start_month: '2026-08',
          end_month: '2026-11',
          last_acq_date: '2026-11-15',
        },
      },
      '/globe': { cells: [], max: 0 },
    });
    renderWithQuery(<TimeControls />);
    const coverage = await screen.findByRole('combobox', { name: 'Data coverage' });
    fireEvent.change(coverage, { target: { value: 'global' } });
    expect(useAppStore.getState().scope).toBe('global');
    expect(useAppStore.getState().mode).toBe('raw');
    expect(screen.getByRole('button', { name: 'Harmonized' })).toBeDisabled();
    expect(screen.getByRole('slider', { name: 'Year' })).toHaveAttribute('min', '2026');
    fireEvent.change(screen.getByRole('combobox', { name: 'Month' }), { target: { value: '8' } });
    fireEvent.change(screen.getByRole('combobox', { name: 'Playback interval' }), {
      target: { value: 'day' },
    });
    expect(useAppStore.getState().playbackDay).toBe(15);
    expect(screen.getByRole('combobox', { name: 'Day' }).querySelector('option')?.value).toBe('15');
    fireEvent.change(coverage, { target: { value: 'indonesia' } });
    expect(screen.getByRole('button', { name: 'Harmonized' })).toBeEnabled();
  });

  it('moves the shared month with the year slider and month picker', async () => {
    renderWithQuery(<TimeControls />);
    const slider = await screen.findByRole('slider', { name: 'Year' });
    expect(slider).toHaveValue('2026');
    fireEvent.change(slider, { target: { value: '2015' } });
    expect(useAppStore.getState().selected).toEqual({ year: 2015, month: 11 });
    fireEvent.change(screen.getByRole('combobox', { name: 'Month' }), { target: { value: '8' } });
    expect(useAppStore.getState().selected).toEqual({ year: 2015, month: 8 });
  });

  it('animates month by month and restarts from January 2001 at the end', async () => {
    renderWithQuery(<TimeControls />);
    const play = await screen.findByRole('button', { name: 'Play' });
    vi.useFakeTimers();
    fireEvent.click(play); // latest month is selected -> restart at 2001-01
    expect(useAppStore.getState().selected).toEqual({ year: 2001, month: 1 });
    act(() => vi.advanceTimersByTime(STEP_MS * 3));
    expect(useAppStore.getState().selected).toEqual({ year: 2001, month: 4 });
    fireEvent.click(screen.getByRole('button', { name: 'Pause' }));
    act(() => vi.advanceTimersByTime(STEP_MS * 3));
    expect(useAppStore.getState().selected).toEqual({ year: 2001, month: 4 });
  });

  it('stops at the latest month', async () => {
    useAppStore.setState({ selected: { year: 2026, month: 10 } });
    renderWithQuery(<TimeControls />);
    const play = await screen.findByRole('button', { name: 'Play' });
    vi.useFakeTimers();
    fireEvent.click(play);
    act(() => vi.advanceTimersByTime(STEP_MS * 4));
    expect(useAppStore.getState().selected).toEqual({ year: 2026, month: 11 });
    expect(screen.getByRole('button', { name: 'Play' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('switches harmonized and raw values for every view', async () => {
    renderWithQuery(<TimeControls />);
    fireEvent.click(await screen.findByRole('button', { name: 'Raw per sensor' }));
    expect(useAppStore.getState().mode).toBe('raw');
    fireEvent.click(screen.getByRole('button', { name: 'Harmonized' }));
    expect(useAppStore.getState().mode).toBe('harmonized');
  });

  it('plays yearly totals and daily acquisition dates', async () => {
    useAppStore.setState({ selected: { year: 2025, month: 11 } });
    renderWithQuery(<TimeControls />);
    const interval = await screen.findByRole('combobox', { name: 'Playback interval' });
    fireEvent.change(interval, { target: { value: 'year' } });
    vi.useFakeTimers();
    fireEvent.click(screen.getByRole('button', { name: 'Play' }));
    act(() => vi.advanceTimersByTime(STEP_MS));
    expect(useAppStore.getState().selected?.year).toBe(2026);
    fireEvent.click(screen.getByRole('button', { name: 'Pause' }));
    fireEvent.change(interval, { target: { value: 'day' } });
    expect(useAppStore.getState().playbackDay).toBe(12);
    fireEvent.change(screen.getByRole('combobox', { name: 'Day' }), { target: { value: '10' } });
    fireEvent.click(screen.getByRole('button', { name: 'Play' }));
    act(() => vi.advanceTimersByTime(STEP_MS));
    expect(useAppStore.getState().playbackDay).toBe(11);
  });
});
