/**
 * Date Utilities for FaithTracker
 * Centralized date formatting with local timezone support
 */

import { format } from 'date-fns/format';

// Get timezone from environment variable, or use browser's local timezone
// This allows deploying to different regions without code changes
const APP_TIMEZONE = import.meta.env.VITE_TIMEZONE || Intl.DateTimeFormat().resolvedOptions().timeZone;

/**
 * Parse a timestamp that may or may not have timezone indicator
 * Backend stores timestamps in UTC but may not include 'Z' suffix
 * @param {string|Date} timestamp - Timestamp to parse
 * @param {boolean} isDateOnly - If true, parse as local date (no timezone conversion)
 * @returns {Date|null} Parsed Date object or null if invalid
 */
export const parseUTCTimestamp = (timestamp, isDateOnly = false) => {
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
 * @param {string|Date} timestamp - Timestamp to format
 * @returns {string} Formatted date string or '-' if invalid
 */
export const formatToLocalTimezone = (timestamp) => {
  const date = parseUTCTimestamp(timestamp);
  if (!date) return '-';

  return date.toLocaleString('id-ID', {
    timeZone: APP_TIMEZONE,
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
};

/**
 * Format a timestamp to local timezone with date only
 * @param {string|Date} timestamp - Timestamp to format
 * @param {string} style - 'short' (dd MMM), 'medium' (dd MMM yyyy), 'long' (dd MMMM yyyy)
 * @returns {string} Formatted date string or '-' if invalid
 */
export const formatDateToLocalTimezone = (timestamp, style = 'medium') => {
  const date = parseUTCTimestamp(timestamp);
  if (!date) return '-';

  const options = {
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
 * @param {string|Date} timestamp - Timestamp to format
 * @param {boolean} includeSeconds - Whether to include seconds
 * @returns {string} Formatted time string or '-' if invalid
 */
export const formatTimeToLocalTimezone = (timestamp, includeSeconds = false) => {
  const date = parseUTCTimestamp(timestamp);
  if (!date) return '-';

  const options = {
    timeZone: APP_TIMEZONE,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  };

  if (includeSeconds) {
    options.second = '2-digit';
  }

  return date.toLocaleTimeString('id-ID', options);
};

/**
 * Safe date formatter using date-fns format
 * Handles invalid dates gracefully
 * @param {string|Date} dateStr - Date to format
 * @param {string} formatStr - date-fns format string (default: 'dd MMM yyyy')
 * @returns {string} Formatted date string or original input if invalid
 */
export const formatDate = (dateStr, formatStr = 'dd MMM yyyy') => {
  try {
    const date = parseUTCTimestamp(dateStr);
    if (!date) return dateStr || '-';
    return format(date, formatStr);
  } catch {
    return dateStr || '-';
  }
};

/**
 * Get current date in local timezone as ISO string (YYYY-MM-DD)
 * @returns {string} Current date in local timezone
 */
export const getTodayLocal = () => {
  const now = new Date();
  // Format to local timezone and extract date part
  const localDate = now.toLocaleDateString('sv-SE', { timeZone: APP_TIMEZONE });
  return localDate; // Returns YYYY-MM-DD format
};

/**
 * Format relative time (e.g., "2 days ago", "in 3 hours")
 * @param {string|Date} timestamp - Timestamp to format
 * @returns {string} Relative time string
 */
export const formatRelativeTime = (timestamp) => {
  const date = parseUTCTimestamp(timestamp);
  if (!date) return '-';

  const now = new Date();
  const diffMs = date - now;
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
