import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { apiGet, apiPost, useMeta } from '../api/client';
import { useT } from '../i18n';
import { monthNames } from '../lib/months';
import { frameFor, frameKey, nextFrame, type PlaybackFrame } from '../lib/playback';
import { numberToYm, ymToNumber } from '../lib/time';
import { useAppStore, type PlaybackPeriod, type ViewMode } from '../state/useAppStore';
import { useGlobeMonth } from '../state/useGlobeMonth';

export const STEP_MS = 900;
export const ANIMATION_START = '2001-01';

const toYm = (n: number) => {
  const [year, month] = numberToYm(n).split('-').map(Number);
  return { year: year!, month: month! };
};

export function TimeControls() {
  const { t, lang } = useT();
  const meta = useMeta().data;
  const month = useGlobeMonth();
  const setSelected = useAppStore((s) => s.setSelected);
  const mode = useAppStore((s) => s.mode);
  const setMode = useAppStore((s) => s.setMode);
  const period = useAppStore((s) => s.playbackPeriod);
  const setPeriod = useAppStore((s) => s.setPlaybackPeriod);
  const day = useAppStore((s) => s.playbackDay);
  const setDay = useAppStore((s) => s.setPlaybackDay);
  const hour = useAppStore((s) => s.playbackHour);
  const setHour = useAppStore((s) => s.setPlaybackHour);
  const queryClient = useQueryClient();
  const [playing, setPlaying] = useState(false);
  const first = meta?.start_month
    ? Math.max(ymToNumber(meta.start_month), ymToNumber(ANIMATION_START))
    : null;
  const last = meta?.end_month ? ymToNumber(meta.end_month) : null;
  const lastAcq = meta?.last_acq_date ?? null;

  useEffect(() => {
    if (!playing || first === null || last === null) return;
    const id = window.setInterval(() => {
      const state = useAppStore.getState();
      const currentMonth = state.selected ?? toYm(last);
      const current = frameFor(
        currentMonth,
        state.playbackPeriod,
        state.playbackDay,
        state.playbackHour,
      );
      const next = nextFrame(current);
      const latest = lastAcq ? new Date(`${lastAcq}T00:00:00Z`) : null;
      const end =
        state.playbackPeriod === 'year' || state.playbackPeriod === 'month'
          ? frameFor(toYm(last), state.playbackPeriod, 1, 0)
          : latest
            ? frameFor(
                { year: latest.getUTCFullYear(), month: latest.getUTCMonth() + 1 },
                state.playbackPeriod,
                latest.getUTCDate(),
                state.playbackPeriod === 'hour' ? 23 : 0,
              )
            : frameFor(toYm(last), state.playbackPeriod, 31, 23);
      if (frameKey(next) > frameKey(end)) {
        setPlaying(false);
        return;
      }
      state.setSelected({ year: next.year, month: next.month });
      if (next.day !== undefined) state.setPlaybackDay(next.day);
      if (next.hour !== undefined) state.setPlaybackHour(next.hour);
      let future: PlaybackFrame = nextFrame(next);
      for (
        let k = 1;
        k <= 2 && frameKey(future) <= frameKey(end);
        k++, future = nextFrame(future)
      ) {
        const warm = future;
        void queryClient.prefetchQuery({
          queryKey: ['/globe', warm, state.mode],
          queryFn: () => apiGet('/globe', { ...warm, mode: state.mode }),
          staleTime: 30 * 60 * 1000,
        });
        if (k === 1 && state.aoi && warm.period !== 'year') {
          const body = { aoi: state.aoi.geometry, ...warm };
          void queryClient.prefetchQuery({
            queryKey: ['/points', body],
            queryFn: () => apiPost('/points', body),
            staleTime: 10 * 60 * 1000,
          });
        }
      }
    }, STEP_MS);
    return () => window.clearInterval(id);
  }, [playing, first, last, lastAcq, queryClient]);

  if (!month || first === null || last === null) return null;
  const names = monthNames(lang, 'long');
  const current = month.year * 12 + month.month - 1;
  const firstYear = toYm(first).year;
  const lastYear = toYm(last).year;
  const maxDay = new Date(Date.UTC(month.year, month.month, 0)).getUTCDate();
  const latest = lastAcq ? new Date(`${lastAcq}T00:00:00Z`) : null;
  const dayLimit = latest && current === last ? Math.min(maxDay, latest.getUTCDate()) : maxDay;
  const selectedFrame = frameFor(month, period, day, hour);
  const lastFrame =
    period === 'year' || period === 'month'
      ? frameFor(toYm(last), period, 1, 0)
      : latest
        ? frameFor(
            { year: latest.getUTCFullYear(), month: latest.getUTCMonth() + 1 },
            period,
            latest.getUTCDate(),
            period === 'hour' ? 23 : 0,
          )
        : frameFor(toYm(last), period, 31, 23);
  const go = (n: number) => {
    setSelected(toYm(Math.min(Math.max(n, first), last)));
    setDay(1);
    setHour(0);
  };
  const changePeriod = (next: PlaybackPeriod) => {
    setPlaying(false);
    setPeriod(next);
    setDay(current === last && latest ? latest.getUTCDate() : 1);
    setHour(0);
  };
  const togglePlay = () => {
    if (!playing && frameKey(selectedFrame) >= frameKey(lastFrame)) {
      if (period === 'year' || period === 'month') go(first);
      else if (period === 'day') setDay(1);
      else setHour(0);
    }
    setPlaying((p) => !p);
  };
  const label =
    period === 'year'
      ? String(month.year)
      : `${period === 'day' || period === 'hour' ? `${selectedFrame.day} ` : ''}${names[month.month - 1]} ${month.year}${period === 'hour' ? ` ${String(hour).padStart(2, '0')}:00 UTC` : ''}`;

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
      <label className="time-controls__period">
        <span className="sr-only">{t('timectl.period')}</span>
        <select value={period} onChange={(e) => changePeriod(e.target.value as PlaybackPeriod)}>
          {(['year', 'month', 'day', 'hour'] as PlaybackPeriod[]).map((p) => (
            <option key={p} value={p} disabled={(p === 'day' || p === 'hour') && !lastAcq}>
              {t(
                p === 'year'
                  ? 'timectl.yearly'
                  : p === 'month'
                    ? 'timectl.monthly'
                    : p === 'day'
                      ? 'timectl.daily'
                      : 'timectl.hourly',
              )}
            </option>
          ))}
        </select>
      </label>
      <label className="time-controls__slider">
        <span className="sr-only">{t('timectl.year')}</span>
        <input
          type="range"
          min={firstYear}
          max={lastYear}
          step={1}
          value={month.year}
          aria-valuetext={label}
          onChange={(e) => go(Number(e.target.value) * 12 + month.month - 1)}
        />
        <span className="time-controls__ticks" aria-hidden="true">
          <span>{firstYear}</span>
          <span>{lastYear}</span>
        </span>
      </label>
      {period !== 'year' && (
        <label className="time-controls__month">
          <span className="sr-only">{t('timectl.month')}</span>
          <select
            value={month.month}
            onChange={(e) => go(month.year * 12 + Number(e.target.value) - 1)}
          >
            {names.map((name, i) => (
              <option
                key={name}
                value={i + 1}
                disabled={month.year * 12 + i < first || month.year * 12 + i > last}
              >
                {name}
              </option>
            ))}
          </select>
        </label>
      )}
      {(period === 'day' || period === 'hour') && (
        <label className="time-controls__day">
          <span className="sr-only">{t('timectl.day')}</span>
          <select
            value={Math.min(day, dayLimit)}
            onChange={(e) => {
              setDay(Number(e.target.value));
              setHour(0);
            }}
          >
            {Array.from({ length: dayLimit }, (_, i) => (
              <option key={i} value={i + 1}>
                {i + 1}
              </option>
            ))}
          </select>
        </label>
      )}
      {period === 'hour' && (
        <label className="time-controls__hour">
          <span className="sr-only">{t('timectl.hour')}</span>
          <select value={hour} onChange={(e) => setHour(Number(e.target.value))}>
            {Array.from({ length: 24 }, (_, i) => (
              <option key={i} value={i}>
                {String(i).padStart(2, '0')}:00 UTC
              </option>
            ))}
          </select>
        </label>
      )}
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
        {playing ? label : ''}
      </span>
    </div>
  );
}
