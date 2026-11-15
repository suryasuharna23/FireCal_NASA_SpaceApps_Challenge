import { useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useMeta } from '../api/client';

/** Refresh existing views after the server atomically publishes a newer dataset. */
export function useDataVersionRefresh() {
  const meta = useMeta().data;
  // Empty new months or revised point details can change without a new grid hash.
  const version = meta?.data_version
    ? `${meta.data_version}|${meta.end_month ?? ''}|${meta.last_updated ?? ''}|${meta.global?.data_version ?? ''}`
    : null;
  const previous = useRef<string | null | undefined>(undefined);
  const queries = useQueryClient();
  useEffect(() => {
    if (previous.current && version && previous.current !== version) {
      void queries.invalidateQueries({ predicate: (query) => query.queryKey[0] !== 'meta' });
    }
    if (version) previous.current = version;
  }, [version, queries]);
}
