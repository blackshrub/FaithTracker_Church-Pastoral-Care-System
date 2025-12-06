/**
 * Formatting Utilities for FaithTracker Mobile
 * Centralized currency and number formatting with Indonesian locale
 */

/**
 * Format currency with null handling
 * Uses Indonesian locale for proper thousands separator (.)
 * @param amount - Amount in IDR (can be null/undefined)
 * @returns Formatted string like "Rp 2.000.000"
 */
export function formatCurrency(amount: number | null | undefined): string {
  if (amount == null) return 'Rp 0';
  return new Intl.NumberFormat('id-ID', {
    style: 'currency',
    currency: 'IDR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

/**
 * Format currency without the "Rp" prefix
 * Useful when you want to display the amount with a custom label
 * @param amount - Amount in IDR (can be null/undefined)
 * @returns Formatted string like "2.000.000"
 */
export function formatCurrencyAmount(amount: number | null | undefined): string {
  if (amount == null) return '0';
  return new Intl.NumberFormat('id-ID', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

/**
 * Format a compact currency value for display in limited space
 * E.g., 1500000 -> "1,5 jt", 15000000000 -> "15 M"
 * @param amount - Amount in IDR
 * @returns Compact formatted string
 */
export function formatCurrencyCompact(amount: number | null | undefined): string {
  if (amount == null) return 'Rp 0';

  const absAmount = Math.abs(amount);
  const sign = amount < 0 ? '-' : '';

  if (absAmount >= 1_000_000_000_000) {
    // Trillions
    return `${sign}Rp ${(absAmount / 1_000_000_000_000).toFixed(1).replace('.', ',')} T`;
  }
  if (absAmount >= 1_000_000_000) {
    // Billions
    return `${sign}Rp ${(absAmount / 1_000_000_000).toFixed(1).replace('.', ',')} M`;
  }
  if (absAmount >= 1_000_000) {
    // Millions
    return `${sign}Rp ${(absAmount / 1_000_000).toFixed(1).replace('.', ',')} jt`;
  }
  if (absAmount >= 1_000) {
    // Thousands
    return `${sign}Rp ${(absAmount / 1_000).toFixed(0)} rb`;
  }

  return formatCurrency(amount);
}

/**
 * Format number with thousand separators (id-ID locale)
 * @param value - Number to format (can be null/undefined)
 * @returns Formatted string with Indonesian thousand separators
 */
export function formatNumber(value: number | null | undefined): string {
  if (value == null) return '0';
  return value.toLocaleString('id-ID');
}

/**
 * Format a percentage value
 * @param value - Decimal value (e.g., 0.75 for 75%)
 * @param decimals - Number of decimal places (default: 0)
 * @returns Formatted percentage string like "75%"
 */
export function formatPercent(
  value: number | null | undefined,
  decimals = 0
): string {
  if (value == null) return '0%';
  return `${(value * 100).toFixed(decimals)}%`;
}

/**
 * Format a percentage value that is already in percentage form
 * @param value - Percentage value (e.g., 75 for 75%)
 * @param decimals - Number of decimal places (default: 0)
 * @returns Formatted percentage string like "75%"
 */
export function formatPercentValue(
  value: number | null | undefined,
  decimals = 0
): string {
  if (value == null) return '0%';
  return `${value.toFixed(decimals)}%`;
}

/**
 * Format a phone number for display
 * Handles Indonesian phone numbers
 * @param phone - Phone number string
 * @returns Formatted phone number or original string
 */
export function formatPhoneNumber(phone: string | null | undefined): string {
  if (!phone) return '-';

  // Remove all non-digit characters
  const digits = phone.replace(/\D/g, '');

  // Indonesian mobile numbers (starting with 62 or 08)
  if (digits.startsWith('62')) {
    // Format: +62 812-3456-7890
    const rest = digits.slice(2);
    if (rest.length >= 9) {
      const formatted = `+62 ${rest.slice(0, 3)}-${rest.slice(3, 7)}-${rest.slice(7)}`;
      return formatted;
    }
  }

  if (digits.startsWith('08')) {
    // Format: 0812-3456-7890
    if (digits.length >= 10) {
      const formatted = `${digits.slice(0, 4)}-${digits.slice(4, 8)}-${digits.slice(8)}`;
      return formatted;
    }
  }

  // Return original if format unknown
  return phone;
}

/**
 * Truncate text with ellipsis
 * @param text - Text to truncate
 * @param maxLength - Maximum length before truncation
 * @returns Truncated text with ellipsis if needed
 */
export function truncateText(
  text: string | null | undefined,
  maxLength: number
): string {
  if (!text) return '';
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength - 3)}...`;
}

/**
 * Capitalize first letter of a string
 * @param text - Text to capitalize
 * @returns Capitalized text
 */
export function capitalize(text: string | null | undefined): string {
  if (!text) return '';
  return text.charAt(0).toUpperCase() + text.slice(1).toLowerCase();
}

/**
 * Format a name (capitalize each word)
 * @param name - Name to format
 * @returns Formatted name with each word capitalized
 */
export function formatName(name: string | null | undefined): string {
  if (!name) return '';
  return name
    .split(' ')
    .map((word) => capitalize(word))
    .join(' ');
}

/**
 * Format phone number for WhatsApp deep link
 * Converts Indonesian local format to international format
 * @param phone - Phone number string (can be +62xxx, 62xxx, 08xxx)
 * @returns WhatsApp URL like "https://wa.me/628123456789"
 */
export function formatPhoneForWhatsApp(phone: string | null | undefined): string | null {
  if (!phone) return null;

  // Remove all non-digit characters except leading +
  let formatted = phone.replace(/[^\d+]/g, '');

  // Convert Indonesian local format to international
  if (formatted.startsWith('0')) {
    formatted = '62' + formatted.substring(1);
  } else if (formatted.startsWith('+')) {
    formatted = formatted.substring(1);
  }

  return `https://wa.me/${formatted}`;
}

export default {
  formatCurrency,
  formatCurrencyAmount,
  formatCurrencyCompact,
  formatNumber,
  formatPercent,
  formatPercentValue,
  formatPhoneNumber,
  formatPhoneForWhatsApp,
  truncateText,
  capitalize,
  formatName,
};
