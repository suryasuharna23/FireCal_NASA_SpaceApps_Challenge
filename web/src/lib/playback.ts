import type { PlaybackPeriod, YearMonth } from '../state/useAppStore';

export interface PlaybackFrame extends YearMonth {
  period: PlaybackPeriod;
  day?: number;
  hour?: number;
}

export function frameFor(ym: YearMonth, period: PlaybackPeriod, day: number, hour: number): PlaybackFrame {
  const maxDay = new Date(Date.UTC(ym.year, ym.month, 0)).getUTCDate();
  return {
    ...ym,
    period,
    ...(period === 'day' || period === 'hour' ? { day: Math.min(day, maxDay) } : {}),
    ...(period === 'hour' ? { hour } : {}),
  };
}

export function frameDate(frame: PlaybackFrame): Date {
  return new Date(Date.UTC(frame.year, frame.month - 1, frame.day ?? 1, frame.hour ?? 0));
}

export function nextFrame(frame: PlaybackFrame): PlaybackFrame {
  const date = frameDate(frame);
  if (frame.period === 'year') date.setUTCFullYear(date.getUTCFullYear() + 1);
  if (frame.period === 'month') date.setUTCMonth(date.getUTCMonth() + 1);
  if (frame.period === 'day') date.setUTCDate(date.getUTCDate() + 1);
  if (frame.period === 'hour') date.setUTCHours(date.getUTCHours() + 1);
  return { year: date.getUTCFullYear(), month: date.getUTCMonth() + 1,
    period: frame.period, ...(frame.day !== undefined ? { day: date.getUTCDate() } : {}),
    ...(frame.hour !== undefined ? { hour: date.getUTCHours() } : {}) };
}

export function frameKey(frame: PlaybackFrame): number {
  if (frame.period === 'year') return frame.year;
  if (frame.period === 'month') return frame.year * 12 + frame.month;
  return frameDate(frame).getTime();
}
