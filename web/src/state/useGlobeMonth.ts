import { useMemo } from 'react';
import { useMeta } from '../api/client';
import { useAppStore } from './useAppStore';

/** Month shown on the globe: the selected month, else the latest month with data. */
export function useGlobeMonth() {
  const selected = useAppStore((s) => s.selected);
  const end = useMeta().data?.end_month;
  return useMemo(() => {
    if (selected) return selected;
    if (!end) return null;
    const [year, month] = end.split('-').map(Number);
    return { year: year!, month: month! };
  }, [selected, end]);
}
