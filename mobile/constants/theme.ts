/**
 * FaithTracker Mobile Design System
 *
 * Primary: Teal (#14b8a6) - Trust, Care, Faith
 * Secondary: Amber (#f59e0b) - Warmth, Attention
 *
 * Designed for pastoral care staff of all ages
 * - High contrast for readability
 * - Large touch targets (min 44x44)
 * - Clear typography hierarchy
 */

export const colors = {
  // Primary - Teal (Trust, Care, Faith)
  primary: {
    50: '#f0fdfa',
    100: '#ccfbf1',
    200: '#99f6e4',
    300: '#5eead4',
    400: '#2dd4bf',
    500: '#14b8a6', // Main brand color
    600: '#0d9488',
    700: '#0f766e',
    800: '#115e59',
    900: '#134e4a',
    // Named aliases
    teal: '#14b8a6',
  },

  // Secondary - Amber (Warmth, Attention)
  secondary: {
    50: '#fffbeb',
    100: '#fef3c7',
    200: '#fde68a',
    300: '#fcd34d',
    400: '#fbbf24',
    500: '#f59e0b', // Accent color
    600: '#d97706',
    700: '#b45309',
    800: '#92400e',
    900: '#78350f',
    // Named aliases
    amber: '#f59e0b',
  },

  // Success - Green (Completed, Growth)
  success: {
    50: '#f0fdf4',
    100: '#dcfce7',
    200: '#bbf7d0',
    300: '#86efac',
    400: '#4ade80',
    500: '#22c55e',
    600: '#16a34a',
    700: '#15803d',
    800: '#166534',
    900: '#14532d',
  },

  // Warning - Amber (Attention Needed)
  warning: {
    50: '#fffbeb',
    100: '#fef3c7',
    200: '#fde68a',
    300: '#fcd34d',
    400: '#fbbf24',
    500: '#f59e0b',
    600: '#d97706',
    700: '#b45309',
    800: '#92400e',
    900: '#78350f',
  },

  // Error - Red (Overdue, Critical)
  error: {
    50: '#fef2f2',
    100: '#fee2e2',
    200: '#fecaca',
    300: '#fca5a5',
    400: '#f87171',
    500: '#ef4444',
    600: '#dc2626',
    700: '#b91c1c',
    800: '#991b1b',
    900: '#7f1d1d',
  },

  // Info - Blue (Information)
  info: {
    50: '#eff6ff',
    100: '#dbeafe',
    200: '#bfdbfe',
    300: '#93c5fd',
    400: '#60a5fa',
    500: '#3b82f6',
    600: '#2563eb',
    700: '#1d4ed8',
    800: '#1e40af',
    900: '#1e3a8a',
  },

  // Neutrals - Gray
  gray: {
    50: '#f9fafb',
    100: '#f3f4f6',
    200: '#e5e7eb',
    300: '#d1d5db',
    400: '#9ca3af',
    500: '#6b7280',
    600: '#4b5563',
    700: '#374151',
    800: '#1f2937',
    900: '#111827',
  },

  // Common
  white: '#ffffff',
  black: '#000000',

  // Semantic
  background: {
    light: '#ffffff',
    dark: '#0f172a',
  },
  text: {
    primary: '#111827',
    secondary: '#6b7280',
    tertiary: '#9ca3af',
    inverse: '#ffffff',
  },

  // Status colors (for quick access)
  status: {
    success: '#22c55e',        // green-500
    warning: '#f59e0b',        // amber-500
    error: '#ef4444',          // red-500
    info: '#3b82f6',           // blue-500
  },
};

