import { useEffect } from 'react';
import { decodeState, encodeState } from '../lib/urlState';
import { useAppStore } from './useAppStore';

/** Current shareable URL for the app state. */
export function shareUrl(): string {
  const query = encodeState(useAppStore.getState()).toString();
  return `${window.location.origin}${window.location.pathname}${query ? `?${query}` : ''}`;
}

/**
 * Restore the view from the URL once, then mirror every state change into the URL with
 * `history.replaceState` so the address bar is always a shareable link (FR-W-19).
 */
export function useUrlSync() {
  useEffect(() => {
    const restored = decodeState(new URLSearchParams(window.location.search));
    if (Object.keys(restored).length) useAppStore.setState(restored);

    let timer: number | undefined;
    const write = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        const next = shareUrl();
        if (next !== window.location.href) window.history.replaceState(null, '', next);
      }, 150);
    };
    write();
    const unsubscribe = useAppStore.subscribe(write);
    return () => {
      unsubscribe();
      window.clearTimeout(timer);
    };
  }, []);
}
