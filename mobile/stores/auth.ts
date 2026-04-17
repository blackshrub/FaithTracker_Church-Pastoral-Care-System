/**
 * FaithTracker Auth Store
 *
 * Manages authentication state with SecureStore persistence
 */

import { create } from 'zustand';
import { useShallow } from 'zustand/shallow';
import * as SecureStore from 'expo-secure-store';
import api from '@/services/api';
import { API_ENDPOINTS } from '@/constants/api';
import { USE_MOCK_DATA, mockLogin, mockGetCurrentUser } from '@/services/mockApi';
import type { User, LoginRequest, LoginResponse } from '@/types';

// ============================================================================
// TYPES
// ============================================================================

interface AuthState {
  token: string | null;
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;

  // Actions
  login: (email: string, password: string, campusId?: string) => Promise<void>;
  loginWithBiometrics: () => Promise<boolean>;
  logout: () => Promise<void>;
  initialize: () => Promise<void>;
  refreshUser: () => Promise<void>;
  saveCredentialsForBiometric: (email: string, password: string) => Promise<void>;
  clearBiometricCredentials: () => Promise<void>;
  hasSavedCredentials: () => boolean;
}

// ============================================================================
// CONSTANTS
// ============================================================================

const TOKEN_KEY = 'faithtracker_auth_token';
const REFRESH_TOKEN_KEY = 'faithtracker_refresh_token';
const USER_KEY = 'faithtracker_auth_user';
// Legacy keys from older app versions — deleted on initialize to scrub stored
// plaintext passwords that used to gate biometric login.
const LEGACY_BIOMETRIC_EMAIL_KEY = 'faithtracker_biometric_email';
const LEGACY_BIOMETRIC_PASSWORD_KEY = 'faithtracker_biometric_password';
// Presence of this flag means the user opted into biometric unlock. The flag
// itself is not a secret — biometric only gatekeeps the *already-stored* JWT.
const BIOMETRIC_ENABLED_KEY = 'faithtracker_biometric_enabled';

// Track if biometric unlock is opted in (in-memory flag, set during initialize)
let hasCredentialsSaved = false;

// ============================================================================
// STORE
// ============================================================================

