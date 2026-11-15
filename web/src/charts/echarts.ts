/** Tree-shaken ECharts build with only the pieces FireCal uses. */
import { BarChart, LineChart } from 'echarts/charts';
import {
  AriaComponent,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  TooltipComponent,
} from 'echarts/components';
import * as echarts from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';

echarts.use([
  LineChart,
  BarChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  AriaComponent,
  CanvasRenderer,
]);

export { echarts };
export type EChartsOption = echarts.EChartsCoreOption;

/** Shared dark "space" styling for every chart. */
export const THEME = {
  text: '#9aa6c8',
  strong: '#ffffff',
  grid: 'rgba(58, 65, 134, 0.25)',
  fire: '#ff6b1a',
  amber: '#ff9f1c',
  orbit: '#71b3f7',
  band: 'rgba(255, 159, 28, 0.18)',
  critical: 'rgba(224, 64, 6, 0.16)',
  tooltipBg: 'rgba(14, 16, 34, 0.96)',
};

export const baseOption = {
  backgroundColor: 'transparent',
  textStyle: { color: THEME.text, fontFamily: 'Inter, system-ui, sans-serif' },
  aria: { enabled: true },
  animationDuration: 400,
  tooltip: {
    trigger: 'axis',
    backgroundColor: THEME.tooltipBg,
    borderColor: '#3a4186',
    textStyle: { color: THEME.strong, fontSize: 12 },
  },
  legend: { top: 0, textStyle: { color: THEME.text }, itemWidth: 14, itemHeight: 8 },
  grid: { left: 44, right: 12, top: 34, bottom: 28 },
};
