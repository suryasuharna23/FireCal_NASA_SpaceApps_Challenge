/**
 * FireCal Design System - Color Variables & Tokens
 * NASA Space Apps Challenge · Cyber Techno & Deep Space Theme
 * 
 * Sourced directly from Figma File: FIRECAL - NASA Space Apps Challenge (Node #12:10396 & #12:10198)
 */

export const colors = {
  // 1. High-Contrast Accents (Solar Flare / Fire)
  flare: {
    ember: '#E04006',   // Extreme Fire & Thermal peak (rgb: 224, 64, 6)
    orange: '#FF6B1A',  // Primary CTA, Active Fire status (rgb: 255, 107, 26)
    amber: '#FF9F1C',   // Interactive Hover, Warm flame (rgb: 255, 159, 28)
    yellow: '#FFD23F',  // Peak Hotspots, Solar glow (rgb: 255, 210, 63)
  },

  // 2. Earth Observation & Bio (Flora)
  flora: {
    light: '#5FD678',    // Logomark leaf start / Vegetative canopy (rgb: 95, 214, 120)
    emerald: '#2CBC84',  // Logomark leaf end / Deep rainforest (rgb: 44, 188, 132)
  },
  earth: {
    blue: '#0180E7',     // Satellite telemetry & Earth water (rgb: 1, 128, 231)
  },

  // 3. Dominant Dark Palette (Indigo Void & Deep Space)
  space: {
    void: '#05050C',       // Surface Void / Deepest orbital dark backdrop (rgb: 5, 5, 12)
    base: '#090A15',       // Surface Base / Main app background (rgb: 9, 10, 21)
    panel: '#0E1022',      // Surface Panel / Cards & sidebar containers (rgb: 14, 16, 34)
    elevated: '#151833',   // Surface Elevated / Popovers, active items (rgb: 21, 24, 51)
    overlay: '#1C2044',    // Surface Overlay / Modals, floating sheets (rgb: 28, 32, 68)
    navyDark: '#031044',   // Deep Cosmic Navy (rgb: 3, 16, 68)
    sapphire: '#051D87',   // Deep Sapphire Accent (rgb: 5, 29, 135)
    atmosphere: '#71B3F7', // Atmosphere Sky Accent (rgb: 113, 179, 247)
  },

  // 4. Cyber Techno Borders & Contours
  border: {
    subtle: '#232752',            // Low-contrast panel border (rgb: 35, 39, 82)
    techno: '#3A4186',            // Medium cyber-techno border (rgb: 58, 65, 134)
    glow: '#5B66D6',              // Cyber glow & active focus ring (rgb: 91, 102, 214)
    canvasSubtle: 'rgba(255, 255, 255, 0.1)', // Subtle white 10% stroke
  },

  // 5. Calendar Heatmap Intensity Scale (Wildfire Tracking)
  heatmap: {
    zero: '#12162B', // 0 detections (No thermal anomaly)
    low: '#4A2612',  // 1 - 50 detections (Low fire alert, text: #FFA56E)
    mid: '#8A380A',  // 50 - 200 detections (Moderate activity, text: #FFD0B3)
    high: '#FF6B1A', // 200 - 500 detections (High outbreak, text: #05050C)
    peak: '#FFD23F', // 500+ detections (Extreme emergency peak, text: #05050C)
  },

  // 6. Typography & Contrast Colors
  text: {
    primary: '#FFFFFF',       // Heading & high-contrast text
    secondary: '#F8F8F8',     // Soft off-white text
    muted: '#9AA6C8',         // Metadata, secondary descriptions
    onFlare: '#05050C',       // Dark text on flare orange/yellow buttons
    canvasNeutral: '#444444', // Figma section backdrop
  },
};

// Gradients
export const gradients = {
  button: 'linear-gradient(180deg, #FF9F1C 0%, #FF6B1A 50%, #E04006 100%)',
  thermal: 'linear-gradient(180deg, #FF9F1C 0%, #E04006 100%)',
  flameMark: 'linear-gradient(163deg, #FF9F1C 34%, #FF6B1A 89%, #E04006 100%)',
  foliageMark: 'linear-gradient(180deg, #5FD678 12%, #2CBC84 77%)',
  spaceSurface: 'linear-gradient(180deg, #12152E 0%, #0A0C18 100%)',
};

// Semantic role mapping for ease of use in UI components
export const semanticColors = {
  background: {
    app: colors.space.base,
    surface: colors.space.panel,
    elevated: colors.space.elevated,
    modal: colors.space.overlay,
    void: colors.space.void,
  },
  brand: {
    primary: colors.flare.orange,
    secondary: colors.flare.amber,
    danger: colors.flare.ember,
    highlight: colors.flare.yellow,
    gradient: gradients.button,
  },
  text: {
    primary: colors.text.primary,
    secondary: colors.text.secondary,
    muted: colors.text.muted,
    inverse: colors.text.onFlare,
  },
  border: {
    subtle: colors.border.subtle,
    focus: colors.border.glow,
    accent: colors.border.techno,
  },
};

// Convert to CSS Custom Properties object or string
export const cssVariables = {
  '--fc-flare-ember': colors.flare.ember,
  '--fc-flare-orange': colors.flare.orange,
  '--fc-flare-amber': colors.flare.amber,
  '--fc-flare-yellow': colors.flare.yellow,
  '--fc-flora-light': colors.flora.light,
  '--fc-flora-emerald': colors.flora.emerald,
  '--fc-earth-blue': colors.earth.blue,
  '--fc-space-void': colors.space.void,
  '--fc-space-base': colors.space.base,
  '--fc-space-panel': colors.space.panel,
  '--fc-space-elevated': colors.space.elevated,
  '--fc-space-overlay': colors.space.overlay,
  '--fc-space-navy-dark': colors.space.navyDark,
  '--fc-space-sapphire': colors.space.sapphire,
  '--fc-atmosphere-sky': colors.space.atmosphere,
  '--fc-border-subtle': colors.border.subtle,
  '--fc-border-techno': colors.border.techno,
  '--fc-border-glow': colors.border.glow,
  '--fc-text-primary': colors.text.primary,
  '--fc-text-secondary': colors.text.secondary,
  '--fc-text-muted': colors.text.muted,
  '--fc-gradient-button': gradients.button,
  '--fc-gradient-thermal': gradients.thermal,
};

// SVG Assets in repository
export const assets = {
  logo: './FIRECAL LOGO.svg',
  logomark: './FIRECAL LOGOMARK.svg',
};

export default {
  colors,
  gradients,
  semanticColors,
  cssVariables,
  assets,
};
