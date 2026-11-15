/**
 * FireCal Design System - Typography & Style Configurations
 * NASA Space Apps Challenge · Cyber Techno & Deep Space Theme
 * 
 * Sourced directly from Figma File: FIRECAL - NASA Space Apps Challenge (Node #12:10396 & #12:10198)
 */

export const fontFamilies = {
  display: "'Space Grotesk', system-ui, -apple-system, sans-serif",
  interface: "'Figtree', 'Plus Jakarta Sans', system-ui, sans-serif",
  mono: "'JetBrains Mono', ui-monospace, monospace",
};

export const fontWeights = {
  regular: 400,
  medium: 500,
  semibold: 600,
  bold: 700,
};

/**
 * Text Style Configurations
 * Matches Figma text styles and web UI specifications
 */
export const textStyles = {
  // Brand & Display Styles
  displayLogo: {
    fontFamily: fontFamilies.display,
    fontSize: '277px',
    fontWeight: fontWeights.medium,
    fontStyle: 'normal',
    lineHeight: '1.0',
    description: 'Logo display text scale in Figma Base Design System (#12:9557)',
  },
  headingXL: {
    fontFamily: fontFamilies.display,
    fontSize: '75px',
    fontWeight: fontWeights.medium,
    lineHeight: '96px',
    letterSpacing: '-0.02em',
    description: 'Heading from Figma Base Design System (#12:10390)',
  },
  display2XL: {
    fontFamily: fontFamilies.display,
    fontSize: '36px',
    fontWeight: fontWeights.bold,
    lineHeight: '44px',
    letterSpacing: '-0.02em',
    description: 'Hero Title and Page Landmark headers (#12:10269)',
  },
  subheading: {
    fontFamily: fontFamilies.display,
    fontSize: '35px',
    fontWeight: fontWeights.medium,
    lineHeight: '45px',
    letterSpacing: '-0.01em',
    description: 'Subheading from Figma Base Design System (#12:10388)',
  },
  headingL: {
    fontFamily: fontFamilies.display,
    fontSize: '24px',
    fontWeight: fontWeights.semibold,
    lineHeight: '32px',
    letterSpacing: '-0.01em',
    description: 'Panel headers & Modal titles (#12:10271)',
  },
  buttonMedium: {
    fontFamily: fontFamilies.display,
    fontSize: '25px',
    fontWeight: fontWeights.medium,
    lineHeight: '32px',
    letterSpacing: '0',
    description: 'Button Medium from Figma Base Design System (#12:10394)',
  },
  bodyBase: {
    fontFamily: fontFamilies.display,
    fontSize: '22px',
    fontWeight: fontWeights.regular,
    lineHeight: '28px',
    letterSpacing: '0',
    description: 'Body Text from Figma Base Design System (#12:10392)',
  },
  headingM: {
    fontFamily: fontFamilies.display,
    fontSize: '18px',
    fontWeight: fontWeights.semibold,
    lineHeight: '24px',
    description: 'Section headers & Accordion controls (#12:10273)',
  },

  // Interface & Content Styles (Figtree / Sans)
  bodyLarge: {
    fontFamily: fontFamilies.interface,
    fontSize: '15px',
    fontWeight: fontWeights.medium,
    lineHeight: '24px',
    description: 'Interface explanatory copy & long-form descriptions (#12:10277)',
  },
  uiSemiBold: {
    fontFamily: fontFamilies.interface,
    fontSize: '13px',
    fontWeight: fontWeights.semibold,
    lineHeight: '18px',
    letterSpacing: '0.01em',
    description: 'Button labels, navigation tabs, filter chips (#12:10279)',
  },
  caption: {
    fontFamily: fontFamilies.interface,
    fontSize: '12px',
    fontWeight: fontWeights.regular,
    lineHeight: '16px',
    description: 'Metadata, satellite timestamps, coordinate badges (#12:10280)',
  },
  badge: {
    fontFamily: fontFamilies.interface,
    fontSize: '11px',
    fontWeight: fontWeights.bold,
    lineHeight: '14px',
    letterSpacing: '0.05em',
    textTransform: 'uppercase',
    description: 'Micro badge pills (e.g. VIIRS 375m, MODIS 1km) (#12:10325)',
  },

  // Monospace Data (JetBrains Mono)
  monoData: {
    fontFamily: fontFamilies.mono,
    fontSize: '13px',
    fontWeight: fontWeights.medium,
    lineHeight: '18px',
    fontVariantNumeric: 'tabular-nums',
    description: 'Telemetry readings, numeric data points, lat/long grids',
  },
};

export default {
  fontFamilies,
  fontWeights,
  textStyles,
};
