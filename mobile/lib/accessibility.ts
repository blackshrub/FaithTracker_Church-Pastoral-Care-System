/**
 * Accessibility Utilities
 *
 * Helpers for building accessible React Native components
 * Following WCAG 2.1 AA guidelines
 */

import { AccessibilityInfo, AccessibilityRole, Platform } from 'react-native';

// ============================================================================
// TYPES
// ============================================================================

export interface AccessibilityProps {
  accessible?: boolean;
  accessibilityLabel?: string;
  accessibilityHint?: string;
  accessibilityRole?: AccessibilityRole;
  accessibilityState?: {
    disabled?: boolean;
    selected?: boolean;
    checked?: boolean | 'mixed';
    busy?: boolean;
    expanded?: boolean;
  };
  accessibilityValue?: {
    min?: number;
    max?: number;
    now?: number;
    text?: string;
  };
  accessibilityActions?: Array<{
    name: string;
    label?: string;
  }>;
  onAccessibilityAction?: (event: { nativeEvent: { actionName: string } }) => void;
}

// ============================================================================
// SCREEN READER ANNOUNCEMENTS
// ============================================================================

/**
 * Announce a message to screen readers
 * @param message - Message to announce
 */
export function announceForAccessibility(message: string): void {
  AccessibilityInfo.announceForAccessibility(message);
}

/**
 * Announce a message after a delay
 * Useful for announcing changes after animations complete
 */
export function announceAfterDelay(message: string, delayMs = 300): void {
  setTimeout(() => {
    AccessibilityInfo.announceForAccessibility(message);
  }, delayMs);
}

// ============================================================================
// ACCESSIBILITY PROP BUILDERS
// ============================================================================

/**
 * Create accessibility props for a button
 */
export function buttonAccessibilityProps(
  label: string,
  options?: {
    hint?: string;
    disabled?: boolean;
  }
): AccessibilityProps {
  return {
    accessible: true,
    accessibilityRole: 'button',
    accessibilityLabel: label,
    accessibilityHint: options?.hint,
    accessibilityState: {
      disabled: options?.disabled,
    },
  };
}

/**
 * Create accessibility props for a link
 */
export function linkAccessibilityProps(
  label: string,
  hint?: string
): AccessibilityProps {
  return {
    accessible: true,
    accessibilityRole: 'link',
    accessibilityLabel: label,
    accessibilityHint: hint || 'Double tap to open',
  };
}

/**
 * Create accessibility props for a checkbox or switch
 */
export function checkboxAccessibilityProps(
  label: string,
  checked: boolean,
  hint?: string
): AccessibilityProps {
  return {
    accessible: true,
    accessibilityRole: 'checkbox',
    accessibilityLabel: label,
    accessibilityHint: hint || `Double tap to ${checked ? 'uncheck' : 'check'}`,
    accessibilityState: {
      checked,
    },
  };
}

/**
 * Create accessibility props for an image
 */
export function imageAccessibilityProps(
  label: string,
  isDecorative = false
): AccessibilityProps {
  if (isDecorative) {
    return {
      accessible: false,
      accessibilityRole: 'none',
    };
  }
  return {
    accessible: true,
    accessibilityRole: 'image',
    accessibilityLabel: label,
  };
}

/**
 * Create accessibility props for a header
 */
export function headerAccessibilityProps(
  label: string,
  level?: 1 | 2 | 3 | 4 | 5 | 6
): AccessibilityProps {
  return {
    accessible: true,
    accessibilityRole: 'header',
    accessibilityLabel: label,
    // Note: React Native doesn't support heading levels directly
    // Consider using accessibilityHint for context
  };
}

/**
 * Create accessibility props for a list item
 */
export function listItemAccessibilityProps(
  label: string,
  index: number,
  total: number,
  hint?: string
): AccessibilityProps {
  return {
    accessible: true,
    accessibilityRole: 'button',
    accessibilityLabel: label,
    accessibilityHint: hint || `Item ${index + 1} of ${total}. Double tap to view details.`,
  };
}

/**
 * Create accessibility props for a tab
 */
