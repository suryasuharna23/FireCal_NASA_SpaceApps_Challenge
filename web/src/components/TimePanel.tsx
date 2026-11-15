import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { useMeta } from '../api/client';
import { useT } from '../i18n';
import { defaults, validateTime, type TimeErrors } from '../lib/time';
import { useAppStore } from '../state/useAppStore';
import { Panel } from './Panel';

/** Date range (month-year) and reference years for the historical median (FR-W-05/06). */
export function TimePanel() {
  const { t } = useT();
  const meta = useMeta().data;
  const store = useAppStore();
  const aoi = store.aoi;
  const range = useMemo(
    () =>
      meta?.start_month && meta.end_month ? { start: meta.start_month, end: meta.end_month } : null,
    [meta?.start_month, meta?.end_month],
  );
  const fallback = range ? defaults(range, meta?.default_reference_years) : null;

  const current = {
    start: store.start ?? fallback?.start ?? '',
    end: store.end ?? fallback?.end ?? '',
    reference: store.referenceYears ?? fallback?.reference ?? ([2003, 2022] as [number, number]),
  };
  const [draft, setDraft] = useState(current);
  const [errors, setErrors] = useState<TimeErrors>({});
  const key = `${current.start}|${current.end}|${current.reference.join('-')}`;
  // Re-sync the form when the applied state changes (defaults load, URL restore).
  useEffect(() => setDraft(current), [key]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!range || !fallback) {
    return (
      <Panel title={t('panel.time')}>
        <p className="muted">{t('status.loading')}</p>
      </Panel>
    );
  }

  const years: number[] = [];
  for (let y = Number(range.start.slice(0, 4)); y <= Number(range.end.slice(0, 4)); y++)
    years.push(y);

  const apply = (event: FormEvent) => {
    event.preventDefault();
    const found = validateTime(draft, range);
    setErrors(found);
    if (Object.keys(found).length) return;
    store.setRange(
      draft.start === fallback.start ? null : draft.start,
      draft.end === fallback.end ? null : draft.end,
    );
    const sameRef =
      draft.reference[0] === fallback.reference[0] && draft.reference[1] === fallback.reference[1];
    store.setReferenceYears(sameRef ? null : draft.reference);
  };

  const reset = () => {
    setErrors({});
    store.setRange(null, null);
    store.setReferenceYears(null);
  };

  const note = (name: keyof TimeErrors, hint: string) =>
    errors[name] ? (
      <small id={`time-${name}-note`} className="field__error">
        {t(errors[name]!, { start: range.start, end: range.end })}
      </small>
    ) : (
      <small id={`time-${name}-note`} className="muted">
        {hint}
      </small>
    );

  return (
    <Panel title={t('panel.time')} id="time-panel">
      <p className="muted small">
        {aoi?.label ?? 'Every Indonesian region'} · {range.start} to {range.end}
      </p>
      <form onSubmit={apply} noValidate aria-label={t('panel.time')}>
        <div className="field-row field-row--2">
          <div className="field">
            <label htmlFor="time-start">{t('time.start')}</label>
            <input
              id="time-start"
              type="month"
              min={range.start}
              max={range.end}
              value={draft.start}
              aria-invalid={Boolean(errors.start)}
              aria-describedby="time-start-note"
              onChange={(e) => setDraft({ ...draft, start: e.target.value })}
            />
            {note('start', t('time.defaultStart', { v: fallback.start }))}
          </div>
          <div className="field">
            <label htmlFor="time-end">{t('time.end')}</label>
            <input
              id="time-end"
              type="month"
              min={range.start}
              max={range.end}
              value={draft.end}
              aria-invalid={Boolean(errors.end)}
              aria-describedby="time-end-note"
              onChange={(e) => setDraft({ ...draft, end: e.target.value })}
            />
            {note('end', t('time.defaultEnd'))}
          </div>
        </div>
        <fieldset className="fieldset">
          <legend>{t('time.reference')}</legend>
          <div className="field-row field-row--2">
            {([0, 1] as const).map((i) => (
              <div className="field" key={i}>
                <label htmlFor={`time-ref-${i}`}>{t(i === 0 ? 'time.from' : 'time.to')}</label>
                <select
                  id={`time-ref-${i}`}
                  value={draft.reference[i]}
                  aria-invalid={Boolean(errors.reference)}
                  aria-describedby="time-reference-note"
                  onChange={(e) => {
                    const reference = [...draft.reference] as [number, number];
                    reference[i] = Number(e.target.value);
                    setDraft({ ...draft, reference });
                  }}
                >
                  {years.map((y) => (
                    <option key={y} value={y}>
                      {y}
                    </option>
                  ))}
                </select>
              </div>
            ))}
          </div>
          {note('reference', t('time.referenceHint'))}
        </fieldset>
        <div className="toolbar">
          <button type="submit" className="btn btn--primary btn--small">
            {t('time.apply')}
          </button>
          <button type="button" className="btn btn--small" onClick={reset}>
            {t('time.reset')}
          </button>
        </div>
      </form>
    </Panel>
  );
}
