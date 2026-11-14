import { fireEvent, screen } from '@testing-library/react';
import { defaults, validateTime } from '../lib/time';
import { useAppStore } from '../state/useAppStore';
import { META_OK, mockFetch, renderWithQuery } from '../test/render';
import { TimePanel } from './TimePanel';

const RANGE = { start: '2000-11', end: '2026-11' };

beforeEach(() => {
  useAppStore.setState({ start: null, end: null, referenceYears: null });
  mockFetch({ '/meta': META_OK });
});
afterEach(() => vi.unstubAllGlobals());

describe('time rules', () => {
  it('defaults to 2001-01 .. latest month and 2003-2022', () => {
    expect(defaults(RANGE)).toEqual({ start: '2001-01', end: '2026-11', reference: [2003, 2022] });
    expect(defaults({ start: '2011-01', end: '2020-12' })).toEqual({
      start: '2011-01',
      end: '2020-12',
      reference: [2011, 2020],
    });
  });

  it('rejects ranges outside the data and reversed ranges', () => {
    const ok = { start: '2005-01', end: '2010-12', reference: [2003, 2022] as [number, number] };
    expect(validateTime(ok, RANGE)).toEqual({});
    expect(validateTime({ ...ok, start: '1999-01' }, RANGE).start).toBe('time.err.outside');
    expect(validateTime({ ...ok, end: '2027-01' }, RANGE).end).toBe('time.err.outside');
    expect(validateTime({ ...ok, start: '2012-01' }, RANGE).end).toBe('time.err.order');
    expect(validateTime({ ...ok, reference: [2020, 2010] }, RANGE).reference).toBe(
      'time.err.refOrder',
    );
  });
});

describe('TimePanel', () => {
  it('shows defaults and applies a valid range and reference years', async () => {
    renderWithQuery(<TimePanel />);
    const start = await screen.findByLabelText('Start month');
    expect(start).toHaveValue('2001-01');
    expect(screen.getByLabelText('End month')).toHaveValue('2026-11');

    fireEvent.change(start, { target: { value: '2010-01' } });
    fireEvent.change(screen.getByLabelText('From'), { target: { value: '2005' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));
    const state = useAppStore.getState();
    expect(state.start).toBe('2010-01');
    expect(state.end).toBeNull(); // still the default
    expect(state.referenceYears).toEqual([2005, 2022]);
  });

  it('rejects an invalid range with a clear message', async () => {
    renderWithQuery(<TimePanel />);
    fireEvent.change(await screen.findByLabelText('Start month'), { target: { value: '1998-05' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }));
    expect(
      screen.getByText(/outside the available data \(2000-11 – 2026-11\)/),
    ).toBeInTheDocument();
    expect(useAppStore.getState().start).toBeNull();
  });
});
