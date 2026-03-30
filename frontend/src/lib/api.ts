/**
 * Centralized Axios Configuration
 * Provides a configured axios instance with:
 * - Request/Response timeouts
 * - Exponential backoff retry logic
 * - Request/Response interceptors
 */

import axios, {
  type AxiosInstance,
  type AxiosError,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios';

const BACKEND_URL: string = import.meta.env.VITE_BACKEND_URL || '';

// Default timeout configuration
const DEFAULT_TIMEOUT = 30000; // 30 seconds
const UPLOAD_TIMEOUT = 120000; // 2 minutes for file uploads

// Retry configuration
const MAX_RETRIES = 3;
const RETRY_DELAY_BASE = 1000; // Base delay of 1 second
const RETRYABLE_STATUS_CODES: number[] = [408, 429, 500, 502, 503, 504];

/** Extended config to track retry count internally */
interface RetryableAxiosRequestConfig extends InternalAxiosRequestConfig {
  __retryCount?: number;
}

// Create axios instance with defaults
// Note: BACKEND_URL should be the full API URL (e.g., https://api.domain.com)
// No /api suffix needed since we're using subdomain routing
const api: AxiosInstance = axios.create({
  baseURL: BACKEND_URL,
  timeout: DEFAULT_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Calculate exponential backoff delay with jitter
 * @param retryCount - Current retry attempt (0-indexed)
 * @returns Delay in milliseconds
 */
const getRetryDelay = (retryCount: number): number => {
  // Exponential backoff: 1s, 2s, 4s
  const exponentialDelay = RETRY_DELAY_BASE * Math.pow(2, retryCount);
  // Add jitter (0-500ms) to prevent thundering herd
  const jitter = Math.random() * 500;
  return exponentialDelay + jitter;
};

/**
 * Determine if request should be retried
 * @param error - Axios error
 * @returns Whether the request should be retried
 */
const shouldRetry = (error: AxiosError): boolean => {
  // Don't retry if no response (network error) - already handled by axios
  if (!error.response) {
    // Retry network errors (timeout, connection refused)
    return error.code === 'ECONNABORTED' || error.code === 'ERR_NETWORK';
  }

  // Don't retry client errors (4xx) except specific codes
  const status = error.response.status;
  return RETRYABLE_STATUS_CODES.includes(status);
};

// Request interceptor
api.interceptors.request.use(
  (config: RetryableAxiosRequestConfig): RetryableAxiosRequestConfig => {
    // Add auth token if available
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    // Set longer timeout for file uploads
    if (config.data instanceof FormData) {
      config.timeout = UPLOAD_TIMEOUT;
    }

    // Initialize retry count
    config.__retryCount = config.__retryCount || 0;

    return config;
  },
  (error: AxiosError) => Promise.reject(error)
);

// Response interceptor with retry logic
api.interceptors.response.use(
  (response: AxiosResponse): AxiosResponse => response,
  async (error: AxiosError) => {
    const config = error.config as RetryableAxiosRequestConfig | undefined;

    // Check if we should retry
    if (config && (config.__retryCount ?? 0) < MAX_RETRIES && shouldRetry(error)) {
      config.__retryCount = (config.__retryCount ?? 0) + 1;

      // Wait with exponential backoff
      const delay = getRetryDelay(config.__retryCount - 1);
      await new Promise(resolve => setTimeout(resolve, delay));

      // Log retry attempt (in development only)
      if (import.meta.env.DEV) {
        // eslint-disable-next-line no-console
        console.log(`Retrying request (attempt ${config.__retryCount}/${MAX_RETRIES}):`, config.url);
      }

      return api(config);
    }

    // Handle 401 Unauthorized - always clear auth and redirect
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      delete api.defaults.headers.common['Authorization'];
      if (!window.location.pathname.includes('/login')) {
        window.location.href = '/login';
      }
    }
    // Handle 403 Forbidden - only redirect if it's an auth/token issue, not a role-based denial
    if (error.response?.status === 403) {
      const detail = (
        (error.response?.data as Record<string, unknown>)?.detail as string || ''
      ).toLowerCase();
      if (detail.includes('token') || detail.includes('not authenticated') || detail.includes('credentials')) {
        localStorage.removeItem('token');
        delete api.defaults.headers.common['Authorization'];
        if (!window.location.pathname.includes('/login')) {
          window.location.href = '/login';
        }
      }
      // Otherwise let the 403 propagate to the calling code for role-based permission errors
    }

    return Promise.reject(error);
  }
);

/**
 * Set authorization header
 * @param token - JWT token
 */
export const setAuthToken = (token: string | null): void => {
  if (token) {
    api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common['Authorization'];
  }
};

/**
 * Clear authorization header
 */
export const clearAuthToken = (): void => {
  delete api.defaults.headers.common['Authorization'];
};

export default api;
