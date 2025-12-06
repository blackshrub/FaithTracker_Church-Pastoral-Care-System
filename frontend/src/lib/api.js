/**
 * Centralized Axios Configuration
 * Provides a configured axios instance with:
 * - Request/Response timeouts
 * - Exponential backoff retry logic
 * - Request/Response interceptors
 */

import axios from 'axios';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

// Default timeout configuration
const DEFAULT_TIMEOUT = 30000; // 30 seconds
const UPLOAD_TIMEOUT = 120000; // 2 minutes for file uploads

// Retry configuration
const MAX_RETRIES = 3;
const RETRY_DELAY_BASE = 1000; // Base delay of 1 second
const RETRYABLE_STATUS_CODES = [408, 429, 500, 502, 503, 504];

// Create axios instance with defaults
// Note: BACKEND_URL should be the full API URL (e.g., https://api.domain.com)
// No /api suffix needed since we're using subdomain routing
const api = axios.create({
  baseURL: BACKEND_URL,
  timeout: DEFAULT_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Calculate exponential backoff delay with jitter
 * @param {number} retryCount - Current retry attempt (0-indexed)
 * @returns {number} Delay in milliseconds
 */
const getRetryDelay = (retryCount) => {
  // Exponential backoff: 1s, 2s, 4s
  const exponentialDelay = RETRY_DELAY_BASE * Math.pow(2, retryCount);
  // Add jitter (0-500ms) to prevent thundering herd
  const jitter = Math.random() * 500;
  return exponentialDelay + jitter;
};

/**
 * Determine if request should be retried
 * @param {Error} error - Axios error
 * @returns {boolean}
 */
const shouldRetry = (error) => {
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
  (config) => {
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
  (error) => Promise.reject(error)
);

// Response interceptor with retry logic
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config;

    // Check if we should retry
    if (config && config.__retryCount < MAX_RETRIES && shouldRetry(error)) {
      config.__retryCount += 1;

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

    // Handle 401 Unauthorized or 403 Forbidden - clear auth and redirect
    // Note: FastAPI's HTTPBearer returns 403 when no valid token is provided
    if (error.response?.status === 401 || error.response?.status === 403) {
      localStorage.removeItem('token');
      delete api.defaults.headers.common['Authorization'];
      // Don't redirect if already on login page
      if (!window.location.pathname.includes('/login')) {
        window.location.href = '/login';
      }
    }

    return Promise.reject(error);
  }
);

/**
 * Set authorization header
 * @param {string} token - JWT token
 */
export const setAuthToken = (token) => {
  if (token) {
    api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common['Authorization'];
  }
};

/**
 * Clear authorization header
 */
export const clearAuthToken = () => {
  delete api.defaults.headers.common['Authorization'];
};

export default api;
