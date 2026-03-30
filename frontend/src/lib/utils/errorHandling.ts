/**
 * Error Handling Utilities
 * Standardized error handling across the application
 */

import { toast } from 'sonner';
import type { AxiosError } from 'axios';

interface ApiErrorResponse {
  detail?: string | ApiValidationError[] | Record<string, unknown>;
  message?: string;
}

interface ApiValidationError {
  msg?: string;
  message?: string;
}

/**
 * Handle API errors with consistent toast messages
 * @param error - Error object from API call
 * @param defaultMessage - Default message if error details unavailable
 * @returns The error message that was displayed
 */
export const handleApiError = (
  error: AxiosError<ApiErrorResponse> | Error,
  defaultMessage = 'Something went wrong'
): string => {
  // Extract error message from various response formats
  let message = defaultMessage;

  const axiosError = error as AxiosError<ApiErrorResponse>;

  if (axiosError.response?.data?.detail) {
    // Litestar/FastAPI error format
    const detail = axiosError.response.data.detail;
    if (typeof detail === 'string') {
      message = detail;
    } else if (Array.isArray(detail)) {
      // Validation errors array
      message = detail.map((err) => err.msg || err.message || String(err)).join(', ');
    } else if (typeof detail === 'object') {
      const detailObj = detail as Record<string, unknown>;
      message =
        (detailObj.message as string) || (detailObj.msg as string) || JSON.stringify(detail);
    }
  } else if (axiosError.response?.data?.message) {
    message = axiosError.response.data.message;
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
 * @param error - Error object
 * @returns Safe error message for display
 */
export const getErrorMessage = (
  error: AxiosError<ApiErrorResponse> | Error | null | undefined
): string => {
  if (!error) return 'An unknown error occurred';

  const axiosError = error as AxiosError<ApiErrorResponse>;

  if (axiosError.response?.data?.detail) {
    const detail = axiosError.response.data.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail.map((e) => e.msg || e.message || String(e)).join(', ');
    }
  }

  if (error.message) return error.message;

  return 'An unexpected error occurred';
};

/**
 * Check if error is a network error
 * @param error - Error object
 * @returns Whether the error is a network error
 */
export const isNetworkError = (error: AxiosError | Error): boolean => {
  const axiosError = error as AxiosError;
  return !axiosError.response && error.message === 'Network Error';
};

/**
 * Check if error is an authentication error
 * @param error - Error object
 * @returns Whether the error is an auth error (401 or 403)
 */
export const isAuthError = (error: AxiosError | Error): boolean => {
  const axiosError = error as AxiosError;
  return axiosError.response?.status === 401 || axiosError.response?.status === 403;
};
