/**
 * Self-hosted variable fonts (Fontsource), shared by CSS, ECharts and canvas exports.
 *
 * - Space Grotesk: display — brand identity, headings, big numbers.
 * - Figtree: interface/body — high-legibility UI text, buttons, forms, descriptions.
 * - JetBrains Mono: data — years, ticks, telemetry, coordinates and tabular figures.
 */
export const FONT_DISPLAY = "'Space Grotesk Variable', 'Space Grotesk', system-ui, sans-serif";
export const FONT_BODY =
  "'Figtree Variable', 'Figtree', 'Plus Jakarta Sans Variable', 'Plus Jakarta Sans', system-ui, -apple-system, 'Segoe UI', sans-serif";
export const FONT_MONO = "'JetBrains Mono Variable', 'JetBrains Mono', ui-monospace, monospace";

/** Canvas needs fonts to be loaded before drawing text into an exported image. */
export async function fontsReady(): Promise<void> {
  try {
    await document.fonts?.ready;
  } catch {
    /* older browsers: fall back to whatever is available */
  }
}
