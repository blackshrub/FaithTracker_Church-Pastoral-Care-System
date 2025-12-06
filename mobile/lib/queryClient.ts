/**
 * Query Client with Persistence
 *
 * Provides offline-first data caching using:
 * - TanStack Query for data fetching and caching
 * - Storage abstraction (MMKV in production, in-memory in Expo Go)
 * - Automatic cache restoration on app start
 *
 * Benefits:
 * - Instant data display on subsequent app opens
 * - Works offline with cached data
 * - Automatic background refresh when online
 */

import { QueryClient } from '@tanstack/react-query';
import { createSyncStoragePersister } from '@tanstack/query-sync-storage-persister';
import { persistQueryClient } from '@tanstack/react-query-persist-client';

// Use centralized storage (works in both Expo Go and production)
import { storage } from '@/lib/storage';

// Key prefix for query cache storage
const CACHE_KEY_PREFIX = 'query-cache:';

// Storage adapter for TanStack Query persister
const storageAdapter = {
  setItem: (key: string, value: string) => {
    storage.set(CACHE_KEY_PREFIX + key, value);
  },
  getItem: (key: string) => {
    const value = storage.getString(CACHE_KEY_PREFIX + key);
    return value ?? null;
  },
  removeItem: (key: string) => {
    storage.remove(CACHE_KEY_PREFIX + key);
  },
};

// Create query client with optimized defaults
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Data freshness settings
      staleTime: 1000 * 60 * 5, // 5 minutes - data considered fresh
      gcTime: 1000 * 60 * 60 * 24, // 24 hours - keep in cache for offline

      // Network behavior
      refetchOnWindowFocus: false, // Don't refetch on app focus
      refetchOnReconnect: true, // Refetch when network reconnects
      retry: 2, // Retry failed requests twice

      // Offline support
      networkMode: 'offlineFirst', // Use cache first, then network
    },
    mutations: {
      retry: 1,
      networkMode: 'offlineFirst',
    },
  },
});

// Create persister with storage adapter
const persister = createSyncStoragePersister({
  storage: storageAdapter,
  // Throttle writes to avoid performance issues
  throttleTime: 1000,
});

// Set up persistence (async but non-blocking)
persistQueryClient({
  queryClient,
  persister,
  // Max age for cached data (7 days)
  maxAge: 1000 * 60 * 60 * 24 * 7,
  // Don't restore cache during hydration - let it happen in background
  hydrateOptions: {},
  dehydrateOptions: {
    shouldDehydrateQuery: (query) => {
      // Only persist successful queries with data
      return query.state.status === 'success' && !!query.state.data;
    },
  },
});

/**
 * Clear all cached query data
 * Use this on logout to clear sensitive data
 */
export function clearQueryCache() {
  queryClient.clear();
  // Clear storage keys with our prefix
  const allKeys = storage.getAllKeys();
  allKeys.forEach((key) => {
    if (key.startsWith(CACHE_KEY_PREFIX)) {
      storage.remove(key);
    }
  });
}

/**
 * Get cache statistics for debugging
 */
export function getCacheStats() {
  const allKeys = storage.getAllKeys();
  const cacheKeys = allKeys.filter((key) => key.startsWith(CACHE_KEY_PREFIX));
  const totalSize = cacheKeys.reduce((acc: number, key: string) => {
    const value = storage.getString(key);
    return acc + (value?.length ?? 0);
  }, 0);

  return {
    itemCount: cacheKeys.length,
    totalSizeBytes: totalSize,
    totalSizeKB: (totalSize / 1024).toFixed(2),
  };
}

export default queryClient;
