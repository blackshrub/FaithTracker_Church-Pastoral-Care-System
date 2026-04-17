/**
 * Access-token refresh coordination.
 *
 * Only ONE refresh call is ever in flight at a time: when multiple requests
 * fail with 401 simultaneously (common on cold starts), the first one fires
 * POST /auth/refresh and all the others await the same promise. This avoids
 * burning through refresh-token rotations in parallel.
 */

import axios, { type AxiosInstance } from 'axios';
import * as SecureStore from 'expo-secure-store';

import { API_ENDPOINTS } from '@/constants/api';
import type { RefreshResponse } from '@/types';

// SecureStore key shared with stores/auth.ts.
const REFRESH_TOKEN_KEY = 'faithtracker_refresh_token';
const TOKEN_KEY = 'faithtracker_auth_token';

export async function getStoredRefreshToken(): Promise<string | null> {
  return SecureStore.getItemAsync(REFRESH_TOKEN_KEY);
}

export async function setStoredRefreshToken(token: string | null): Promise<void> {
  if (token) {
    await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, token);
  } else {
    await SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY).catch(() => {});
  }
}

export async function setStoredAccessToken(token: string | null): Promise<void> {
  if (token) {
    await SecureStore.setItemAsync(TOKEN_KEY, token);
  } else {
    await SecureStore.deleteItemAsync(TOKEN_KEY).catch(() => {});
  }
}

let inflight: Promise<string | null> | null = null;

/**
 * Attempt a refresh. Returns the new access token, or null if refresh failed
 * (in which case the caller should force a logout).
 *
 * @param baseURL - the same baseURL the main axios instance uses. We create a
 *   fresh, interceptor-free axios call here to avoid reentering our own 401
 *   handler (which would infinite-loop).
 */
export function refreshAccessToken(baseURL: string): Promise<string | null> {
  if (inflight) {
    return inflight;
  }

  inflight = (async () => {
    try {
      const refreshToken = await getStoredRefreshToken();
      if (!refreshToken) {
        return null;
      }

      // Bare axios — no interceptors — to avoid recursive refresh attempts.
      const response = await axios.post<RefreshResponse>(
        `${baseURL}${API_ENDPOINTS.AUTH.REFRESH}`,
        { refresh_token: refreshToken },
        {
          headers: { 'Content-Type': 'application/json' },
          timeout: 15000,
        }
      );

      const newAccess = response.data.access_token;
      const rotatedRefresh = response.data.refresh_token ?? null;

      await setStoredAccessToken(newAccess);
      if (rotatedRefresh) {
        await setStoredRefreshToken(rotatedRefresh);
      }

      // Push the new access token into the Zustand auth store so React
      // components see the update. Lazy-require to break a circular import.
      try {
        const { useAuthStore } = require('@/stores/auth');
        useAuthStore.setState({ token: newAccess });
      } catch {
        // stores/auth not yet loaded — safe to ignore, the token is in
        // SecureStore and will be picked up on next initialize().
      }

      return newAccess;
    } catch (err) {
      // Refresh failed — caller will handle logout.
      return null;
    } finally {
      inflight = null;
    }
  })();

  return inflight;
}

/**
 * Apply the refresh-on-401 interceptor to the given axios instance.
 *
 * Semantics:
 *   1. On any 401, try to refresh the access token (single-flight).
 *   2. If refresh succeeds: retry the original request once with the new token.
 *   3. If refresh fails: log out the user and let the original 401 propagate.
 *   4. Never retry /auth/login, /auth/refresh, or /auth/logout themselves.
 */
export function installRefreshInterceptor(api: AxiosInstance): void {
  api.interceptors.response.use(
    (r) => r,
    async (error) => {
      const original = error?.config;
      if (!error?.response || error.response.status !== 401 || !original) {
        throw error;
      }

      // Don't try to refresh for auth endpoints themselves — that'd loop.
      const url: string = original.url ?? '';
      if (
        url.includes(API_ENDPOINTS.AUTH.LOGIN) ||
        url.includes(API_ENDPOINTS.AUTH.REFRESH) ||
        url.includes(API_ENDPOINTS.AUTH.LOGOUT)
      ) {
        throw error;
      }

      // Prevent infinite retry loops on a single request.
      if (original._retriedAfterRefresh) {
        throw error;
      }
      original._retriedAfterRefresh = true;

      const baseURL: string =
        api.defaults.baseURL || process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8001/api';
      const newAccess = await refreshAccessToken(baseURL);

      if (!newAccess) {
        // Refresh failed — force a logout so the UI routes back to login.
        try {
          const { useAuthStore } = require('@/stores/auth');
          await useAuthStore.getState().logout();
        } catch {
          // If stores/auth isn't ready, the 401 still propagates.
        }
        throw error;
      }

      // Retry the original request with the fresh token.
      original.headers = original.headers || {};
      original.headers.Authorization = `Bearer ${newAccess}`;
      return api(original);
    }
  );
}
