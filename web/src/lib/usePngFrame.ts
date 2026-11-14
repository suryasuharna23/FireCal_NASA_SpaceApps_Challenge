import { useT } from '../i18n';
import { useAppStore } from '../state/useAppStore';
import { formatKm2 } from './aoi';

/** Subtitle (AOI name, area and date range) and filename stem for exported images. */
export function usePngFrame() {
  const { lang } = useT();
  const aoi = useAppStore((s) => s.aoi);
  return (title: string, range: { start: string; end: string }, slug: string) => ({
    frame: {
      title,
      subtitle: `${aoi?.label ?? 'Area'} · ${aoi ? formatKm2(aoi.areaKm2, lang) : ''} · ${range.start} to ${range.end}`,
    },
    filename: `firecal_${slug}_${range.start}_${range.end}.png`,
  });
}
