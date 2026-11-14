import { useState, type FormEvent } from 'react';
import { useMeta } from '../api/client';
import { useT } from '../i18n';
import { circleAoi, maxRadiusKm, validateCircle, type CircleErrors } from '../lib/circle';
import { DEFAULT_MAX_AOI_KM2 } from '../lib/aoi';
import { useAppStore } from '../state/useAppStore';

/** Latitude / longitude / radius form producing a circular AOI (FR-W-02). */
export function CircleForm() {
  const { t } = useT();
  const setAoi = useAppStore((s) => s.setAoi);
  const maxKm2 = useMeta().data?.max_aoi_km2 ?? DEFAULT_MAX_AOI_KM2;
  const [values, setValues] = useState({ lat: '-1.5', lon: '113.9', radius: '100' });
  const [errors, setErrors] = useState<CircleErrors>({});

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const result = validateCircle(values, maxKm2);
    setErrors(result.errors);
    if (result.value) {
      const { lat, lon, radiusKm } = result.value;
      setAoi(circleAoi(lat, lon, radiusKm, t('aoi.circleLabel', { r: radiusKm, lat, lon })));
    }
  };

  const field = (name: keyof typeof values, label: string, hint: string) => (
    <div className="field">
      <label htmlFor={`circle-${name}`}>{label}</label>
      <input
        id={`circle-${name}`}
        name={name}
        inputMode="decimal"
        value={values[name]}
        aria-invalid={Boolean(errors[name])}
        aria-describedby={`circle-${name}-note`}
        onChange={(e) => setValues({ ...values, [name]: e.target.value })}
      />
      {errors[name] ? (
        <small id={`circle-${name}-note`} className="field__error">
          {t(errors[name]!, { max: Math.floor(maxRadiusKm(maxKm2)) })}
        </small>
      ) : (
        <small id={`circle-${name}-note`} className="muted">
          {hint}
        </small>
      )}
    </div>
  );

  return (
    <form className="circle-form" onSubmit={submit} noValidate aria-label={t('circle.title')}>
      <div className="field-row">
        {field('lat', t('circle.lat'), '−90 … 90')}
        {field('lon', t('circle.lon'), '−180 … 180')}
        {field('radius', t('circle.radius'), `1 … ${Math.floor(maxRadiusKm(maxKm2))} km`)}
      </div>
      <button type="submit" className="btn btn--primary btn--small">
        {t('circle.apply')}
      </button>
    </form>
  );
}
