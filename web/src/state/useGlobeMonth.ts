import { useMemo } from 'react';
import { useMeta } from '../api/client';
import { useAppStore } from './useAppStore';

/** Month shown on the globe: the selected month, else the latest month with data. */
export function useGlobeMonth() {
  const selected = useAppStore((s) => s.selected);
  const scope = useAppStore((s) => s.scope);
  const data = useMeta().data;
  const active = scope === 'global' ? data?.global : data;
  const end = active?.end_month;
  const start = active?.start_month;
  return useMemo(() => {
    if (
      selected &&
      (scope !== 'global' ||
        (start &&
          end &&
          `${selected.year}-${String(selected.month).padStart(2, '0')}` >= start &&
          `${selected.year}-${String(selected.month).padStart(2, '0')}` <= end))
    )
      return selected;
    if (!end) return null;
    const [year, month] = end.split('-').map(Number);
    return { year: year!, month: month! };
  }, [selected, end, start, scope]);
}
