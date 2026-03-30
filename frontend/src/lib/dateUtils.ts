/**
 * Date Utilities for FaithTracker
 * Centralized date formatting with local timezone support
 */

import { format } from 'date-fns/format';

// Get timezone from environment variable, or use browser's local timezone
// This allows deploying to different regions without code changes
const APP_TIMEZONE: string =
  import.meta.env.VITE_TIMEZONE || Intl.DateTimeFormat().resolvedOptions().timeZone;

type DateInput = string | Date;

type DateStyle = 'short' | 'medium' | 'long';

/**
 * Parse a timestamp that may or may not have timezone indicator
 * Backend stores timestamps in UTC but may not include 'Z' suffix
 * @param timestamp - Timestamp to parse
 * @param isDateOnly - If true, parse as local date (no timezone conversion)
 * @returns Parsed Date object or null if invalid
 */
export const parseUTCTimestamp = (
  timestamp: DateInput | null | undefined,
  isDateOnly = false
): Date | null => {
  if (!timestamp) return null;

  // If already a Date object, return it
  if (timestamp instanceof Date) return timestamp;

  // Convert to string if needed
  let ts = String(timestamp);

  // Check if this is a date-only string (YYYY-MM-DD format, no time component)
  const isDateOnlyString = /^\d{4}-\d{2}-\d{2}$/.test(ts);

  if (isDateOnly || isDateOnlyString) {
    // For date-only values, parse as local date to avoid timezone shift
    // This ensures "2024-12-03" displays as "Dec 03" regardless of timezone
    const [year, month, day] = ts.split('T')[0].split('-').map(Number);
    const date = new Date(year, month - 1, day);
    return isNaN(date.getTime()) ? null : date;
  }

  // For full timestamps, assume UTC if no timezone indicator
  if (!ts.endsWith('Z') && !ts.match(/[+-]\d{2}:\d{2}$/)) {
    ts = ts + 'Z';
  }

  const date = new Date(ts);
  return isNaN(date.getTime()) ? null : date;
};

/**
 * Format a timestamp to local timezone with full date and time
 * @param timestamp - Timestamp to format
 * @returns Formatted date string or '-' if invalid
 */
export const formatToLocalTimezone = (timestamp: DateInput | null | undefined): string => {
  const date = parseUTCTimestamp(timestamp);
  if (!date) return '-';

  return date.toLocaleString('id-ID', {
    timeZone: APP_TIMEZONE,
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
};

/**
 * Format a timestamp to local timezone with date only
 * @param timestamp - Timestamp to format
 * @param style - 'short' (dd MMM), 'medium' (dd MMM yyyy), 'long' (dd MMMM yyyy)
 * @returns Formatted date string or '-' if invalid
 */
export const formatDateToLocalTimezone = (
  timestamp: DateInput | null | undefined,
  style: DateStyle = 'medium'
): string => {
  const date = parseUTCTimestamp(timestamp);
  if (!date) return '-';

  const options: Intl.DateTimeFormatOptions = {
    timeZone: APP_TIMEZONE,
    day: 'numeric',
  };

  switch (style) {
    case 'short':
      options.month = 'short';
      break;
    case 'long':
      options.month = 'long';
      options.year = 'numeric';
      break;
    case 'medium':
    default:
      options.month = 'short';
      options.year = 'numeric';
      break;
  }

  return date.toLocaleDateString('id-ID', options);
};

/**
 * Format a timestamp to local timezone with time only
 * @param timestamp - Timestamp to format
 * @param includeSeconds - Whether to include seconds
 * @returns Formatted time string or '-' if invalid
 */
export const formatTimeToLocalTimezone = (
  timestamp: DateInput | null | undefined,
  includeSeconds = false
): string => {
  const date = parseUTCTimestamp(timestamp);
  if (!date) return '-';

  const options: Intl.DateTimeFormatOptions = {
    timeZone: APP_TIMEZONE,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  };

  if (includeSeconds) {
    options.second = '2-digit';
  }

  return date.toLocaleTimeString('id-ID', options);
};

/**
 * Safe date formatter using date-fns format
 * Handles invalid dates gracefully
 * @param dateStr - Date to format
 * @param formatStr - date-fns format string (default: 'dd MMM yyyy')
 * @returns Formatted date string or original input if invalid
 */
export const formatDate = (
  dateStr: DateInput | null | undefined,
  formatStr = 'dd MMM yyyy'
): string => {
  try {
    const date = parseUTCTimestamp(dateStr);
    if (!date) return (dateStr as string) || '-';
    return format(date, formatStr);
  } catch {
    return (dateStr as string) || '-';
  }
};

/**
 * Get current date in local timezone as ISO string (YYYY-MM-DD)
 * @returns Current date in local timezone
 */
export const getTodayLocal = (): string => {
  const now = new Date();
  // Format to local timezone and extract date part
  const localDate = now.toLocaleDateString('sv-SE', { timeZone: APP_TIMEZONE });
  return localDate; // Returns YYYY-MM-DD format
};

/**
 * Format relative time (e.g., "2 days ago", "in 3 hours")
 * @param timestamp - Timestamp to format
 * @returns Relative time string
 */
export const formatRelativeTime = (timestamp: DateInput | null | undefined): string => {
  const date = parseUTCTimestamp(timestamp);
  if (!date) return '-';

  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Tomorrow';
  if (diffDays === -1) return 'Yesterday';
  if (diffDays > 0) return `In ${diffDays} days`;
  return `${Math.abs(diffDays)} days ago`;
};

// Keep old names as aliases for backward compatibility
export const formatToJakarta = formatToLocalTimezone;
export const formatDateToJakarta = formatDateToLocalTimezone;
export const formatTimeToJakarta = formatTimeToLocalTimezone;
export const getTodayInJakarta = getTodayLocal;

export default {
  parseUTCTimestamp,
  formatToLocalTimezone,
  formatDateToLocalTimezone,
  formatTimeToLocalTimezone,
  formatDate,
  getTodayLocal,
  formatRelativeTime,
  // Aliases
  formatToJakarta: formatToLocalTimezone,
  formatDateToJakarta: formatDateToLocalTimezone,
  formatTimeToJakarta: formatTimeToLocalTimezone,
  getTodayInJakarta: getTodayLocal,
};
