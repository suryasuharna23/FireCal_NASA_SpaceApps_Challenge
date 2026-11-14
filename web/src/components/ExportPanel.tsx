import { useRef, useState } from 'react';
import { useSeriesRequest } from '../api/queries';
import { useT } from '../i18n';
import { formatCount } from '../lib/colors';
import { downloadExport, type ExportKind, type ExportProgress } from '../lib/download';
import { Panel } from './Panel';

type State =
  | { status: 'idle' }
  | { status: 'busy'; kind: ExportKind; progress: ExportProgress }
  | { status: 'done'; filename: string }
  | { status: 'error'; message: string };

/** CSV downloads for the active AOI and date range (FR-W-16, FR-W-17, NFR-02). */
export function ExportPanel() {
  const { t, lang } = useT();
  const request = useSeriesRequest();
  const [state, setState] = useState<State>({ status: 'idle' });
  const abort = useRef<AbortController | null>(null);

  if (!request) return null;

  const start = async (kind: ExportKind) => {
    abort.current = new AbortController();
    setState({ status: 'busy', kind, progress: { bytes: 0, rows: 0 } });
    try {
      const filename = await downloadExport(
        kind,
        request,
        (progress) => setState({ status: 'busy', kind, progress }),
        abort.current.signal,
      );
      setState({ status: 'done', filename });
    } catch (err) {
      if ((err as Error).name === 'AbortError') setState({ status: 'idle' });
      else setState({ status: 'error', message: (err as Error).message });
    }
  };

  const busy = state.status === 'busy';

  return (
    <Panel title={t('panel.export')} id="export">
      <div className="toolbar">
        <button
          type="button"
          className="btn btn--primary btn--small"
          disabled={busy}
          onClick={() => start('monthly')}
        >
          {t('export.monthly')}
        </button>
        <button
          type="button"
          className="btn btn--small"
          disabled={busy}
          onClick={() => start('points')}
        >
          {t('export.points')}
        </button>
        {busy && (
          <button type="button" className="btn btn--small" onClick={() => abort.current?.abort()}>
            {t('export.cancel')}
          </button>
        )}
      </div>
      <p className="muted small">{t('export.hint')}</p>
      <p className="small" role="status" aria-live="polite">
        {state.status === 'busy' &&
          t('export.progress', {
            rows: formatCount(state.progress.rows, lang),
            size: (state.progress.bytes / 1e6).toFixed(1),
          })}
        {state.status === 'done' && t('export.done', { file: state.filename })}
      </p>
      {state.status === 'error' && (
        <p className="form-error" role="alert">
          {state.message}
        </p>
      )}
    </Panel>
  );
}
