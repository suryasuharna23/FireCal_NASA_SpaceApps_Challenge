import { useMeta } from '../api/client';
import { useT } from '../i18n';

function formatDate(iso: string | null | undefined, lang: string) {
  if (!iso) return '–';
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleDateString(lang, {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      });
}

/** Data freshness, NRT status and API/FIRMS warnings (FR-W-22, NFR-07). */
export function StatusBar() {
  const { t, lang } = useT();
  const { data, isError, isLoading } = useMeta();

  if (isLoading) return <div className="status">{t('status.loading')}</div>;
  if (isError || !data)
    return (
      <div className="status status--error" role="alert">
        {t('status.apiDown')}
      </div>
    );
  if (data.status === 'no_data')
    return (
      <div className="status status--warn" role="status">
        {t('status.noData')}
      </div>
    );

  return (
    <div className="status" role="status">
      <span>
        {t('status.updated')} <strong>{formatDate(data.last_updated, lang)}</strong>
      </span>
      <span>
        {t('status.latest')} <strong>{formatDate(data.last_acq_date, lang)}</strong>
      </span>
      <span className="status__muted">
        {t('status.version')} {data.data_version}
      </span>
      {data.nrt?.provisional && (
        <span className="badge badge--warn" title={data.nrt.provisional_months.join(', ')}>
          {t('status.provisional')}
        </span>
      )}
      {data.nrt && !data.nrt.ok && (
        <span className="badge badge--error">{t('status.firmsFailed')}</span>
      )}
    </div>
  );
}
