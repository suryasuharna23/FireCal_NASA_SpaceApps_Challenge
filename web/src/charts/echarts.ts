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
import { FONT_BODY } from '../lib/fonts';

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
  strong: '#e8edff',
  grid: 'rgba(148, 168, 255, 0.12)',
  fire: '#ff7a3d',
  amber: '#ffb347',
  orbit: '#5ee7ff',
  band: 'rgba(255, 179, 71, 0.18)',
  critical: 'rgba(255, 90, 50, 0.12)',
  tooltipBg: 'rgba(8, 12, 26, 0.96)',
};

export const baseOption = {
  backgroundColor: 'transparent',
  textStyle: { color: THEME.text, fontFamily: FONT_BODY },
  aria: { enabled: true },
  animationDuration: 400,
  tooltip: {
    trigger: 'axis',
    backgroundColor: THEME.tooltipBg,
    borderColor: 'rgba(148, 168, 255, 0.32)',
    textStyle: { color: THEME.strong, fontSize: 12 },
  },
  legend: { top: 0, textStyle: { color: THEME.text }, itemWidth: 14, itemHeight: 8 },
  grid: { left: 44, right: 12, top: 34, bottom: 28 },
};
