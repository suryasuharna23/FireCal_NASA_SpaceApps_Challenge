import { useId, useRef, useState, type ChangeEvent } from 'react';
import { useMeta } from '../api/client';
import { useT } from '../i18n';
import { DEFAULT_MAX_AOI_KM2, formatKm2 } from '../lib/aoi';
import { parseUpload } from '../lib/geojsonUpload';
import { useAppStore } from '../state/useAppStore';

/** Upload one GeoJSON polygon (≤ 5 MB) as the AOI (FR-W-04). */
export function GeoJsonUpload() {
  const { t, lang } = useT();
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const setAoi = useAppStore((s) => s.setAoi);
  const maxKm2 = useMeta().data?.max_aoi_km2 ?? DEFAULT_MAX_AOI_KM2;
  const [error, setError] = useState<string | null>(null);

  const onFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const result = parseUpload(await file.text(), file.name, file.size, maxKm2);
    if (result.ok) {
      setError(null);
      setAoi(result.aoi);
    } else {
      setError(
        t(result.error, {
          ...result.vars,
          area: result.vars?.area ? formatKm2(Number(result.vars.area), lang) : '',
          max: formatKm2(maxKm2, lang),
        }),
      );
    }
    if (input.current) input.current.value = '';
  };

  return (
    <div className="upload">
      <label htmlFor={id} className="btn btn--small upload__button">
        {t('upload.button')}
      </label>
      <input
        ref={input}
        id={id}
        type="file"
        accept=".geojson,.json,application/geo+json,application/json"
        className="sr-only"
        aria-describedby={`${id}-hint`}
        onChange={onFile}
      />
      <small id={`${id}-hint`} className="muted">
        {t('upload.hint')}
      </small>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
