/**
 * Storage Utilities
 *
 * Uses MMKV for production builds (faster and more reliable)
 * Falls back to in-memory storage for Expo Go development
 */

import Constants from 'expo-constants';

// ============================================================================
// STORAGE INTERFACE
// ============================================================================

/**
 * Storage interface matching MMKV's API
 */
interface StorageInterface {
  getString(key: string): string | undefined;
  set(key: string, value: string | number | boolean): void;
  getNumber(key: string): number | undefined;
  getBoolean(key: string): boolean | undefined;
  remove(key: string): void;
  clearAll(): void;
  getAllKeys(): string[];
  contains(key: string): boolean;
}

// ============================================================================
// IN-MEMORY STORAGE (for Expo Go)
// ============================================================================

/**
 * In-memory storage implementation for Expo Go
 * Provides same interface as MMKV but data doesn't persist
 */
class InMemoryStorage implements StorageInterface {
  private data: Map<string, string | number | boolean> = new Map();

  getString(key: string): string | undefined {
    const value = this.data.get(key);
    return typeof value === 'string' ? value : undefined;
  }

  set(key: string, value: string | number | boolean): void {
    this.data.set(key, value);
  }

  getNumber(key: string): number | undefined {
    const value = this.data.get(key);
    return typeof value === 'number' ? value : undefined;
  }

  getBoolean(key: string): boolean | undefined {
    const value = this.data.get(key);
    return typeof value === 'boolean' ? value : undefined;
  }

  remove(key: string): void {
    this.data.delete(key);
  }

  clearAll(): void {
    this.data.clear();
  }

  getAllKeys(): string[] {
    return Array.from(this.data.keys());
  }

  contains(key: string): boolean {
    return this.data.has(key);
  }
}

// ============================================================================
// STORAGE INSTANCE
// ============================================================================

/**
 * Check if we're running in Expo Go
 */
const isExpoGo = Constants.executionEnvironment === 'storeClient';

/**
 * Create storage instance based on environment
 */
function createStorage(): StorageInterface {
  if (isExpoGo) {
    console.log('[Storage] Using in-memory storage (Expo Go mode)');
    return new InMemoryStorage();
  }

  try {
    // Dynamic import for MMKV - only loads in production builds
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { createMMKV } = require('react-native-mmkv');
    console.log('[Storage] Using MMKV storage (production mode)');
    return createMMKV({ id: 'faithtracker-storage' });
  } catch (error) {
    console.warn('[Storage] MMKV not available, falling back to in-memory storage');
    return new InMemoryStorage();
  }
}

/**
 * Main storage instance
 */
export const storage: StorageInterface = createStorage();

// ============================================================================
// STORAGE KEYS
// ============================================================================

/**
 * Centralized storage keys to avoid magic strings
 */
export const STORAGE_KEYS = {
  // Auth
  ACCESS_TOKEN: 'access_token',
  REFRESH_TOKEN: 'refresh_token',
  USER_DATA: 'user_data',

  // Notifications
  NOTIFICATION_ENABLED: 'notification_enabled',
  PUSH_TOKEN: 'push_token',
  DAILY_DIGEST_ENABLED: 'daily_digest_enabled',

  // Theme
  THEME_MODE: 'theme_mode',

  // Biometrics
  BIOMETRIC_ENABLED: 'biometric_enabled',
  BIOMETRIC_CREDENTIALS: 'biometric_credentials',

  // Offline sync
  OFFLINE_QUEUE: 'offline_queue',
  LAST_SYNC_TIME: 'last_sync_time',

  // Cache
  DASHBOARD_CACHE: 'dashboard_cache',
  MEMBERS_CACHE: 'members_cache',

  // User preferences
  LANGUAGE: 'language',
  FIRST_LAUNCH: 'first_launch',
  ONBOARDING_COMPLETE: 'onboarding_complete',
} as const;

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

/**
 * Get a JSON object from storage
 */
export function getJSON<T>(key: string): T | null {
  try {
    const value = storage.getString(key);
    if (value) {
      return JSON.parse(value) as T;
    }
  } catch (error) {
    console.error(`Failed to parse JSON for key ${key}:`, error);
  }
  return null;
}

/**
 * Set a JSON object in storage
 */
export function setJSON(key: string, value: unknown): void {
  try {
    storage.set(key, JSON.stringify(value));
  } catch (error) {
    console.error(`Failed to stringify JSON for key ${key}:`, error);
  }
}

/**
 * Remove a key from storage
 */
export function remove(key: string): void {
  storage.remove(key);
}

/**
 * Clear all storage
 */
export function clearAll(): void {
  storage.clearAll();
}

/**
 * Get all keys in storage
 */
export function getAllKeys(): string[] {
  return storage.getAllKeys();
}

/**
 * Check if a key exists
 */
export function has(key: string): boolean {
  return storage.contains(key);
}

/**
 * Check if storage is persistent (MMKV) or temporary (in-memory)
 */
export function isPersistent(): boolean {
  return !isExpoGo;
}

export default {
  storage,
  STORAGE_KEYS,
  getJSON,
  setJSON,
  remove,
  clearAll,
  getAllKeys,
  has,
  isPersistent,
};