// Dark mode semantic colors
export const darkColors = {
  // Backgrounds
  background: '#0f172a',       // slate-900
  surface: '#1e293b',          // slate-800
  surfaceElevated: '#334155',  // slate-700
  surfacePressed: '#475569',   // slate-600

  // Text
  text: {
    primary: '#f1f5f9',        // slate-100
    secondary: '#94a3b8',      // slate-400
    tertiary: '#64748b',       // slate-500
    inverse: '#0f172a',        // slate-900
  },

  // Borders
  border: {
    default: '#334155',        // slate-700
    light: '#1e293b',          // slate-800
    subtle: '#475569',         // slate-600
  },

  // Icon colors
  icon: {
    default: '#f1f5f9',        // slate-100
    muted: '#64748b',          // slate-500
    subtle: '#475569',         // slate-600
  },

  // Status (slightly adjusted for dark mode visibility)
  status: {
    success: '#22c55e',        // green-500
    warning: '#f59e0b',        // amber-500
    error: '#ef4444',          // red-500
    info: '#3b82f6',           // blue-500
  },
};

// Light mode semantic colors
export const lightColors = {
  // Backgrounds
  background: '#f9fafb',       // gray-50
  surface: '#ffffff',          // white
  surfaceElevated: '#ffffff',  // white
  surfacePressed: '#f3f4f6',   // gray-100

  // Text
  text: {
    primary: '#111827',        // gray-900
    secondary: '#6b7280',      // gray-500
    tertiary: '#9ca3af',       // gray-400
    inverse: '#ffffff',        // white
  },

  // Borders
  border: {
    default: '#e5e7eb',        // gray-200
    light: '#f3f4f6',          // gray-100
    subtle: '#d1d5db',         // gray-300
  },

  // Icon colors
  icon: {
    default: '#374151',        // gray-700
    muted: '#9ca3af',          // gray-400
    subtle: '#d1d5db',         // gray-300
  },

  // Status
  status: {
    success: '#22c55e',        // green-500
    warning: '#f59e0b',        // amber-500
    error: '#ef4444',          // red-500
    info: '#3b82f6',           // blue-500
  },
};

// Premium gradient for headers (dark teal theme)
export const gradients = {
  header: {
    start: '#0f4a47',
    mid: '#115e59',
    end: '#134e4a',
  },
  headerLight: {
    start: '#f0fdfa',
    mid: '#ccfbf1',
    end: '#99f6e4',
  },
};

export const typography = {
  fonts: {
    body: 'System',
    heading: 'System',
    mono: 'Courier',
  },
  sizes: {
    xs: 12,
    sm: 14,
    md: 16,
    lg: 18,
    xl: 20,
    '2xl': 24,
    '3xl': 30,
    '4xl': 36,
    '5xl': 48,
  },
  lineHeights: {
    tight: 1.25,
    normal: 1.5,
    relaxed: 1.75,
    loose: 2,
  },
  weights: {
    normal: '400' as const,
    medium: '500' as const,
    semibold: '600' as const,
    bold: '700' as const,
  },
};

export const shadows = {
  sm: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 1,
  },
  md: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  lg: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
    elevation: 5,
  },
  xl: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.2,
    shadowRadius: 16,
    elevation: 8,
  },
};

// Touch target sizes (WCAG AAA)
export const touchTargets = {
  minimum: 44,
  comfortable: 56,
  large: 64,
};

// Icon sizes
export const iconSizes = {
  xs: 16,
  sm: 20,
  md: 24,
  lg: 32,
  xl: 48,
};

// Event type colors for care events
export const eventTypeColors = {
  birthday: colors.secondary[500], // Amber
  grief_loss: colors.gray[600], // Dark gray
  accident_illness: colors.error[500], // Red
  financial_aid: colors.success[500], // Green
  regular_contact: colors.primary[500], // Teal
  childbirth: colors.info[500], // Blue
  new_house: colors.primary[400], // Light teal
};

// Engagement status colors
export const engagementColors = {
  active: colors.success[500],
  at_risk: colors.warning[500],
  disconnected: colors.error[500],
};

export default {
  colors,
  gradients,
  typography,
  shadows,
  touchTargets,
  iconSizes,
  eventTypeColors,
  engagementColors,
};
