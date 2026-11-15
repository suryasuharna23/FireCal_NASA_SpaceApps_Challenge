import { useEffect } from 'react';
import { decodeState, encodeState } from '../lib/urlState';
import { loadRegionAoi } from '../lib/regions';
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
    const regionId = new URLSearchParams(window.location.search).get('region');
    let cancelled = false;
    let unsubscribe = () => {};
    const startSync = () => {
      if (cancelled) return;
      write();
      unsubscribe = useAppStore.subscribe(write);
    };
    if (regionId) {
      void loadRegionAoi(regionId)
        .then((aoi) => {
          if (!cancelled) useAppStore.setState({ aoi });
        })
        .catch(() => {})
        .finally(startSync);
    } else {
      startSync();
    }
    return () => {
      cancelled = true;
      unsubscribe();
      window.clearTimeout(timer);
    };
  }, []);
}
