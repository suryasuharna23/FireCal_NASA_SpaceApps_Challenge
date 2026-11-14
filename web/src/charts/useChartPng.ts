import { useCallback, useRef } from 'react';
import { EXPORT_SCALE, exportFramedPng, loadImage } from '../lib/png';
import { usePngFrame } from '../lib/usePngFrame';
import type { echarts } from './echarts';

/** Keeps the ECharts instance and exports it as a framed 2x PNG (FR-W-18). */
export function useChartPng() {
  const chart = useRef<echarts.ECharts | null>(null);
  const pngFrame = usePngFrame();
  const onReady = useCallback((instance: echarts.ECharts | null) => {
    chart.current = instance;
  }, []);

  const exportPng = async (title: string, range: { start: string; end: string }, slug: string) => {
    const instance = chart.current;
    if (!instance) throw new Error('The chart is not ready yet');
    const url = instance.getDataURL({
      type: 'png',
      pixelRatio: EXPORT_SCALE,
      backgroundColor: '#0b1022',
    });
    const img = await loadImage(url);
    const width = img.width / EXPORT_SCALE;
    const height = img.height / EXPORT_SCALE;
    const { frame, filename } = pngFrame(title, range, slug);
    await exportFramedPng(
      frame,
      { width, height, draw: (ctx) => ctx.drawImage(img, 0, 0, width, height) },
      filename,
    );
  };

  return { onReady, exportPng };
}
