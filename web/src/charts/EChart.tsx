import { useEffect, useRef } from 'react';
import { echarts, type EChartsOption } from './echarts';

interface EChartProps {
  option: EChartsOption;
  height?: number;
  ariaLabel: string;
  /** Receives the chart instance (used for PNG export). */
  onReady?: (chart: echarts.ECharts | null) => void;
}

/** Minimal React wrapper around an ECharts instance with resize handling. */
export function EChart({ option, height = 260, ariaLabel, onReady }: EChartProps) {
  const el = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const ready = useRef(onReady);
  ready.current = onReady;

  useEffect(() => {
    if (!el.current) return;
    const instance = echarts.init(el.current, undefined, { renderer: 'canvas' });
    chart.current = instance;
    ready.current?.(instance);
    let observer: ResizeObserver | undefined;
    if (typeof ResizeObserver !== 'undefined') {
      observer = new ResizeObserver(() => instance.resize());
      observer.observe(el.current);
    }
    return () => {
      observer?.disconnect();
      ready.current?.(null);
      instance.dispose();
      chart.current = null;
    };
  }, []);

  useEffect(() => {
    chart.current?.setOption(option, true);
  }, [option]);

  return <div ref={el} className="chart" style={{ height }} role="img" aria-label={ariaLabel} />;
}
