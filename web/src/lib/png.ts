import { saveBlob } from './download';

/** Pixel ratio of exported images (FR-W-18: at least 2x). */
export const EXPORT_SCALE = 2;
export const ATTRIBUTION = 'Data: NASA FIRMS (MODIS C6.1 & VIIRS 375 m) · FireCal';

const BG = '#0b1022';
const FG = '#e8edff';
const MUTED = '#9aa6c8';
const ZERO = '#18213f';
const PAD = 20;
const HEADER = 58;
const FOOTER = 30;

export interface PngFrame {
  title: string;
  subtitle: string;
}

/** Canvas can't resolve CSS variables, so map the theme's zero colour to a hex value. */
export const canvasColor = (c: string) => (c.startsWith('var(') ? ZERO : c);

/** Lay out the framed image size (CSS pixels) around a body of the given size. */
export function frameSize(bodyWidth: number, bodyHeight: number) {
  return { width: bodyWidth + PAD * 2, height: bodyHeight + HEADER + FOOTER };
}

/**
 * Draw title, subtitle (AOI + range), body and FIRMS attribution on a 2x canvas and
 * save it as PNG. ``drawBody`` paints into the body box in CSS-pixel coordinates.
 */
export async function exportFramedPng(
  frame: PngFrame,
  body: { width: number; height: number; draw: (ctx: CanvasRenderingContext2D) => void },
  filename: string,
): Promise<void> {
  const { width, height } = frameSize(body.width, body.height);
  const canvas = document.createElement('canvas');
  canvas.width = width * EXPORT_SCALE;
  canvas.height = height * EXPORT_SCALE;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Canvas is not available in this browser');
  ctx.scale(EXPORT_SCALE, EXPORT_SCALE);
  ctx.fillStyle = BG;
  ctx.fillRect(0, 0, width, height);

  ctx.fillStyle = FG;
  ctx.font = '600 17px "Space Grotesk", Inter, sans-serif';
  ctx.fillText(frame.title, PAD, 28);
  ctx.fillStyle = MUTED;
  ctx.font = '12px Inter, sans-serif';
  ctx.fillText(frame.subtitle, PAD, 46);

  ctx.save();
  ctx.translate(PAD, HEADER);
  body.draw(ctx);
  ctx.restore();

  ctx.fillStyle = MUTED;
  ctx.font = '11px Inter, sans-serif';
  ctx.fillText(ATTRIBUTION, PAD, height - 11);

  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/png'));
  if (!blob) throw new Error('Could not create the PNG');
  saveBlob(blob, filename);
}

/** Load a data URL (e.g. from ECharts getDataURL) as an image. */
export function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('Could not render the chart image'));
    img.src = src;
  });
}

export interface CalendarCell {
  year: number;
  month: number;
  color: string;
}

/** Geometry of the calendar drawing, shared by the drawer and its tests. */
export function calendarLayout(years: number) {
  const label = 40;
  const header = 16;
  const cellW = 30;
  const cellH = 14;
  const gap = 2;
  return {
    label,
    header,
    cellW,
    cellH,
    gap,
    width: label + 12 * (cellW + gap),
    height: header + years * (cellH + gap),
  };
}

/** Paint the year x month grid (same colours as on screen) for PNG export. */
export function drawCalendar(
  ctx: CanvasRenderingContext2D,
  cells: CalendarCell[],
  months: string[],
): void {
  const years = [...new Set(cells.map((c) => c.year))].sort((a, b) => a - b);
  const L = calendarLayout(years.length);
  ctx.font = '10px Inter, sans-serif';
  ctx.fillStyle = MUTED;
  ctx.textAlign = 'center';
  months.forEach((m, i) => ctx.fillText(m, L.label + i * (L.cellW + L.gap) + L.cellW / 2, 10));
  ctx.textAlign = 'right';
  years.forEach((y, r) =>
    ctx.fillText(String(y), L.label - 6, L.header + r * (L.cellH + L.gap) + L.cellH - 3),
  );
  ctx.textAlign = 'left';
  for (const c of cells) {
    const r = years.indexOf(c.year);
    ctx.fillStyle = canvasColor(c.color);
    ctx.fillRect(
      L.label + (c.month - 1) * (L.cellW + L.gap),
      L.header + r * (L.cellH + L.gap),
      L.cellW,
      L.cellH,
    );
  }
}
