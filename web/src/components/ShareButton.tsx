import { useState } from 'react';
import { useT } from '../i18n';
import { shareUrl } from '../state/useUrlSync';

/** Copies a link that restores the same area, dates and view (US-08). */
export function ShareButton() {
  const { t } = useT();
  const [copied, setCopied] = useState<'idle' | 'ok' | 'fail'>('idle');

  const copy = async () => {
    const url = shareUrl();
    try {
      await navigator.clipboard.writeText(url);
      setCopied('ok');
    } catch {
      window.prompt(t('share.manual'), url);
      setCopied('fail');
    }
    window.setTimeout(() => setCopied('idle'), 2500);
  };

  return (
    <>
      <button type="button" className="share-btn" onClick={copy}>
        {copied === 'ok' ? t('share.copied') : t('share.button')}
      </button>
      <span className="sr-only" aria-live="polite">
        {copied === 'ok' ? t('share.copied') : ''}
      </span>
    </>
  );
}