export function tabAccessibilityProps(
  label: string,
  selected: boolean,
  index: number,
  total: number
): AccessibilityProps {
  return {
    accessible: true,
    accessibilityRole: 'tab',
    accessibilityLabel: label,
    accessibilityHint: `Tab ${index + 1} of ${total}`,
    accessibilityState: {
      selected,
    },
  };
}

/**
 * Create accessibility props for a text input
 */
export function textInputAccessibilityProps(
  label: string,
  options?: {
    hint?: string;
    required?: boolean;
    error?: string;
  }
): AccessibilityProps {
  let accessibilityLabel = label;
  if (options?.required) {
    accessibilityLabel += ', required';
  }
  if (options?.error) {
    accessibilityLabel += `, error: ${options.error}`;
  }

  return {
    accessible: true,
    accessibilityLabel,
    accessibilityHint: options?.hint || 'Double tap to edit',
  };
}

/**
 * Create accessibility props for a progress indicator
 */
export function progressAccessibilityProps(
  label: string,
  value: number,
  max = 100
): AccessibilityProps {
  const percentage = Math.round((value / max) * 100);
  return {
    accessible: true,
    accessibilityRole: 'progressbar',
    accessibilityLabel: `${label}, ${percentage}% complete`,
    accessibilityValue: {
      min: 0,
      max,
      now: value,
      text: `${percentage}%`,
    },
  };
}

/**
 * Create accessibility props for a slider
 */
export function sliderAccessibilityProps(
  label: string,
  value: number,
  min: number,
  max: number,
  hint?: string
): AccessibilityProps {
  return {
    accessible: true,
    accessibilityRole: 'adjustable',
    accessibilityLabel: label,
    accessibilityHint: hint || 'Swipe up or down to adjust',
    accessibilityValue: {
      min,
      max,
      now: value,
    },
  };
}

// ============================================================================
// SEMANTIC LABELS
// ============================================================================

/**
 * Format a count for accessibility (e.g., "5 items" instead of "5")
 */
export function formatCountLabel(count: number, singular: string, plural?: string): string {
  const pluralWord = plural || `${singular}s`;
  return count === 1 ? `1 ${singular}` : `${count} ${pluralWord}`;
}

/**
 * Format a date for accessibility announcement
 */
export function formatDateLabel(date: Date | string): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return d.toLocaleDateString(undefined, {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

/**
 * Format currency for accessibility
 */
export function formatCurrencyLabel(amount: number, currency = 'IDR'): string {
  if (currency === 'IDR') {
    if (amount >= 1000000) {
      return `${(amount / 1000000).toFixed(1)} million rupiah`;
    }
    if (amount >= 1000) {
      return `${(amount / 1000).toFixed(0)} thousand rupiah`;
    }
    return `${amount} rupiah`;
  }
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency,
  }).format(amount);
}

// ============================================================================
// FOCUS MANAGEMENT
// ============================================================================

/**
 * Create a ref handler that can focus an element
 * Usage: <View ref={focusRef} accessible />
 */
export function createFocusRef() {
  let elementRef: any = null;

  return {
    setRef: (ref: any) => {
      elementRef = ref;
    },
    focus: () => {
      if (elementRef && Platform.OS === 'ios') {
        AccessibilityInfo.setAccessibilityFocus(elementRef);
      }
    },
  };
}

// ============================================================================
// LIVE REGION SUPPORT
// ============================================================================

/**
 * Props for live region (announces changes automatically)
 */
export function liveRegionProps(
  polite: 'polite' | 'assertive' = 'polite'
): { accessibilityLiveRegion: 'polite' | 'assertive' | 'none' } {
  return {
    accessibilityLiveRegion: polite,
  };
}

export default {
  announceForAccessibility,
  announceAfterDelay,
  buttonAccessibilityProps,
  linkAccessibilityProps,
  checkboxAccessibilityProps,
  imageAccessibilityProps,
  headerAccessibilityProps,
  listItemAccessibilityProps,
  tabAccessibilityProps,
  textInputAccessibilityProps,
  progressAccessibilityProps,
  sliderAccessibilityProps,
  formatCountLabel,
  formatDateLabel,
  formatCurrencyLabel,
  createFocusRef,
  liveRegionProps,
};
