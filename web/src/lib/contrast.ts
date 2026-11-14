/**
 * Colour accessibility helpers (T-36, NFR-03, NFR-04): WCAG contrast ratio and
 * colour-vision-deficiency simulation (Machado, Oliveira & Fernandes 2009, severity 1).
 */

export type RGB = [number, number, number];

export function parseColor(color: string): RGB {
  const hex = color.trim().match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
  if (hex) {
    const h = hex[1]!.length === 3 ? [...hex[1]!].map((c) => c + c).join('') : hex[1]!;
    return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16)) as RGB;
  }
  const rgb = color.match(/rgba?\(([^)]+)\)/i);
  if (rgb)
    return rgb[1]!
      .split(',')
      .slice(0, 3)
      .map((v) => Number(v.trim())) as RGB;
  throw new Error(`Unsupported colour ${color}`);
}

const toLinear = (c: number) => {
  const s = c / 255;
  return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
};
const toSrgb = (l: number) => {
  const v = l <= 0.0031308 ? 12.92 * l : 1.055 * l ** (1 / 2.4) - 0.055;
  return Math.round(Math.min(1, Math.max(0, v)) * 255);
};

/** WCAG relative luminance. */
export function luminance(color: string | RGB): number {
  const [r, g, b] = (typeof color === 'string' ? parseColor(color) : color).map(toLinear);
  return 0.2126 * r! + 0.7152 * g! + 0.0722 * b!;
}

/** WCAG contrast ratio (1–21). */
export function contrast(a: string | RGB, b: string | RGB): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi! + 0.05) / (lo! + 0.05);
}

/** Composite a translucent colour over an opaque background. */
export function over(fg: string, alpha: number, bg: string): RGB {
  const f = parseColor(fg);
  const b = parseColor(bg);
  return f.map((c, i) => Math.round(c * alpha + b[i]! * (1 - alpha))) as RGB;
}

const MATRICES = {
  protanopia: [
    [0.152286, 1.052583, -0.204868],
    [0.114503, 0.786281, 0.099216],
    [-0.003882, -0.048116, 1.051998],
  ],
  deuteranopia: [
    [0.367322, 0.860646, -0.227968],
    [0.280085, 0.672501, 0.047413],
    [-0.01182, 0.04294, 0.968881],
  ],
} as const;

export type Deficiency = keyof typeof MATRICES;

/** Simulate how a colour looks with protanopia or deuteranopia. */
export function simulate(color: string | RGB, type: Deficiency): RGB {
  const lin = (typeof color === 'string' ? parseColor(color) : color).map(toLinear);
  return MATRICES[type].map((row) =>
    toSrgb(row[0] * lin[0]! + row[1] * lin[1]! + row[2] * lin[2]!),
  ) as RGB;
}