export const useAuthStore = create<AuthState>((set, get) => ({
  token: null,
  user: null,
  isLoading: true,
  isAuthenticated: false,

  /**
   * Login with email and password
   */
  login: async (email: string, password: string, campusId?: string) => {
    try {
      let access_token: string;
      let refresh_token: string | null | undefined;
      let user: User;

      if (USE_MOCK_DATA) {
        // Use mock API in development
        const result = await mockLogin(email, password);
        access_token = result.token;
        refresh_token = null;
        user = result.user;
      } else {
        // Use real API
        const payload: LoginRequest = { email, password };
        if (campusId) {
          payload.campus_id = campusId;
        }
        const response = await api.post<LoginResponse>(
          API_ENDPOINTS.AUTH.LOGIN,
          payload
        );
        access_token = response.data.access_token;
        refresh_token = response.data.refresh_token;
        user = response.data.user;
      }

      // Persist access + refresh tokens + user to secure storage.
      // The refresh token is what keeps the user logged in across access-token
      // expiries — without it we'd boot them out every 4 hours.
      await SecureStore.setItemAsync(TOKEN_KEY, access_token);
      if (refresh_token) {
        await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, refresh_token);
      } else {
        // Mock mode has no refresh token — ensure we don't carry a stale one.
        await SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY).catch(() => {});
      }
      await SecureStore.setItemAsync(USER_KEY, JSON.stringify(user));

      // Update state
      set({
        token: access_token,
        user,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch (error) {
      set({ isLoading: false });
      throw error;
    }
  },

  /**
   * Unlock the already-stored session using biometric auth.
   *
   * Unlike the old implementation, this does NOT re-run a password login —
   * it restores the JWT that was saved at last login (validated via /auth/me).
   * If the token has expired, the caller should fall back to password entry.
   */
  loginWithBiometrics: async () => {
    try {
      const token = await SecureStore.getItemAsync(TOKEN_KEY);
      const userStr = await SecureStore.getItemAsync(USER_KEY);

      if (!token || !userStr) {
        // Nothing to unlock — user needs to do a full password login.
        return false;
      }

      const user = JSON.parse(userStr) as User;

      // Put the token in state so the next /auth/me call carries the Bearer.
      set({
        token,
        user,
        isAuthenticated: true,
        isLoading: false,
      });

      if (USE_MOCK_DATA) {
        return true;
      }

      try {
        // Confirm the stored token is still valid against the backend.
        const response = await api.get<User>(API_ENDPOINTS.AUTH.ME);
        set({ user: response.data });
        await SecureStore.setItemAsync(USER_KEY, JSON.stringify(response.data));
        return true;
      } catch (error) {
        // Token expired or revoked — clear state so the UI shows the password form.
        await get().logout();
        return false;
      }
    } catch (error) {
      console.error('Biometric unlock failed:', error);
      return false;
    }
  },

  /**
   * Logout and clear all auth data
   */
  logout: async () => {
    // Best-effort revoke the refresh token server-side so a leaked token can't
    // outlive the logout. We don't block the user if this fails (e.g. offline).
    try {
      const refreshToken = await SecureStore.getItemAsync(REFRESH_TOKEN_KEY);
      if (refreshToken && !USE_MOCK_DATA) {
        await api.post(API_ENDPOINTS.AUTH.LOGOUT, { refresh_token: refreshToken }).catch(() => {});
      }
    } catch {
      // ignore
    }

    try {
      // Clear secure storage
      await SecureStore.deleteItemAsync(TOKEN_KEY);
      await SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY);
      await SecureStore.deleteItemAsync(USER_KEY);
    } catch (error) {
      console.error('Error clearing auth data:', error);
    }

    // Clear the TanStack Query cache so data cached for the previous user
    // cannot bleed into the next user's session on this device.
    // Lazy require to break circular dependency with queryClient ↔ api.
    try {
      const { clearQueryCache } = require('@/lib/queryClient');
      clearQueryCache();
    } catch (error) {
      console.warn('Could not clear query cache on logout:', error);
    }

    // Clear state
    set({
      token: null,
      user: null,
      isAuthenticated: false,
      isLoading: false,
    });
  },

  /**
   * Initialize auth state from secure storage
   * Called on app startup
   */
  initialize: async () => {
    try {
      const token = await SecureStore.getItemAsync(TOKEN_KEY);
      const userStr = await SecureStore.getItemAsync(USER_KEY);

      // One-time migration: delete any legacy plaintext-password store from
      // older app versions. Biometric unlock now gates the JWT only.
      await SecureStore.deleteItemAsync(LEGACY_BIOMETRIC_EMAIL_KEY).catch(() => {});
      await SecureStore.deleteItemAsync(LEGACY_BIOMETRIC_PASSWORD_KEY).catch(() => {});

      // User has opted into biometric unlock?
      const biometricFlag = await SecureStore.getItemAsync(BIOMETRIC_ENABLED_KEY);
      hasCredentialsSaved = biometricFlag === '1';

      if (token && userStr) {
        const user = JSON.parse(userStr) as User;

        set({
          token,
          user,
          isAuthenticated: true,
          isLoading: false,
        });

        // Verify token is still valid by fetching current user
        // Skip verification in mock mode - trust the stored data
        if (!USE_MOCK_DATA) {
          try {
            const response = await api.get<User>(API_ENDPOINTS.AUTH.ME);
            set({ user: response.data });
            // Update stored user with fresh data
            await SecureStore.setItemAsync(USER_KEY, JSON.stringify(response.data));
          } catch (error) {
            // Token invalid, logout
            console.log('Token invalid, logging out');
            await get().logout();
          }
        }
      } else {
        set({ isLoading: false });
      }
    } catch (error) {
      console.error('Error initializing auth:', error);
      set({ isLoading: false });
    }
  },

  /**
   * Refresh user data from server
   */
  refreshUser: async () => {
    try {
      let user: User;

      if (USE_MOCK_DATA) {
        user = await mockGetCurrentUser();
      } else {
        const response = await api.get<User>(API_ENDPOINTS.AUTH.ME);
        user = response.data;
      }

      await SecureStore.setItemAsync(USER_KEY, JSON.stringify(user));
      set({ user });
    } catch (error) {
      console.error('Error refreshing user:', error);
      throw error;
    }
  },

  /**
   * Opt into biometric unlock. The email/password args are accepted for
   * backwards compatibility with existing UI (which prompts the user to
   * confirm their password), but they are NOT persisted — the password is
   * intentionally discarded after the caller has used it to verify identity.
   * Biometric unlock only gates the already-stored JWT.
   */
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  saveCredentialsForBiometric: async (_email: string, _password: string) => {
    try {
      await SecureStore.setItemAsync(BIOMETRIC_ENABLED_KEY, '1');
      hasCredentialsSaved = true;
    } catch (error) {
      console.error('Error enabling biometric unlock:', error);
      throw error;
    }
  },

  /**
   * Disable biometric unlock.
   */
  clearBiometricCredentials: async () => {
    try {
      await SecureStore.deleteItemAsync(BIOMETRIC_ENABLED_KEY);
      // Also scrub legacy keys if a pre-migration install still has them.
      await SecureStore.deleteItemAsync(LEGACY_BIOMETRIC_EMAIL_KEY).catch(() => {});
      await SecureStore.deleteItemAsync(LEGACY_BIOMETRIC_PASSWORD_KEY).catch(() => {});
      hasCredentialsSaved = false;
    } catch (error) {
      console.error('Error clearing biometric credentials:', error);
    }
  },

  /**
   * Check if biometric credentials are saved
   */
  hasSavedCredentials: () => {
    return hasCredentialsSaved;
  },
}));

// ============================================================================
// SELECTORS (Shallow for performance)
// ============================================================================

/**
 * Use when you only need user data
 */
export const useAuthUser = () =>
  useAuthStore(
    useShallow((state) => ({
      user: state.user,
      isAuthenticated: state.isAuthenticated,
    }))
  );

/**
 * Use when you only need the token
 */
export const useAuthToken = () =>
  useAuthStore(
    useShallow((state) => ({
      token: state.token,
      isAuthenticated: state.isAuthenticated,
    }))
  );

/**
 * Use when you only need auth actions
 */
export const useAuthActions = () =>
  useAuthStore(
    useShallow((state) => ({
      login: state.login,
      logout: state.logout,
      initialize: state.initialize,
      refreshUser: state.refreshUser,
    }))
  );

/**
 * Use when you only need loading state
 */
export const useAuthLoading = () =>
  useAuthStore(
    useShallow((state) => ({
      isLoading: state.isLoading,
    }))
  );
