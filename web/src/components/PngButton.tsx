import { useState } from 'react';
import { useT } from '../i18n';

/** Small "PNG" action button with busy and error states (FR-W-18). */
export function PngButton({ onExport, label }: { onExport: () => Promise<void>; label: string }) {
  const { t } = useT();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      await onExport();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button
        type="button"
        className="btn btn--small"
        aria-label={label}
        title={error ?? label}
        disabled={busy}
        onClick={run}
      >
        {busy ? '…' : t('png.button')}
      </button>
      {error && (
        <span className="sr-only" role="alert">
          {error}
        </span>
      )}
    </>
  );
}
