import type { MessageKey } from '../i18n';

export const DEFAULT_START = '2001-01';
export const DEFAULT_REFERENCE: [number, number] = [2003, 2022];

const MONTH = /^\d{4}-(0[1-9]|1[0-2])$/;

export function ymToNumber(ym: string): number {
  const [y, m] = ym.split('-').map(Number);
  return y! * 12 + (m! - 1);
}

export function numberToYm(n: number): string {
  const y = Math.floor(n / 12);
  return `${y}-${String((n % 12) + 1).padStart(2, '0')}`;
}

export interface DataRange {
  start: string; // first data month, e.g. 2000-11
  end: string; // latest month
}

/** Defaults from the FRD: 2001-01 .. latest month, reference 2003-2022 (FR-W-05/06). */
export function defaults(range: DataRange, reference?: [number, number]) {
  const start = ymToNumber(DEFAULT_START) < ymToNumber(range.start) ? range.start : DEFAULT_START;
  const [r0, r1] = reference ?? DEFAULT_REFERENCE;
  const first = Number(range.start.slice(0, 4));
  const last = Number(range.end.slice(0, 4));
  return {
    start,
    end: range.end,
    reference: [Math.max(r0, first), Math.min(r1, last)] as [number, number],
  };
}

export type TimeErrors = Partial<Record<'start' | 'end' | 'reference', MessageKey>>;

export function validateTime(
  value: { start: string; end: string; reference: [number, number] },
  range: DataRange,
): TimeErrors {
  const errors: TimeErrors = {};
  const lo = ymToNumber(range.start);
  const hi = ymToNumber(range.end);
  if (!MONTH.test(value.start)) errors.start = 'time.err.format';
  else if (ymToNumber(value.start) < lo || ymToNumber(value.start) > hi)
    errors.start = 'time.err.outside';
  if (!MONTH.test(value.end)) errors.end = 'time.err.format';
  else if (ymToNumber(value.end) < lo || ymToNumber(value.end) > hi)
    errors.end = 'time.err.outside';
  if (!errors.start && !errors.end && ymToNumber(value.start) > ymToNumber(value.end))
    errors.end = 'time.err.order';
  const [r0, r1] = value.reference;
  const first = Number(range.start.slice(0, 4));
  const last = Number(range.end.slice(0, 4));
  if (!(r0 <= r1)) errors.reference = 'time.err.refOrder';
  else if (r0 < first || r1 > last) errors.reference = 'time.err.refOutside';
  return errors;
}

export function monthLabel(ym: string, lang: string): string {
  const [y, m] = ym.split('-').map(Number);
  return new Date(Date.UTC(y!, m! - 1, 1)).toLocaleDateString(lang === 'en' ? 'en-GB' : 'id-ID', {
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  });
}
