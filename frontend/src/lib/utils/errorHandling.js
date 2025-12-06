/**
 * Error Handling Utilities
 * Standardized error handling across the application
 */

import { toast } from 'sonner';

/**
 * Handle API errors with consistent toast messages
 * @param {Error} error - Error object from API call
 * @param {string} defaultMessage - Default message if error details unavailable
 */
export const handleApiError = (error, defaultMessage = 'Something went wrong') => {
  // Extract error message from various response formats
  let message = defaultMessage;

  if (error.response?.data?.detail) {
    // Litestar/FastAPI error format
    const detail = error.response.data.detail;
    if (typeof detail === 'string') {
      message = detail;
    } else if (Array.isArray(detail)) {
      // Validation errors array
      message = detail.map(err => err.msg || err.message || String(err)).join(', ');
    } else if (typeof detail === 'object') {
      message = detail.message || detail.msg || JSON.stringify(detail);
    }
  } else if (error.response?.data?.message) {
    message = error.response.data.message;
  } else if (error.message) {
    message = error.message;
  }

  // Show toast
  toast.error(message);

  // Error already shown via toast - no additional logging needed

  return message;
};

/**
 * Safe error detail extraction for display
 * @param {Error} error - Error object
 * @returns {string} Safe error message for display
 */
export const getErrorMessage = (error) => {
  if (!error) return 'An unknown error occurred';

  if (error.response?.data?.detail) {
    const detail = error.response.data.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail.map(e => e.msg || e.message || String(e)).join(', ');
    }
  }

  if (error.message) return error.message;

  return 'An unexpected error occurred';
};

/**
 * Check if error is a network error
 * @param {Error} error - Error object
 * @returns {boolean}
 */
export const isNetworkError = (error) => {
  return !error.response && error.message === 'Network Error';
};

/**
 * Check if error is an authentication error
 * @param {Error} error - Error object
 * @returns {boolean}
 */
export const isAuthError = (error) => {
  return error.response?.status === 401 || error.response?.status === 403;
};
