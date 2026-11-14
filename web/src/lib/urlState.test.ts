import { renderHook } from '@testing-library/react';
import { useAppStore } from '../state/useAppStore';
import { useUrlSync } from '../state/useUrlSync';
import { circleAoi } from './circle';
import { FIRE_REGIONS, regionAoi } from './regions';
import {
  decodeGeometry,
  decodeState,
  encodeGeometry,
  encodeState,
  type ShareState,
} from './urlState';

const BASE: ShareState = {
  aoi: null,
  start: null,
  end: null,
  referenceYears: null,
  selected: null,
  mode: 'harmonized',
  scale: 'linear',
  calendarView: 'count',
};

const roundTrip = (s: ShareState) => decodeState(new URLSearchParams(encodeState(s).toString()));

describe('URL state', () => {
  it('omits defaults', () => {
    expect(encodeState(BASE).toString()).toBe('');
  });

  it('round-trips dates, reference years, month and view options', () => {
    const s: ShareState = {
      ...BASE,
      start: '2010-01',
      end: '2020-12',
      referenceYears: [2005, 2015],
      selected: { year: 2016, month: 9 },
      mode: 'raw',
      scale: 'log',
      calendarView: 'anomaly',
    };
    expect(roundTrip(s)).toEqual({
      start: '2010-01',
      end: '2020-12',
      referenceYears: [2005, 2015],
      selected: { year: 2016, month: 9 },
      mode: 'raw',
      scale: 'log',
      calendarView: 'anomaly',
    });
  });

  it('restores fire regions, circles and drawn polygons', () => {
    const region = regionAoi(FIRE_REGIONS[0]!);
    expect(encodeState({ ...BASE, aoi: region }).get('region')).toBe(FIRE_REGIONS[0]!.id);
    expect(roundTrip({ ...BASE, aoi: region }).aoi?.regionId).toBe(FIRE_REGIONS[0]!.id);

    const circle = circleAoi(-2, 113, 120, 'Circle');
    const c = roundTrip({ ...BASE, aoi: circle }).aoi!;
    expect(c.circle).toEqual({ lat: -2, lon: 113, radiusKm: 120 });
    expect(c.label).toBe('Circle');

    const polygon = {
      type: 'Polygon' as const,
      coordinates: [
        [
          [104.123456, -2],
          [108, -2],
          [108, 2],
          [104.123456, 2],
          [104.123456, -2],
        ],
      ],
    };
    const d = roundTrip({
      ...BASE,
      aoi: { kind: 'draw', geometry: polygon, areaKm2: 1, label: 'Drawn area' },
    }).aoi!;
    expect(d.kind).toBe('draw');
    expect(d.geometry.coordinates[0]![0]).toEqual([104.1235, -2]);
    expect(d.areaKm2).toBeGreaterThan(190_000);
  });

  it('ignores invalid values', () => {
    const bad = decodeState(
      new URLSearchParams('start=2020-13&ref=2020-2010&circle=95,0,10&aoi=%%%&mode=x'),
    );
    expect(bad).toEqual({});
    expect(decodeGeometry('not-base64!')).toBeNull();
    expect(encodeGeometry({ type: 'Polygon', coordinates: [] })).toBeTruthy();
  });
});

describe('useUrlSync', () => {
  it('restores the view from the URL and keeps the URL updated', async () => {
    window.history.replaceState(
      null,
      '',
      '/?region=id-riau&start=2015-01&view=anomaly&month=2015-09',
    );
    useAppStore.setState({ ...BASE });
    renderHook(() => useUrlSync());
    const state = useAppStore.getState();
    expect(state.aoi?.regionId).toBe('id-riau');
    expect(state.start).toBe('2015-01');
    expect(state.calendarView).toBe('anomaly');
    expect(state.selected).toEqual({ year: 2015, month: 9 });

    useAppStore.getState().setMode('raw');
    await new Promise((r) => setTimeout(r, 250));
    expect(window.location.search).toContain('mode=raw');
    expect(window.location.search).toContain('region=id-riau');
  });
});
