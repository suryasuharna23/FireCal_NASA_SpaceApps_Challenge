import { useMeta } from '../api/client';
import { useT } from '../i18n';
import { useAppStore } from '../state/useAppStore';

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
  const { data, error, isError, isLoading } = useMeta();
  const scope = useAppStore((s) => s.scope);

  if (isLoading) return <div className="status">{t('status.loading')}</div>;
  if (isError || !data)
    return (
      <div className="status status--error" role="alert">
        Real NASA data could not be loaded.{' '}
        {error instanceof Error ? error.message : t('status.apiDown')}
      </div>
    );
  if (data.status === 'no_data')
    return (
      <div className="status status--error" role="alert">
        {t('status.noData')}
      </div>
    );

  if (scope === 'global') {
    const worldwide = data.global;
    const live = worldwide?.live;
    const failed = live?.status === 'failed' || live?.status === 'missing_key';
    return (
      <div
        className={failed || worldwide?.status !== 'ok' ? 'status status--error' : 'status'}
        role={failed || worldwide?.status !== 'ok' ? 'alert' : 'status'}
      >
        {worldwide?.status === 'ok' ? (
          <>
            <span>
              Worldwide NASA detections · {worldwide.start_date} to{' '}
              <strong>{worldwide.last_acq_date}</strong>
            </span>
            <span className="status__muted">Version {worldwide.data_version}</span>
            {worldwide.provisional && (
              <span className="badge badge--warn">Provisional NASA observations</span>
            )}
            {live?.status === 'updating' && <span>Checking newer worldwide observations…</span>}
            {failed && (
              <strong>
                GLOBAL UPDATE UNAVAILABLE · {live?.detail} Showing saved real observations.
              </strong>
            )}
            {live?.checked_at && (
              <span className="status__muted">
                NASA check attempted {new Date(live.checked_at).toLocaleString(lang)}
              </span>
            )}
            {!live && <span>Saved snapshot · updated through the date shown.</span>}
          </>
        ) : (
          <strong>{worldwide?.detail ?? 'Real global observations are unavailable.'}</strong>
        )}
      </div>
    );
  }

  const updateFailed = data.live?.status === 'failed' || data.live?.status === 'missing_key';
  return (
    <div
      className={updateFailed ? 'status status--error' : 'status'}
      role={updateFailed ? 'alert' : 'status'}
    >
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
      {data.live?.checked_at && (
        <span className="status__muted">
          {data.live.status === 'updated' || data.live.status === 'up_to_date'
            ? 'NASA checked '
            : 'NASA check attempted '}
          {new Date(data.live.checked_at).toLocaleString(lang)}
        </span>
      )}
      {data.live?.status === 'updating' && <span>Checking newer NASA observations…</span>}
      {data.live?.status === 'missing_key' && (
        <strong>
          LIVE UPDATES UNAVAILABLE · NASA access key is missing. Showing saved real observations.
        </strong>
      )}
      {data.live?.status === 'failed' && (
        <strong>
          NASA UPDATE FAILED · Showing last real observations. These are not verified as current.
        </strong>
      )}
      {data.live?.lagging_sources?.map((source) => (
        <span className="badge badge--warn" key={source.source}>
          {source.source.replace('VIIRS_', '').replace('_NRT', '')} available through{' '}
          {source.available_through}
        </span>
      ))}
    </div>
  );
}
