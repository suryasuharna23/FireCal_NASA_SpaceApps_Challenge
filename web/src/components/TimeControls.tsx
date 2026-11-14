import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { apiGet, useMeta } from '../api/client';
import { useT } from '../i18n';
import { monthNames } from '../lib/months';
import { numberToYm, ymToNumber } from '../lib/time';
import { useAppStore, type ViewMode } from '../state/useAppStore';
import { useGlobeMonth } from '../state/useGlobeMonth';

/** Milliseconds per animation frame (one month). */
export const STEP_MS = 450;
/** The animation starts in January 2001 (FR-W-25, T-44). */
export const ANIMATION_START = '2001-01';

const toYm = (n: number) => {
  const [year, month] = numberToYm(n).split('-').map(Number);
  return { year: year!, month: month! };
};

/**
 * Single time source for the globe and calendar (FR-W-25): year slider, month picker
 * and a play button that animates month by month, plus the harmonized/raw toggle that
 * applies to the globe, calendar and charts at once (FR-W-26).
 */
export function TimeControls() {
  const { t, lang } = useT();
  const meta = useMeta().data;
  const month = useGlobeMonth();
  const setSelected = useAppStore((s) => s.setSelected);
  const mode = useAppStore((s) => s.mode);
  const setMode = useAppStore((s) => s.setMode);
  const queryClient = useQueryClient();
  const [playing, setPlaying] = useState(false);

  const first = meta?.start_month
    ? Math.max(ymToNumber(meta.start_month), ymToNumber(ANIMATION_START))
    : null;
  const last = meta?.end_month ? ymToNumber(meta.end_month) : null;

  useEffect(() => {
    if (!playing || first === null || last === null) return;
    const id = window.setInterval(() => {
      const { selected } = useAppStore.getState();
      const current = selected ? selected.year * 12 + selected.month - 1 : last;
      const next = current >= last ? null : current + 1;
      if (next === null) {
        setPlaying(false);
        return;
      }
      setSelected(toYm(next));
      // Warm the cache a few months ahead so the animation stays smooth.
      for (let k = 1; k <= 3 && next + k <= last; k++) {
        const ym = toYm(next + k);
        void queryClient.prefetchQuery({
          queryKey: ['/globe', ym.year, ym.month, useAppStore.getState().mode],
          queryFn: () => apiGet('/globe', { ...ym, mode: useAppStore.getState().mode }),
          staleTime: 30 * 60 * 1000,
        });
      }
    }, STEP_MS);
    return () => window.clearInterval(id);
  }, [playing, first, last, setSelected, queryClient]);

  if (!month || first === null || last === null) return null;

  const names = monthNames(lang, 'long');
  const current = month.year * 12 + month.month - 1;
  const firstYear = toYm(first).year;
  const lastYear = toYm(last).year;

  const go = (n: number) => setSelected(toYm(Math.min(Math.max(n, first), last)));
  const togglePlay = () => {
    if (!playing && current >= last) go(first); // restart from January 2001
    setPlaying((p) => !p);
  };

  return (
    <div className="time-controls" role="group" aria-label={t('timectl.label')}>
      <button
        type="button"
        className="btn btn--primary btn--small time-controls__play"
        aria-pressed={playing}
        onClick={togglePlay}
      >
        {playing ? t('timectl.pause') : t('timectl.play')}
      </button>
      <label className="time-controls__slider">
        <span className="sr-only">{t('timectl.year')}</span>
        <input
          type="range"
          min={firstYear}
          max={lastYear}
          step={1}
          value={month.year}
          aria-valuetext={`${names[month.month - 1]} ${month.year}`}
          onChange={(e) => go(Number(e.target.value) * 12 + month.month - 1)}
        />
        <span className="time-controls__ticks" aria-hidden="true">
          <span>{firstYear}</span>
          <span>{lastYear}</span>
        </span>
      </label>
      <label className="time-controls__month">
        <span className="sr-only">{t('timectl.month')}</span>
        <select
          value={month.month}
          onChange={(e) => go(month.year * 12 + Number(e.target.value) - 1)}
        >
          {names.map((name, i) => {
            const n = month.year * 12 + i;
            return (
              <option key={name} value={i + 1} disabled={n < first || n > last}>
                {name}
              </option>
            );
          })}
        </select>
      </label>
      <div className="segmented" role="group" aria-label={t('timectl.values')}>
        {(['harmonized', 'raw'] as ViewMode[]).map((m) => (
          <button
            key={m}
            type="button"
            className="btn btn--small"
            aria-pressed={mode === m}
            onClick={() => setMode(m)}
          >
            {t(m === 'raw' ? 'globe.raw' : 'globe.harmonized')}
          </button>
        ))}
      </div>
      <span className="sr-only" aria-live="polite">
        {playing ? `${names[month.month - 1]} ${month.year}` : ''}
      </span>
    </div>
  );
}
